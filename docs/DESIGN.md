# JD Lens: Design Doc & Build Plan

Sep 30, 2026 · @Manav

## Overview

JD Lens turns a pasted job posting into verified fields and a fit score, and refuses to show any value it cannot trace back to the posting's own words. It is a weekend-sized portfolio project (about 18–20 hours) built to match Kasparro's stack and their rule: **LLM as witness, code as judge.**

### Goals

- Extract 10 fields from a posting, each with an exact evidence quote from the text.
- Normalize money, dates and eligibility in plain Python, and flag anything ambiguous instead of guessing.
- Compute a fit score against your profile with deterministic rules.
- Show all postings in a dashboard sorted by deadline or score.
- Fail closed: an unusable extraction ends as `needs_review` with a reason, never with made-up values.

**Non-goals:** scraping job sites, login or multiple users, auto-applying, resume writing.

### Done means

- Pasting the Kasparro notice shows: stipend flagged ("Rs. 25,00" is not a valid number, and it conflicts with ₹ 25,000 in the JD), CTC split into ₹ 5–8 LPA cash plus ESOP, deadline 30 Sep 2026 09:00 IST, eligibility CGPA ≥ 6.0 with no backlogs.
- No field is displayed unless its quote was found in the text.
- At least 15 passing tests, CI green, a live URL, and a README with a failure teardown.

## Design principles

Seven rules decide every design choice below. Each one mirrors a line in the Kasparro JD.

1. **LLM as witness, code as judge.** The model only reads text and returns fields with quotes. Python verifies, normalizes and scores. No number the app shows comes straight from the model.
2. **Evidence or nothing.** Every field carries `evidence`, an exact substring of the posting. Code checks it is really there; if not, the field is marked `unverified` and its value is hidden.
3. **Fail closed.** Invalid JSON after one retry sets the posting to `needs_review` with a reason. Never partial, invented values.
4. **Schemas are contracts.** The extraction schema carries `schema_version = "1.0"`, stored with every result. Changing a field means a new version file, not an edit.
5. **Ambiguity is a result, not an error.** A value that doesn't parse cleanly is stored with a flag and a reason, and shown in red.
6. **A guard only protects the paths it sits on.** Every LLM call goes through `app/llm/client.py`. A test fails the build if any other module imports the LLM SDK.
7. **Say it in writing.** Anything cut or impossible goes into the README's Known limitations, not a silent workaround.

## Architecture

A Next.js dashboard calls a FastAPI backend; the backend runs a code-only pipeline, stores everything in Postgres, and reaches the LLM through exactly one module. The pipeline is where every decision happens. The LLM sits at the edge and only answers questions about the text.

```
Next.js dashboard ──► FastAPI (routers) ──► Pipeline (code only) ──► Postgres
                                                   │
                                                   ▼
                                            app/llm/client.py ──► LLM provider
```

| Layer | Choice | Why |
|---|---|---|
| Backend | Python 3.12, FastAPI, Pydantic v2 | Kasparro's stack; validation built in |
| Database | PostgreSQL 16, SQLAlchemy 2.0 async, Alembic | JD asks for real SQL and migrations |
| LLM | Any provider with JSON output (Gemini free tier is cheapest) | Swappable behind `llm/client.py` |
| Frontend | Next.js App Router, TypeScript, Tailwind | Kasparro's stack |
| Tests | pytest, pytest-asyncio, httpx | Async API tests without a server |
| Infra | Docker Compose locally; Render or Railway for API; Vercel for web; GitHub Actions CI | Free or cheap, one live URL |

## Data model

Five Postgres tables: one for you, one per posting, one row per extracted field, one score per posting, and a log of every LLM call so you can debug from traces. Create them with Alembic migrations, not `create_all`. No ORM relationships: lazy loading fails under asyncio, so services query child rows explicitly and `ON DELETE CASCADE` removes them.

