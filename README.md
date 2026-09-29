# JD Lens

Paste a job posting, get verified fields and a fit score. Every value shown is traced back to an exact quote from the posting — **LLM as witness, code as judge.**

> Work in progress. See [docs/DESIGN.md](docs/DESIGN.md) for the design and build plan.

## Run locally

```bash
cp .env.example .env            # fill in LLM_API_KEY
docker compose up -d db
cd backend
pip install -e ".[dev]"
uvicorn app.main:app --reload   # http://localhost:8000/health
```

## Tests

```bash
cd backend
ruff check .
pytest -q
```

## Known limitations

**Evidence check**
- Strict by design: only whitespace, curly quotes and dash characters are folded. A model that changes case, drops a word, or adds/removes a space *inside* a token (`Rs.25,00` vs `Rs. 25,00`) gets the field marked unverified. We'd rather lose a good field than show a paraphrase.

**Money**
- Rupees only; `$`, `USD` etc. are not recognised as currency.
- A stipend with two separate amounts ("₹20k for 3 months, then ₹25k") is flagged ambiguous, not modelled as a schedule.
- CTC with no period is assumed yearly (CTC is annual by definition); a monthly CTC is multiplied by 12.
- Cash vs total is decided by the word "total"/"overall" before an amount. Other phrasings ("fixed", "variable", "in-hand") aren't distinguished.
- Equity is detected by keyword (ESOP, equity, stock, RSU) only; its value is never parsed.

**Dates**
- No timezone → IST assumed (`tz_assumed: true`); no time → 23:59:59 assumed (`time_assumed: true`). Both are stored so the UI can say so.
- Numeric dates are read as DD/MM only when that's forced (day > 12); `05/10/2026` is flagged ambiguous.
- "Midnight" is flagged ambiguous; relative deadlines ("within 7 days") aren't parsed.
- Only IST, UTC and GMT are recognised as timezones.

**Eligibility and scoring**
- CGPA on a 10-point scale only; percentage cutoffs ("60% throughout") are not converted, so eligibility becomes "Check manually".
- "CGPA > 7" is treated as a minimum of 7 (strict vs non-strict inequality is not kept).
- Branch and graduation-year rules aren't checked yet (schema v2 extension).
- An unknown deadline doesn't block eligibility; the posting just can't be shown as Closed.
- Pay score uses CTC cash only. Internship-only postings with just a stipend get no pay score (the part is left out and weights rescale).
- Skill and city matching use small hand-written alias maps; anything not in them must match exactly (case-insensitive).
- "Virtual" is deliberately not read as remote: in placement notices it usually describes the recruitment drive, not the job.
