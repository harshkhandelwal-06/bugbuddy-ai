"""Runs a prompt version (a workflow of 1 or 2 prompts) and parses the result."""
from __future__ import annotations

import json
import re
from typing import Callable

from . import llm as llm_mod
from .prompts import load_version

LLMCall = Callable[..., "llm_mod.LLMResponse"]


def strip_fences(text: str) -> str:
    t = text.strip()
    m = re.match(r"^```[a-zA-Z]*\s*\n(.*?)\n?```\s*$", t, flags=re.S)
    return m.group(1).strip() if m else t


def parse_json(text: str) -> tuple[dict | None, bool]:
    """Return (object, strict_ok). strict_ok is True when the reply is valid JSON
    (after removing a surrounding markdown fence). A looser brace-extraction is
    used as a fallback so the app keeps working, but it is reported as not strict."""
    t = strip_fences(text)
    try:
        obj = json.loads(t)
        return (obj, True) if isinstance(obj, dict) else (None, False)
    except json.JSONDecodeError:
        pass
    i, j = t.find("{"), t.rfind("}")
    if i != -1 and j > i:
        try:
            obj = json.loads(t[i:j + 1])
            return (obj, False) if isinstance(obj, dict) else (None, False)
        except json.JSONDecodeError:
            pass
    return None, False


def first_code_block(text: str) -> str:
    m = re.search(r"```[a-zA-Z0-9_+#-]*[ \t]*\n(.*?)```", text, flags=re.S)
    return m.group(1).strip("\n") if m else ""


def run_version(version: str, language: str, code: str, error: str,
                llm: LLMCall | None = None) -> dict:
    """Run one prompt version on one input. Returns a JSON-serialisable record."""
    call = llm or llm_mod.call_llm
    prompts = load_version(version)
    variables = {"language": language, "code": code, "error": error or "(none given)"}
    steps, parsed, json_ok = [], {}, None

    for idx, pr in enumerate(prompts):
        extra = {}
        if idx == 1:  # P2 receives the P1 diagnosis (without status/missing_info noise)
            diag = {k: v for k, v in parsed.items()
                    if k in ("error_type", "root_cause", "location", "bugs_found",
                             "other_bugs", "contains_secret")}
            extra["diagnosis"] = json.dumps(diag, ensure_ascii=False)
        user = pr.render_user(**variables, **extra)
        resp = call(pr.system, user, pr.temperature)
        steps.append({"prompt_id": pr.id, "temperature": pr.temperature, "user_prompt": user,
                      "raw": resp.text, "latency_s": resp.latency_s,
                      "provider": resp.provider, "model": resp.model})
        if version == "v1":
            parsed = {"status": "ok" if first_code_block(resp.text) else "no_fix",
                      "fixed_code": first_code_block(resp.text), "explanation": resp.text}
            break
        obj, strict = parse_json(resp.text)
        json_ok = strict if json_ok is None else (json_ok and strict)
        if obj is None:
            parsed["parse_error"] = True
            parsed.setdefault("status", "parse_error")
            break
        parsed.update(obj)
        if parsed.get("status") != "ok":  # P1 guard: stop, ask the user for more info
            break

    return {"version": version, "language": language, "steps": steps, "parsed": parsed,
            "json_ok": json_ok, "total_latency_s": round(sum(s["latency_s"] for s in steps), 2)}