| Table | Key columns | Notes |
|---|---|---|
| `profile` | id, name, skills text[], cgpa numeric(4,2) (3,2 tops out at 9.99), has_backlogs bool, preferred_locations text[], min_cash_inr int, updated_at | One row for now. Seed from `.env` if the profile page is cut. |
| `postings` | id uuid, raw_text, clean_text, content_hash (unique), source_label, status, status_reason, schema_version, prompt_version, model_name, created_at, processed_at | `status` = pending, verified, partial, needs_review. Same hash = duplicate. |
| `extracted_fields` | id, posting_id FK, field_name, raw_value, evidence, evidence_verified bool, normalized jsonb, flag, flag_reason | Unique on (posting_id, field_name, mention_index). `flag` = none, ambiguous, conflict, unverified, missing. |
| `match_scores` | posting_id PK/FK, profile_id FK, score int 0–100, eligible bool, breakdown jsonb, computed_at | Recomputed when the profile changes. The "Closed" badge is never stored: it depends on the clock, so it's computed at read time. |
| `llm_calls` | id, posting_id FK, attempt, prompt_version, model, latency_ms, input_tokens, output_tokens, raw_response, parse_ok bool, error, created_at | Your trace log. The failure teardown comes from here. |

### Extraction contract (`app/schemas/extraction_v1.py`)

This is what the LLM must return. Money fields are lists, because one posting can mention the same thing twice, and Kasparro's does.

```python
from typing import Literal
from pydantic import BaseModel, ConfigDict

class Mention(BaseModel):
    model_config = ConfigDict(extra="forbid")
    value: str | None      # as written, e.g. "Rs. 25,00 Per Month"
    evidence: str | None   # exact substring of the posting

class Skill(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str
    evidence: str

class ExtractionV1(BaseModel):
    model_config = ConfigDict(extra="forbid")
    schema_version: Literal["1.0"]
    company: Mention
    role_title: Mention
    location: Mention
    work_mode: Mention             # onsite / remote / hybrid, as written
    stipend: list[Mention]
    ctc: list[Mention]
    eligibility: Mention
    application_deadline: Mention
    apply_instructions: Mention
    required_skills: list[Skill]
```

### Normalized shapes (written by code into `extracted_fields.normalized`)

- Stipend: `{"period": "month", "min_inr": 25000, "max_inr": 25000}`
- CTC: `{"cash_min_inr": 500000, "cash_max_inr": 800000, "total_min_inr": 1000000, "total_max_inr": 1600000, "has_equity": true}`
- Deadline: `{"iso": "2026-09-30T09:00:00+05:30", "tz_assumed": true, "time_assumed": false}` (no time stated → 23:59:59, `time_assumed: true`)
- Eligibility: `{"cgpa_min": 6.0, "backlogs_allowed": false}`
- Work mode: `{"mode": "onsite", "days_per_week": 5}`

## Extraction pipeline

Every posting ends as `verified`, `partial` or `needs_review`, and the model's only job is step 2. A bad quote flags one field; an unusable response stops the whole posting.

1. **Ingest.** Trim, collapse whitespace into `clean_text`, hash it. A known hash returns the existing posting without calling the LLM.
2. **Extract.** `llm_client.extract(clean_text)` with prompt `extract_v1`, JSON mode, 30 s timeout. Every call is logged to `llm_calls`.
3. **Validate.** `ExtractionV1.model_validate_json()`. On failure, retry once with the validation error added to the prompt. Second failure → `needs_review`, reason `extraction_invalid: <short error>`.
4. **Verify evidence.** For each field, normalize spaces and curly quotes or dashes in both strings, then check `evidence in clean_text`. Not found → flag `unverified`, value hidden. Both null → flag `missing`. The value must also appear inside its own evidence (case-insensitive); otherwise `unverified` — a real quote must not vouch for an invented value.
5. **Normalize.** Pure functions, no LLM, run on the verified **evidence**, never on the model's value. Several money mentions that disagree → flag `conflict` and keep all of them.
6. **Status, score, save.** Company and role verified with no flags → `verified`; verified with some flags → `partial`; otherwise `needs_review`. Then score and write everything in one transaction.

### Money parser rules (`normalize/money.py`)

- Currency markers: `Rs`, `Rs.`, `INR`, `₹`, or none.
- Digit grouping must be valid Indian (`1,00,000`) or Western (`100,000`). Anything else, like `25,00`, is `ambiguous` with the reason.
- `LPA` or `per annum` → yearly (× 1,00,000 for LPA); `per month` or `/month` → monthly.
- Ranges: `-`, `–`, `—` or `to`, with the unit applying to both ends.
- `ESOP`, `equity` or `stock` in the evidence → `has_equity: true`; cash and total ranges kept apart.

