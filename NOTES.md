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

## 2026-09-30 — the rate limit could be bypassed with one fake header (found on the live deploy)

- **Symptom:** none, which is the point. The limiter worked in tests and on Render: 10
  posts accepted, the 11th got 429.
- **How I found it:** asked "what does the limiter key on behind Render's proxy?". The
  Dockerfile ran uvicorn with `--proxy-headers --forwarded-allow-ips='*'`, so the client IP
  was the *leftmost* `X-Forwarded-For` entry, and the leftmost entry is whatever the client
  sends. Test on the live API: exhaust the limit, then send `X-Forwarded-For: 1.2.3.4` →
  200, `5.6.7.8` → 200, no header → 429. Anyone could reset their limit per request and
  burn the Gemini quota.
- **Why tests missed it:** the test client has no proxy in front, so the header path never
  ran. The bug only exists in the deployed topology.
- **Fix:** response headers (`Server: cloudflare`, `CF-RAY`) show Render's edge is
  Cloudflare, which sets `CF-Connecting-IP` to the real client address. The limiter keys on
  that when `TRUST_CF_CONNECTING_IP=true` (set in render.yaml), and never reads
  `X-Forwarded-For`; `--forwarded-allow-ips='*'` is gone. Unit tests pin the behaviour.
- **Live re-test after the deploy:** 11 duplicate posts, each with a *different* random fake
  `X-Forwarded-For`. Old code: `200 ×11` (every fake address got its own limit). New code:
  `200 ×10, 429`. With all-different fake addresses, the old code could never produce that
  429, so it proves the fix is what's serving.
- **Lesson:** "trust the proxy headers" is only safe when you know exactly which proxy
  wrote them. `'*'` means "trust anyone".
