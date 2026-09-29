# JD Lens: rules for Claude

Read docs/DESIGN.md before any task. Work only on the phase I name.

## Non-negotiables
- LLM as witness, code as judge: the LLM returns fields plus exact evidence quotes only.
  All parsing, checking and scoring is plain Python in app/pipeline/.
- Only app/llm/client.py may import the LLM SDK.
- Never return or display a value whose evidence is not verified.
- Fail closed: invalid LLM output after one retry → status needs_review with a reason.
- app/schemas/extraction_v1.py is a contract. Changes mean a new version file.
- Never edit a test just to make it pass. If a test looks wrong, say so and stop.
- If a task seems impossible or needs a workaround, explain in writing before coding it.

## Workflow
- Propose a short plan first; wait for my OK.
- Write tests with the code. Run `pytest -q` and `ruff check .` before saying done.
- Keep functions small and typed. No new dependencies without asking.

## Commands
- Tests: cd backend && pytest -q
- Lint: cd backend && ruff check .
- API: cd backend && uvicorn app.main:app --reload
- Web: cd frontend && npm run dev

## Local machine notes
- Windows. Backend venv is backend/.venv (Python 3.12 via uv); activate it with
  `backend\.venv\Scripts\Activate.ps1` or run tools as `.venv\Scripts\pytest`.
- Docker is not installed yet, so docker-compose Postgres may be unavailable; /health reports db: error.
