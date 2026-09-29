# Failure teardown: raw material

Source material for the README's failure teardown (Manav writes the teardown itself).
Everything here is real output, not reconstructed.

## 1. The deployed Kasparro posting (from Neon)

Full rows: [teardown-kasparro-llm-calls.json](teardown-kasparro-llm-calls.json).

`llm_calls` for posting `46c8e9de-…` (created 2026-09-29 21:07 UTC via the API):

| id | attempt | parse_ok | latency | tokens in → out | error |
|---|---|---|---|---|---|
| 1 | 1 | true | 6,498 ms | 984 → 711 | none |

What the code did with the money fields (`extracted_fields`):

| field | model's quote (verified in text) | flag | reason | normalized |
|---|---|---|---|---|
| stipend[0] | `Stipend : Rs. 25,00 Per Month` | **ambiguous** | `"25,00" is not a valid digit grouping` | **null** |
| ctc[0] | `CTC : Rs. 5.00 –Rs. 8.00 LPA cash, plus an ESOP grant of matching value. Total Rs. 10.00–Rs. 16.00 LPA` | none | | cash ₹5–8 L, total ₹10–16 L, has_equity |

Posting status: `partial`, reason `flagged: stipend (ambiguous)`.

Note: the notice alone has no "₹ 25,000", so this is an *ambiguous* flag, not the
*conflict* the design anticipated (that needs the separate JD text). The conflict path is
covered by `reconcile()` and its tests (`test_reconcile_invalid_vs_valid_is_conflict…`).

## 2. The first-ever real run (Phase 2 CLI, before the database existed)

`python -m app.cli tests/fixtures/postings/kasparro.txt --raw`, gemini-2.5-flash, the
first draft of `extract_v1`. Not in `llm_calls` (no database yet); captured from the
terminal at the time and summarised in NOTES.md.

- **Attempt 1: rejected by the validator.** 912 → 699 tokens, 8,446 ms.
  Error fed back into the retry prompt: `work_mode: Input should be an object`.
  The relevant parts of the raw response:

  ```json
  "work_mode": null,
  "stipend": [
    {"value": "Rs. 25,00 Per Month", "evidence": "Stipend : Rs. 25,00 Per Month"}
  ],
  "ctc": [
    {"value": "Rs. 5.00 –Rs. 8.00 LPA cash", "evidence": "Rs. 5.00 –Rs. 8.00 LPA cash"},
    {"value": "Total Rs. 10.00–Rs. 16.00 LPA", "evidence": "Total Rs. 10.00–Rs. 16.00 LPA"}
  ],
  ```

- **Attempt 2: valid.** 945 → 716 tokens, 12,213 ms. `work_mode` became
  `{"value": null, "evidence": null}` and the CTC came back as one mention.

**The near miss:** had attempt 1 passed validation, its CTC split would have been parsed
as two separate CTCs: "5–8 LPA cash" (no ESOP word in that half, so total = cash) and
"Total 10–16 LPA". `reconcile()` would then have shown a **conflict** between ₹5–8 L and
₹10–16 L that isn't in the posting. It was avoided only because the same answer failed
validation for an unrelated reason. Fix: `extract_v1` now says one compensation statement
is one mention, and never a bare `null` for an object field. Since then: 0 retries and
no split CTC in 9 eval runs (docs/eval.md), and `tests/pipeline/test_eval.py` checks that
the eval would catch a split CTC.

## 3. Questions a teardown usually answers

- What did the model return (quote it), and what did the code conclude? (sections 1, 2)
- Why show "ambiguous" instead of picking 25,000? (the code can't know whether `25,00`
  means 2,500 or 25,000; the design's rule is to flag, not guess)
- What would have gone wrong without the check? (the near miss above)
- What changed afterwards, and how do you know it worked? (prompt fix + eval numbers)