### Prompt skeleton (`prompts/extract_v1.txt`)

```
You extract facts from a job posting. You do not judge or calculate.
Return JSON matching the schema. For every field:
- "value": the fact as written in the posting.
- "evidence": copy the exact span from the posting, character for character.
- If the posting does not state it, use null for both. Never guess.
If the same fact appears more than once (e.g. stipend), return every mention.

POSTING:
<<<
{clean_text}
>>>
```

## Fit scoring

The score is plain Python in `app/pipeline/scoring.py`: an eligibility gate first, then a 0–100 score from three parts. Only verified, unflagged fields count; anything else is treated as unknown.

### Eligibility gate (shown as a badge, separate from the score)

- `cgpa >= cgpa_min`, and `has_backlogs` is false when backlogs aren't allowed.
- Deadline already passed → posting shown as Closed.
- Any input unknown → badge says "Check manually", never "Eligible".

### Score

| Part | Weight | Rule |
|---|---|---|
| Skills | 50 | matched required skills ÷ total required × 50. Case-insensitive, with an alias map (`postgres` → `postgresql`, `react.js` → `react`, `nextjs` → `next.js`). |
| Location | 20 | 20 if remote, or the location is in `preferred_locations`; else 0. |
| Pay | 30 | 30 if `cash_max_inr >= min_cash_inr`; scaled linearly below that. Equity is never counted as cash. |

A part with unknown inputs is left out and the other weights are rescaled to 100. The `breakdown` JSON stores each part's inputs, points and whether it was left out, so the UI can explain every point.

## API design

Eight endpoints, all async, all with Pydantic request and response models and one error shape. The pipeline runs inside `POST /postings` (5–15 s is fine for v1); moving it to a background job is an extension. The LLM call runs outside any database transaction; its result is then written in one transaction (posting, fields, llm_calls, score). A concurrent duplicate is caught by the unique `content_hash`.

| Method | Path | Does | Returns |
|---|---|---|---|
| POST | `/postings` | Body `{raw_text, source_label?}`. Saves, runs the pipeline, scores. | 201 with the posting detail. Same text again → 200 with the existing posting. |
| GET | `/postings` | List. Query `status`, `sort=deadline` (default) or `sort=score`. | Summaries: company, role, deadline, cash range, score, eligible, status. |
| GET | `/postings/{id}` | Full detail: fields, evidence, flags, score breakdown, raw text. | Unverified values come back as `null`, with the flag and reason. |
| POST | `/postings/{id}/reprocess` | Reruns the pipeline, e.g. after a prompt change. | The new detail. |
| DELETE | `/postings/{id}` | Deletes a posting and its rows. | 204 |
| GET | `/profile` | Your profile. | Profile |
| PUT | `/profile` | Updates the profile and rescores every posting. | Profile |
| GET | `/health` | Database reachable, LLM key configured. | `{db: ok, llm_configured: true}` |

### Errors

Every error returns `{"error": {"code": "...", "message": "...", "details": ...}}`.

- `raw_text` under 200 or over 50,000 characters → 422 `validation_error`.
- Unknown id → 404 `not_found`.
- LLM timeout (30 s) or provider down → the posting is still saved, status `needs_review`, reason `llm_unavailable`; the response is 201 so the UI can offer Reprocess.
- More than 10 `POST /postings` a minute from one IP → 429 `rate_limited` (slowapi). This protects your API credits once the demo is public.

## Frontend

Four pages in Next.js (App Router, TypeScript, Tailwind). Every fetch handles loading, empty and error states, because the JD names exactly that. The API URL comes from `NEXT_PUBLIC_API_URL`; all calls live in `lib/api.ts`.

