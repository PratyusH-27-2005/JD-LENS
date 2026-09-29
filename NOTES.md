# Notes

Anything that took over 30 minutes to figure out — raw material for the "hardest bug" story.

## 2026-09-30 — first real run on the Kasparro notice (gemini-2.5-flash, extract_v1 draft)

- **Attempt 1 failed validation**: `work_mode: Input should be an object`. The model wrote
  `"work_mode": null` instead of `{"value": null, "evidence": null}`. The retry (error fed back
  into the prompt) fixed it: attempt 2 parsed. 912→699 tokens, 8.4 s; then 945→716, 12.2 s.
- **Near miss — false conflict**: attempt 1 also split the CTC into two mentions,
  `"Rs. 5.00 –Rs. 8.00 LPA cash"` and `"Total Rs. 10.00–Rs. 16.00 LPA"`. Parsed separately,
  each looks like a whole CTC (no ESOP word in either half, so total = cash), and `reconcile`
  would have flagged 5–8 L vs 10–16 L as a conflict. It didn't happen only because attempt 1
  was rejected for the other reason. Fix: prompt now says one compensation statement = one
  mention, and bare `null` is never allowed for object fields.
- Final (attempt 2): stipend ambiguous (`"25,00" is not a valid digit grouping`), CTC cash
  5–8 L / total 10–16 L / ESOP, deadline 2026-09-30T09:00+05:30 (tz assumed), CGPA ≥ 6.0,
  no backlogs. Status `partial`.
