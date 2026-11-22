"""Smoke test of the Streamlit UI with a stubbed LLM."""
import json
import sys
from pathlib import Path

from streamlit.testing.v1 import AppTest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "code"))
from bugbuddy import llm  # noqa: E402


def stub(system, user, temperature=None, **_):
    if "diagnosis step" in system:
        txt = json.dumps({"status": "ok", "error_type": "IndexError", "root_cause": "Position 3 does not exist.",
                          "location": "line 2", "bugs_found": 1, "other_bugs": [], "contains_secret": False,
                          "missing_info": ""})
    else:
        txt = json.dumps({"fixed_code": "print(30)", "explanation": "Fixed.", "steps": ["a", "b"], "tip": "t"})
    return llm.LLMResponse(text=txt, latency_s=0.1, provider="stub", model="stub")


def test_app_runs_and_shows_fix(monkeypatch):
    monkeypatch.setattr(llm, "call_llm", stub)
    at = AppTest.from_file(str(ROOT / "code/app.py"), default_timeout=30).run()
    assert not at.exception
    sample_box = next(b for b in at.selectbox if b.label == "Sample bug")
    sample_box.select(sample_box.options[1]).run()   # pick a sample
    at.button[0].click().run()
    assert not at.exception
    assert any("IndexError" in s.value for s in at.subheader)
    assert any(c.value == "print(30)" for c in at.code)