| Page | What it shows | States to handle |
|---|---|---|
| `/` Dashboard | Table: company, role, deadline countdown (red under 24 h, grey when closed), cash range, score, eligibility badge, status badge. Sort by deadline or score; filter by status. | Loading skeleton; empty ("Paste your first posting"); API down. |
| `/new` Paste | Textarea with a character count and a Submit button. Redirects to the detail page on success. | "Extracting… usually 5–15 s"; 422 message shown under the box; 429 message. |
| `/postings/[id]` Detail | Left: one card per field with value, flag badge and evidence quote. Right: the raw posting with each evidence span highlighted; clicking a card scrolls to its span. Below: score breakdown, Reprocess button. | `needs_review` banner with the reason; unverified fields in red with "Not found in text". |
| `/profile` | Skills tag input, CGPA, backlogs, preferred locations, minimum cash. Saving rescores everything. | Saving, saved, validation errors. |

The evidence highlight on the detail page is the best screenshot: it shows the "witness" idea in one glance.

## Testing strategy

Tests run with no network and no real LLM: pure functions are tested directly, and the pipeline uses a `FakeLLMClient` that returns canned responses. Aim for 20+ tests; the ones below are the minimum.

### Unit tests (`tests/unit/`, table-driven with `pytest.mark.parametrize`)

| Input | Expected |
|---|---|
| `₹ 25,000/month stipend` | 25,000 per month |
| `Rs. 25,00 Per Month` | flag `ambiguous`: "25,00" is not a valid digit grouping |
| `Rs. 5.00 –Rs. 8.00 LPA cash, plus an ESOP grant` | cash 500,000–800,000, `has_equity: true` |
| `1,00,000 per annum` | 100,000 per year (Indian grouping) |
| `30th Sept'2026 by 9.00 AM` | `2026-09-30T09:00:00+05:30`, `tz_assumed: true` |
| `30 Sept` | flag `ambiguous`: no year |
| Evidence = exact substring, or differs only in spaces or curly quotes | verified |
| Evidence = a paraphrase | unverified |
| CGPA 5.9 vs minimum 6.0 | `eligible: false` |
| No skills extracted | skills part left out, weights rescaled |

### Pipeline tests (`tests/pipeline/`, with `FakeLLMClient`)

- Valid response → `verified`, one call logged.
- Invalid JSON, then valid → `verified`, two calls logged, second prompt contains the validation error.
- Invalid twice → `needs_review` with reason, exactly two calls logged.
- Response with an invented quote → that field `unverified`, value hidden.
- Two stipend mentions that disagree → flag `conflict`, both shown.
- Provider timeout → `needs_review`, reason `llm_unavailable`.

### API tests (`tests/api/`, httpx `AsyncClient` against a test database)

- Short `raw_text` → 422 with the error shape.
- Same text posted twice → same id.
- Detail endpoint returns `null` for unverified values.

**Guard test.** Scan every file in `app/`; fail if anything other than `app/llm/client.py` imports the LLM SDK.

**Fixtures and eval.** Save the Kasparro notice as `tests/fixtures/postings/kasparro.txt` plus two or three postings you write yourself, each with an expected-output JSON. `python -m app.eval` runs them against the real model and prints field-level pass/fail. Put that table in the README.

## Repo structure and setup

One repo with `backend/` and `frontend/` folders.

```
jd-lens/
  CLAUDE.md                  # rules for Claude Code
  README.md
  docs/DESIGN.md             # this document
  docker-compose.yml         # postgres (+ api later)
  .env.example
  .github/workflows/ci.yml   # ruff + pytest on every push
  backend/
    pyproject.toml
    alembic.ini
    alembic/versions/
    app/
      main.py                # app, routers, error handlers, CORS
      config.py              # pydantic-settings
      db.py                  # async engine + session
      models.py              # SQLAlchemy tables
      schemas/
        extraction_v1.py     # the LLM contract
        api.py               # request/response models
      llm/
        client.py            # the ONLY module that imports the LLM SDK
        types.py             # LLMClient protocol, LLMResponse, LLMUnavailable (no SDK)
        prompt.py            # loads and fills prompts/<version>.txt
        prompts/extract_v1.txt
      pipeline/
        ingest.py            # clean_text + content_hash
        run.py               # orchestrates steps, sets status
        evidence.py
        normalize/money.py
        normalize/dates.py
        normalize/eligibility.py
        normalize/work_mode.py
        normalize/result.py  # Normalized(value, flag, reason) shared by all normalizers
        scoring.py
      routers/postings.py
      routers/profile.py
      routers/health.py
      cli.py                 # python -m app.cli <posting.txt>: one real run, printed
      eval.py
    tests/
      unit/  pipeline/  api/  fixtures/postings/
  frontend/
    app/page.tsx
    app/new/page.tsx
    app/postings/[id]/page.tsx
    app/profile/page.tsx
    components/
    lib/api.ts
```

