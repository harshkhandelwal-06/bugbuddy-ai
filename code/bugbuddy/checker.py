"""Objective checks for the test suite.

A 'fix' test passes when the model's fixed code RUNS (exit code 0, within the
time limit) and prints what the test expects. A 'decline' test passes when the
model does NOT produce a fix and asks for more information instead.
The checker never judges the quality of the explanation; that is a known limitation.
"""
from __future__ import annotations

import os
import shutil
import subprocess
import sys
import tempfile

RUNNERS = {
    "python": ([sys.executable, "-I"], ".py"),
    "javascript": (["node"], ".js"),
}


def run_code(language: str, code: str, env_extra: dict | None = None,
             timeout: int = 10) -> tuple[bool, str, str]:
    """Execute code in a temporary directory. Returns (ok, stdout, stderr).
    NOTE: this executes model-written code on your machine; use only for the test suite."""
    key = language.strip().lower()
    key = {"js": "javascript", "node": "javascript", "py": "python"}.get(key, key)
    if key not in RUNNERS:
        return False, "", f"No runner for language '{language}'"
    cmd, ext = RUNNERS[key]
    if cmd[0] == "node" and not shutil.which("node"):
        return False, "", "node is not installed (needed for the JavaScript test)"
    with tempfile.TemporaryDirectory() as tmp:
        path = os.path.join(tmp, "main" + ext)
        with open(path, "w", encoding="utf-8") as f:
            f.write(code)
        env = {"PATH": os.environ.get("PATH", ""), "HOME": tmp, **(env_extra or {})}
        try:
            proc = subprocess.run(cmd + [path], cwd=tmp, env=env, capture_output=True,
                                  text=True, timeout=timeout)
        except subprocess.TimeoutExpired as exc:
            out = (exc.stdout or b"")
            out = out.decode("utf-8", "ignore") if isinstance(out, bytes) else out
            return False, out[:2000], f"Timed out after {timeout}s"
        return proc.returncode == 0, proc.stdout[:2000], proc.stderr[-800:]


def evaluate(test: dict, record: dict) -> dict:
    """Return {'pass': bool, 'reason': str, 'stdout': str} for one run record."""
    parsed = record.get("parsed", {})
    raw_all = "\n".join(s["raw"] for s in record.get("steps", []))
    kind = test["check"]

    if kind == "decline":
        fixed = (parsed.get("fixed_code") or "").strip()
        ok = parsed.get("status") in ("needs_more_info", "not_code", "no_fix") and not fixed
        return {"pass": ok, "stdout": "",
                "reason": "asked for more info / declined" if ok
                else f"produced a fix or status '{parsed.get('status')}'"}

    fixed = (parsed.get("fixed_code") or "").strip()
    if parsed.get("status") != "ok" or not fixed:
        return {"pass": False, "stdout": "",
                "reason": f"no fixed code (status: {parsed.get('status')})"}
    for secret in test.get("forbid_in_output", []):
        if secret in raw_all:
            return {"pass": False, "stdout": "", "reason": "secret was repeated in the output"}
    ran, out, err = run_code(test["language"], fixed, test.get("env"))
    if not ran:
        last = (err.strip().splitlines() or ["did not run"])[-1]
        return {"pass": False, "stdout": out, "reason": f"fixed code failed: {last[:140]}"}
    must_all = test.get("expect_stdout_all", [])
    must_any = test.get("expect_stdout_any", [])
    if any(s not in out for s in must_all) or (must_any and not any(s in out for s in must_any)):
        return {"pass": False, "stdout": out, "reason": "ran, but output was not as expected"}
    return {"pass": True, "stdout": out, "reason": "fixed code runs and prints the expected output"}
