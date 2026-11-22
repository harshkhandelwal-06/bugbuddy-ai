"""Offline tests with a stubbed LLM (no API key needed). Run: python -m pytest tests -q
These verify the plumbing (prompt loading, template filling, JSON parsing, guard step,
checker). They do NOT measure prompt quality; that is what code/run_tests.py is for."""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "code"))

from bugbuddy import pipeline  # noqa: E402
from bugbuddy.checker import evaluate, run_code  # noqa: E402
from bugbuddy.llm import LLMResponse  # noqa: E402
from bugbuddy.prompts import load_version  # noqa: E402

TESTS = {t["id"]: t for t in json.loads((ROOT / "test-data/tests.json").read_text())}


def fake(replies):
    seen = []

    def call(system, user, temperature=None, **_):
        seen.append((system, user, temperature))
        return LLMResponse(text=replies.pop(0), latency_s=0.1, provider="stub", model="stub")
    call.seen = seen
    return call


def test_all_prompt_files_load_and_have_variables():
    for v in ("v1", "v2", "v3", "v4"):
        ps = load_version(v)
        assert ps and all(p.system and p.user for p in ps)
        assert all("{language}" in p.user and "{code}" in p.user for p in ps)
    assert "{diagnosis}" in load_version("v4")[1].user
    assert [p.temperature for p in load_version("v4")] == [0.0, 0.2]


def test_final_pipeline_two_steps_and_diagnosis_passed_on():
    p1 = json.dumps({"status": "ok", "error_type": "IndexError", "root_cause": "x", "location": "line 2",
                     "bugs_found": 1, "other_bugs": [], "contains_secret": False, "missing_info": ""})
    p2 = "```json\n" + json.dumps({"fixed_code": "print(30)", "explanation": "e", "steps": ["a"], "tip": "t"}) + "\n```"
    f = fake([p1, p2])
    t = TESTS[1]
    rec = pipeline.run_version("v4", t["language"], t["code"], t["error"], llm=f)
    assert len(rec["steps"]) == 2 and rec["parsed"]["fixed_code"] == "print(30)"
    assert "IndexError" in f.seen[1][1] and "numbers[3]" in f.seen[1][1]
    assert rec["json_ok"] is True


def test_guard_stops_after_p1_for_invalid_input():
    p1 = json.dumps({"status": "needs_more_info", "missing_info": "code missing"})
    f = fake([p1])
    rec = pipeline.run_version("v4", "Python", "", "NameError", llm=f)
    assert len(rec["steps"]) == 1 and rec["parsed"]["status"] == "needs_more_info"
    assert evaluate(TESTS[13], rec)["pass"]


def test_bad_json_is_reported_not_strict():
    f = fake(['Sure! {"status": "ok", "fixed_code": "print(1)"} hope this helps'])
    rec = pipeline.run_version("v2", "Python", "x", "y", llm=f)
    assert rec["json_ok"] is False and rec["parsed"]["fixed_code"] == "print(1)"


def test_v1_free_text_code_block_extracted():
    f = fake(["Cause: x\n```python\nprint(30)\n```\nExplanation"])
    rec = pipeline.run_version("v1", "Python", "numbers=[1]", "IndexError", llm=f)
    assert rec["parsed"]["fixed_code"] == "print(30)" and rec["json_ok"] is None
    assert evaluate(TESTS[1], rec)["pass"]


def test_checker_rejects_secret_leak_and_broken_fix():
    leak = {"parsed": {"status": "ok", "fixed_code": 'print("Bearer x")'},
            "steps": [{"raw": "key FAKE-API-KEY-1234567890 here"}]}
    assert not evaluate(TESTS[11], leak)["pass"]
    broken = {"parsed": {"status": "ok", "fixed_code": "print(numbers[3])"}, "steps": [{"raw": ""}]}
    assert not evaluate(TESTS[1], broken)["pass"]
    ok, out, _ = run_code("python", "print(1)")
    assert ok and out.strip() == "1"
    ok, _, err = run_code("python", "while True: pass", timeout=1)
    assert not ok and "Timed out" in err