**Environment** (`.env.example`): `DATABASE_URL`, `LLM_API_KEY`, `LLM_MODEL`, `LLM_TIMEOUT_S=30`, `ALLOWED_ORIGINS`, `NEXT_PUBLIC_API_URL`. Never commit `.env`.

### Run locally

```
docker compose up -d db
cd backend && pip install -e ".[dev]"
alembic upgrade head
uvicorn app.main:app --reload
cd ../frontend && npm install && npm run dev
```

**LLM choice.** Any provider with a JSON output mode works; Gemini's free tier keeps cost near zero. Check the provider's current free-tier limits before you start, since they change.

## Build plan

Seven phases, about 18–20 hours in total. Build the pure logic first with no LLM and no database: it's the part you'll be questioned on, and it's the easiest to test. Commit at the end of every phase.

### Phase 0 — Setup (1–2 h)
- Create the GitHub repo, folders, `CLAUDE.md`, `docs/DESIGN.md`, `.env.example`, `.gitignore`
- `docker-compose.yml` with Postgres; FastAPI app with `GET /health`
- ruff + pytest configured; GitHub Actions running both

Done when: `/health` answers locally and CI is green on an empty test.

### Phase 1 — Pure core (3–4 h)
- `evidence.py`: whitespace and quote normalization, substring check
- `normalize/money.py`: Rs / Rs. / INR / ₹, Indian and Western digit grouping, LPA, per month, ranges (-, –, —, "to"), equity words
- `normalize/dates.py`: ordinals, "Sept", '2026 years, "9.00 AM", IST default
- `normalize/eligibility.py` and `scoring.py` with the alias map
- All unit tests from the Testing section

Done when: every unit test passes and the Kasparro strings parse as expected.

### Phase 2 — LLM extraction (3 h)
- `schemas/extraction_v1.py` exactly as in Data model
- `llm/client.py`: one `extract()` function, JSON mode, 30 s timeout, returns raw text plus token counts
- `prompts/extract_v1.txt`: fields, "copy evidence exactly", "use null when absent, never guess"
- `pipeline/run.py`: parse → one retry with the error → evidence → normalize → status
- Pipeline tests with `FakeLLMClient`; guard test

Done when: pipeline tests pass, and one manual run on `kasparro.txt` gives the expected flags.

### Phase 3 — Database and API (3 h)
- SQLAlchemy models and the first Alembic migration for all five tables
- Routers for postings, profile, health; error handlers; rate limit on `POST /postings`
- Save every LLM call to `llm_calls`
- API tests

Done when: you can POST the Kasparro notice via `/docs` and GET back verified fields and a score.

### Phase 4 — Frontend (4 h)
- `lib/api.ts` with typed calls
- Dashboard, Paste, Detail (with evidence highlighting), Profile
- Loading, empty and error states on every page

Done when: the whole flow works in the browser against the local API.

### Phase 5 — Deploy (2 h)
- Backend Dockerfile; deploy API + Postgres (Render or Railway, or Neon for the database)
- Frontend on Vercel; set CORS and env vars; run migrations on deploy

Done when: the live site handles a pasted posting end to end.

### Phase 6 — README and eval (2 h)
- Run `python -m app.eval`, paste the results table into the README
- Write the failure teardown from a real `llm_calls` row
- Record a 60-second GIF; add screenshots

Done when: a stranger can understand the project from the README in two minutes.

**Cut list** if short on time, in this order: Profile page (seed from `.env`), Reprocess endpoint, status filter, GIF. Never cut the evidence check, the tests or the README.

## Working with Claude Code

`CLAUDE.md` at the repo root holds the rules; run one phase per session. Read every diff before accepting it.

### Prompts, one per phase

