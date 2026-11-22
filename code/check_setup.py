"""Check your API setup before running the tests:  python code/check_setup.py"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "code"))
from bugbuddy import llm  # noqa: E402

c = llm.config()
print(f"Provider: {c['provider']}   Model: {c['model'] or '(not set)'}   Key set: {bool(c['key'])}")
if not c["key"]:
    sys.exit("No key found. Set LLM_API_KEY (see README.md, step 2).")
if c["provider"] == "gemini" and not c["model"]:
    print("Models your key can use (copy one name into LLM_MODEL, prefer a 'flash' or 'flash-lite' one):")
    for m in llm.list_gemini_models():
        print("  ", m)
    sys.exit(0)
try:
    r = llm.call_llm("Reply with the single word: ready", "ping", temperature=0.0, max_tokens=50)
    print("Model replied:", r.text.strip()[:60], f"({r.latency_s}s)  -> setup OK")
except llm.LLMError as exc:
    sys.exit(f"Setup problem: {exc}")
