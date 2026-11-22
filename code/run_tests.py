"""Run the test set against each prompt version, then score the results.

  python code/run_tests.py run [--versions v1,v2,v3,v4] [--tests 1,2,3] [--force]
  python code/run_tests.py evaluate

'run' calls your real LLM (needs LLM_API_KEY / LLM_MODEL) and saves every raw reply
in test-data/outputs/<version>/test<ID>.json. Already-saved runs are skipped, so you
can stop and resume. 'evaluate' scores the saved replies (no LLM calls) and writes
test-data/results.json and test-data/results.md.
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "code"))

from bugbuddy import llm, pipeline  # noqa: E402
from bugbuddy.checker import evaluate as check  # noqa: E402

TESTS = json.loads((ROOT / "test-data/tests.json").read_text(encoding="utf-8"))
OUT = ROOT / "test-data/outputs"
ALL_VERSIONS = ["v1", "v2", "v3", "v4"]


def cmd_run(args):
    versions = args.versions.split(",")
    ids = {int(x) for x in args.tests.split(",")} if args.tests else {t["id"] for t in TESTS}
    print(f"Model: {llm.describe()}")
    todo = [(v, t) for v in versions for t in TESTS if t["id"] in ids]
    for n, (v, t) in enumerate(todo, 1):
        path = OUT / v / f"test{t['id']:02d}.json"
        if path.exists() and not args.force:
            print(f"[{n}/{len(todo)}] {v} test {t['id']}: saved already, skipped")
            continue
        try:
            rec = pipeline.run_version(v, t["language"], t["code"], t["error"])
        except llm.LLMError as exc:
            print(f"[{n}/{len(todo)}] {v} test {t['id']}: FAILED ({exc}). Re-run to retry.")
            continue
        rec["test_id"] = t["id"]
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(rec, indent=1, ensure_ascii=False), encoding="utf-8")
        print(f"[{n}/{len(todo)}] {v} test {t['id']}: saved ({rec['total_latency_s']}s)")
        time.sleep(args.sleep)
    print("Done. Now run: python code/run_tests.py evaluate")


def cmd_evaluate(_args):
    results = {"versions": {}, "tests": {}, "model": None, "provider": None}
    for v in ALL_VERSIONS:
        per = {}
        for t in TESTS:
            path = OUT / v / f"test{t['id']:02d}.json"
            if not path.exists():
                continue
            rec = json.loads(path.read_text(encoding="utf-8"))
            verdict = check(t, rec)
            verdict["json_ok"] = rec.get("json_ok")
            verdict["latency_s"] = rec.get("total_latency_s")
            per[t["id"]] = verdict
            first = rec["steps"][0]
            results["model"], results["provider"] = first["model"], first["provider"]
        if not per:
            continue
        n = len(per)
        fixes = [t for t in TESTS if t["id"] in per and t["check"] == "fix"]
        declines = [t for t in TESTS if t["id"] in per and t["check"] == "decline"]
        js = [per[i]["json_ok"] for i in per if per[i]["json_ok"] is not None]
        results["versions"][v] = {
            "runs": n,
            "pass_total": sum(per[i]["pass"] for i in per),
            "fix_pass": sum(per[t["id"]]["pass"] for t in fixes), "fix_total": len(fixes),
            "decline_pass": sum(per[t["id"]]["pass"] for t in declines), "decline_total": len(declines),
            "json_valid": sum(js) if js else None, "json_total": len(js) if js else None,
            "avg_latency_s": round(sum(per[i]["latency_s"] or 0 for i in per) / n, 1),
        }
        results["tests"][v] = per
    (ROOT / "test-data/results.json").write_text(json.dumps(results, indent=1), encoding="utf-8")

    lines = [f"# Test results (model: {results['provider']} / {results['model']})", "",
             "| Version | Runs | Overall pass | Fix verified | Declined invalid | Valid JSON | Avg latency (s) |",
             "|---|---|---|---|---|---|---|"]
    for v, m in results["versions"].items():
        js = f"{m['json_valid']}/{m['json_total']}" if m["json_total"] else "n/a"
        lines.append(f"| {v} | {m['runs']} | {m['pass_total']}/{m['runs']} | {m['fix_pass']}/{m['fix_total']} "
                     f"| {m['decline_pass']}/{m['decline_total']} | {js} | {m['avg_latency_s']} |")
    lines += ["", "## Per-test results (Pass/Fail and reason)", ""]
    for t in TESTS:
        row = [f"{t['id']:>2} {t['type']:<7}"]
        for v in results["tests"]:
            r = results["tests"][v].get(t["id"])
            row.append(f"{v}: {'PASS' if r and r['pass'] else 'FAIL'}" if r else f"{v}: -")
        fin = results["tests"].get("v4", {}).get(t["id"])
        lines.append(" | ".join(row) + (f"  ({fin['reason']})" if fin and not fin["pass"] else ""))
    cand = [t["id"] for t in TESTS if results["tests"].get("v1", {}).get(t["id"], {"pass": True})["pass"] is False
            and results["tests"].get("v4", {}).get(t["id"], {"pass": False})["pass"]]
    lines += ["", "Good before/after candidates for the reel (v1 failed, v4 passed): "
              + (", ".join(f"test {i}" for i in cand) if cand else "none - pick any test where outputs differ visibly")]
    (ROOT / "test-data/results.md").write_text("\n".join(lines), encoding="utf-8")
    print("\n".join(lines))


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    r = sub.add_parser("run")
    r.add_argument("--versions", default=",".join(ALL_VERSIONS))
    r.add_argument("--tests", default="")
    r.add_argument("--force", action="store_true")
    r.add_argument("--sleep", type=float, default=2.0, help="seconds to wait between runs")
    r.set_defaults(fn=cmd_run)
    e = sub.add_parser("evaluate")
    e.set_defaults(fn=cmd_evaluate)
    a = ap.parse_args()
    a.fn(a)
