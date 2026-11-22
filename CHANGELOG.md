# Changelog (since Milestone 1)

Milestone 1 (proposal) contained only the idea and one baseline prompt. No code existed.

## 2026-11-22
- Created the repository structure (README, prompts/, code/, test-data/, docs/, tests/).
- Saved the Milestone 1 baseline prompt as prompt version v1 and wrote versions v2 (JSON output), v3 (2 examples, temperature 0.2) and the final two-prompt workflow v4 (P1 diagnose + P2 fix and explain).
- Built the pipeline (prompt loader, provider adapter for Gemini/Claude/OpenAI-compatible APIs, JSON parser, P1 guard step) and the Streamlit web app.
- Wrote 14 test inputs (8 normal, 4 edge, 2 invalid) and a test runner whose checker executes the fixed code to decide Pass/Fail.
- Added offline unit tests for the pipeline and the app, four diagrams, and the Business Model Canvas.