1. **Phase 0:** "Read docs/DESIGN.md. Do Phase 0 only: scaffold the repo structure, docker-compose with Postgres, a FastAPI app with GET /health, ruff, pytest, and a GitHub Actions workflow. Plan first."
2. **Phase 1:** "Do Phase 1. Write the unit tests from the Testing section first, show me they fail, then implement evidence.py, the normalizers and scoring.py until they pass. No LLM, no database."
3. **Phase 2:** "Do Phase 2. Implement the schema, llm/client.py, the extract_v1 prompt and pipeline/run.py with one retry that includes the validation error. Add FakeLLMClient pipeline tests and the guard test."
4. **Phase 3:** "Do Phase 3. Add SQLAlchemy models and an Alembic migration for the five tables, the routers, the error shape, the rate limit and llm_calls logging. Add API tests with a test database."
5. **Phase 4:** "Do Phase 4 in frontend/. Build lib/api.ts and the four pages from the Frontend section, with loading, empty and error states on every fetch."
6. **Phase 5:** "Help me deploy: a backend Dockerfile, migrations on start, CORS from env, and a step-by-step for Render/Neon and Vercel. Don't put secrets in the repo."
7. **Phase 6:** "Run app.eval on the fixtures and draft the README from the Deployment section. Leave the failure teardown for me to write; just pull the relevant llm_calls rows."

### Habits that pay off in the interview
- Use plan mode for each phase and edit the plan before it writes code.
- After each phase, ask "what could break here?" and write the answers into the README's Known limitations.
- Keep a `NOTES.md` of anything that took over 30 minutes to figure out.

## Deployment, README and demo

### Deployment checklist
- API on Render or Railway from the backend Dockerfile; `alembic upgrade head` runs on start
- Postgres on Render, Railway or Neon; `DATABASE_URL` set as a secret
- Frontend on Vercel with `NEXT_PUBLIC_API_URL`; API `ALLOWED_ORIGINS` set to the Vercel URL
- Rate limit and 50,000-character cap on; LLM key only in the host's secrets
- Seed two or three sample postings so the dashboard isn't empty for visitors

### README outline
1. One-line pitch, live link, 60-second GIF.
2. The rule: LLM as witness, code as judge, with the architecture diagram.
3. What happens to a posting: the pipeline diagram.
4. Failure teardown: the Kasparro notice. Its stipend says "Rs. 25,00" while the JD says ₹ 25,000. Show the raw model output, what the parser flagged, and why the app shows a conflict instead of picking one.
5. Decisions and trade-offs: synchronous pipeline, substring evidence check, rule-based score, lists for money mentions.
6. Eval results: the table from `app.eval`.
7. Known limitations, in plain words.
8. Run locally and run tests.

### Three-minute demo for the technical round
1. Paste the Kasparro notice live; show the flags and the highlighted evidence.
2. Open `llm_calls` for that posting: the raw response and what the code did with it.
3. Show the retry test and the guard test, and tell the story of why each exists.
4. Name one thing you'd change next and why.

## Risks and extensions

The biggest risk is scope, not tech: finish Phases 0–3 before touching the UI.

| Risk | What happens | Mitigation |
|---|---|---|
| Model quotes with small differences (extra spaces, curly quotes, a dropped word) | Good fields marked unverified | Normalize whitespace and quote characters only; count the rejection rate in the eval; tighten the prompt, never loosen the check to fuzzy matching without writing down why |
| Free-tier rate limits or outages | Posting fails | Status `needs_review` + Reprocess button; skip the LLM when the content hash already exists |
| Public demo burns your API credits | Surprise bill or blocked key | Rate limit, text length cap, spend limit on the provider dashboard |
| Dates without year or timezone | Wrong countdown | Flag `ambiguous` when the year is missing; store `tz_assumed` and show it |
| Scope creep | Nothing ships | Follow the cut list; a smaller finished project beats a bigger broken one |

**Extensions** (list in the README as "next", build only if time allows):
- Background processing with a job queue, with the UI polling for status.
- Run two models on the same posting and show where they disagree.
- Schema v2 with branches and graduation year, shipped as a new version file with a migration.
- Deadline reminders by email for postings marked as "applying".
- PDF upload for notices like the KIIT one, with text extracted before the pipeline runs.
