"""BugBuddy AI - Streamlit app.  Run:  streamlit run code/app.py"""
import json
import os
import sys
from pathlib import Path

import streamlit as st

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "code"))

# On Streamlit Cloud, keys live in st.secrets (never in the repository).
try:
    for k in ("LLM_PROVIDER", "LLM_MODEL", "LLM_API_KEY", "LLM_BASE_URL"):
        if k in st.secrets and k not in os.environ:
            os.environ[k] = str(st.secrets[k])
except Exception:
    pass

from bugbuddy import llm, pipeline  # noqa: E402

st.set_page_config(page_title="BugBuddy AI", page_icon="🐞", layout="wide")

SAMPLES = {t["short"]: t for t in json.loads((ROOT / "test-data/tests.json").read_text(encoding="utf-8"))
           if t["check"] == "fix" and t["id"] in (1, 3, 6, 8)}
LANGS = ["Python", "JavaScript", "Java", "C", "C++", "Other"]

st.title("🐞 BugBuddy AI")
st.caption("Paste your code and the error. BugBuddy finds the cause, fixes the code and explains it in simple words.")

with st.sidebar:
    st.subheader("Try a sample")
    choice = st.selectbox("Sample bug", ["(write my own)"] + list(SAMPLES))
    st.markdown("---")
    st.caption(f"Model: {llm.describe()}")
    st.caption("Do not paste passwords, API keys or personal data.")

sample = SAMPLES.get(choice)
col_in, col_out = st.columns(2)

with col_in:
    lang_default = LANGS.index(sample["language"]) if sample and sample["language"] in LANGS else 0
    language = st.selectbox("Programming language", LANGS, index=lang_default)
    code = st.text_area("Your code", value=sample["code"] if sample else "", height=260, key=f"code-{choice}")
    error = st.text_area("Error message (or describe what goes wrong)", value=sample["error"] if sample else "",
                         height=100, key=f"err-{choice}")
    go = st.button("Debug my code", type="primary")

with col_out:
    if go:
        if not code.strip() and not error.strip():
            st.warning("Please paste your code and/or the error message.")
        else:
            with st.spinner("Step 1: finding the cause...  Step 2: writing the fix..."):
                try:
                    rec = pipeline.run_version("v4", language, code, error)
                except llm.LLMError as exc:
                    st.error(f"The AI service could not be reached: {exc}")
                    st.stop()
            r = rec["parsed"]
            if r.get("parse_error") or r.get("status") == "parse_error":
                st.error("The AI reply could not be read. Please press the button again.")
            elif r.get("status") != "ok":
                st.warning("BugBuddy needs more information before it can help.")
                st.write(r.get("missing_info") or "Please share the code and the exact error message.")
            else:
                st.subheader(f"Cause: {r.get('error_type', 'Problem found')}")
                st.write(r.get("root_cause", ""))
                if r.get("location"):
                    st.caption(f"Where: {r['location']}")
                if r.get("other_bugs"):
                    st.info("Other problems found: " + "; ".join(map(str, r["other_bugs"])))
                st.subheader("Fixed code")
                st.code(r.get("fixed_code", ""), language=language.lower() if language != "Other" else None)
                st.subheader("Explanation")
                st.write(r.get("explanation", ""))
                if r.get("steps"):
                    st.subheader("How to debug this next time")
                    for i, s in enumerate(r["steps"], 1):
                        st.markdown(f"{i}. {s}")
                if r.get("tip"):
                    st.success("Tip: " + r["tip"])
            st.caption(f"Answered in {rec['total_latency_s']} s using {len(rec['steps'])} prompt step(s).")
    else:
        st.info("Your result will appear here.")
