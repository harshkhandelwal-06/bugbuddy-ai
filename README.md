# BugBuddy AI - Bug Explanation and Fix Assistant

Team **404 not found** | SCSE4041 Prompt Engineering, Milestone 2

Members: Harsh Khandelwal (S24CSEU1988), Anuj Gupta (S24CSEU1990), Gokarn Nath Mishra (S24CSEU2634)

Prototype link: _paste the deployed app link here_

## What it does
Paste a programming language, your code and the error message. BugBuddy returns the cause, fixed code, a simple explanation, debugging steps and a tip. If the code is missing or the input is not code, it says what is missing and writes no fix.
It is a two-prompt workflow: **P1** checks the input and diagnoses, **P2** writes the fix and explanation (`prompts/final/`).

## Folder structure
| Path | Content |
|---|---|
| `prompts/v1, v2, v3` | Older prompt versions (v1 = Milestone 1 baseline) |
| `prompts/final` | Final prompts P1 and P2 (used by the app) |
| `code/` | `app.py` (web app), `bugbuddy/` (pipeline), `run_tests.py`, `check_setup.py`, `build_docs.py` |
| `test-data/` | `tests.json` (14 inputs), `outputs/` (saved model replies), `results.json/.md` |
| `docs/` | Diagrams, screenshots, Milestone 2 PDF, Business Model Canvas |
| `tests/` | Offline unit tests (no API key needed) |
| `CHANGELOG.md` | Dated changes since Milestone 1 |

## Run it
1. `pip install -r requirements.txt`
2. Get an API key (for example a free key from Google AI Studio) and set:
   ```
   export LLM_PROVIDER=gemini        # or anthropic / openai (openai also covers Groq, OpenRouter via LLM_BASE_URL)
   export LLM_API_KEY=your-key
   python code/check_setup.py        # lists usable models; then: export LLM_MODEL=<name>
   python code/check_setup.py        # should print "setup OK"
   ```
3. Web app: `streamlit run code/app.py`
4. Tests: `python code/run_tests.py run` then `python code/run_tests.py evaluate`
5. Documents: `python code/build_docs.py`

**Safety note:** the test checker runs the model's fixed code on your computer (10 s limit, temp folder). Use it only with the provided test set, ideally in Colab or a throw-away environment.
Never commit API keys. `.env` and `.streamlit/secrets.toml` are git-ignored.
