# tools/ai_planner — mission-planner chat over the solver (SKELETON)

Status: scaffold only. **No API has been called.** Nothing here produces a number shown in the app.

- Model: Gemini via **Vertex AI** (`google-genai`, `GOOGLE_GENAI_USE_VERTEXAI=True`). The Google Cloud trial credit applies to Vertex AI, not to the AI Studio Gemini API.
- Config from env only: `GOOGLE_CLOUD_PROJECT`, `GOOGLE_CLOUD_LOCATION` (default `us-central1`), auth via `gcloud auth application-default login`. No keys in code or in the static site. Set a billing budget alert first.
- Tools: `python -m polaris_solver --tool-spec` (run from `tools/`, needs the solver venv: set `POLARIS_PYTHON` to its python).
- Guard: `grounding_check(reply, tool_results)` rejects any number in the reply that is not in that turn's tool results (exact value; rounding is rejected). Blocked replies are not shown. Shown replies are prefixed **AI-GENERATED**.

Tests (no network):

```bash
cd tools/ai_planner && python3 -m unittest test_planner -v
```

Next: implement `ask()` (function-calling loop → `polaris_solver.solve()` → `grounding_check` → label) and a Cloud Run / local proxy so the browser never holds credentials.
