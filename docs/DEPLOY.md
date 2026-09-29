# Deploying JD Lens

API on **Render** (Docker, Singapore), database on **Neon** (Singapore), web app on
**Vercel**. All free tiers. No secret is ever committed: they live in each host's
dashboard.

```
Browser ──► Vercel (Next.js) ──► Render (FastAPI, Docker) ──► Neon (Postgres 16)
                                         └──► Gemini API
```

## 0. Before you start

- **Rotate the Gemini key** if it was ever pasted anywhere (chat, a committed file).
  Google AI Studio → API keys → create a new key, delete the old one. Put the new one in
  your local `.env` and, below, in Render.
- Push the repo to GitHub (Render and Vercel deploy from it).

## 1. Database: Neon

Already set up for local development. For the deploy you need its **direct** (not pooled)
connection string: Neon console → your project → **Connect** → Connection pooling **off**
→ copy the `postgresql://…?sslmode=require&channel_binding=require` string. Paste it as-is;
the app converts it for the async driver.

The API runs `alembic upgrade head` on every start, so there's no separate migration step.

> The deployed app and your local dev both use this database, so the public demo shows
> your real postings and profile. To keep them apart, create a Neon branch (e.g. `dev`)
> for local use and point your local `.env` at it.

## 2. API: Render

1. Render dashboard → **New** → **Blueprint** → connect GitHub → pick the repo.
   Render reads `render.yaml` and proposes the `jd-lens-api` service (Docker, Singapore,
   free plan, health check `/health`).
2. Fill in the three secrets it asks for:

   | Key | Value |
   |---|---|
   | `DATABASE_URL` | the Neon string from step 1 |
   | `LLM_API_KEY` | your Gemini key |
   | `ALLOWED_ORIGINS` | `http://localhost:3000` for now; the Vercel URL after step 3 |

3. **Apply**. The first build takes a few minutes. When it's live, open
   `https://<your-service>.onrender.com/health` → `{"db":"ok","llm_configured":true}`.

## 3. Web: Vercel

1. Vercel → **Add New… → Project** → import the repo.
2. **Root Directory: `frontend`**. Framework preset: Next.js (auto-detected).
3. Environment variable: `NEXT_PUBLIC_API_URL` = `https://<your-service>.onrender.com`
   (no trailing slash). It's baked in at build time, so changing it later means a redeploy.
4. **Deploy**. Note the production URL, e.g. `https://jd-lens.vercel.app`.

## 4. Connect them (CORS)

Back in Render → the service → **Environment**:

- `ALLOWED_ORIGINS` = `https://jd-lens.vercel.app` (your exact production URL; add
  `,http://localhost:3000` if you also want local dev against the deployed API)
- Optional, for Vercel preview deployments: `ALLOWED_ORIGIN_REGEX` =
  `https://jd-lens(-[\w-]+)?\.vercel\.app`

Save; Render redeploys. Open the Vercel URL: the dashboard should list your postings.

## 5. Check

- [ ] `/health` on Render → `db: ok`, `llm_configured: true`
- [ ] Vercel dashboard loads postings (no "API is unreachable")
- [ ] Paste a posting → detail page with highlighted quotes
- [ ] Profile saves and rescores
- [ ] 11 quick posts in a minute → the 11th says "rate limited"

## Free-tier behaviour to expect

- **Render sleeps after 15 minutes idle.** The first request after that takes ~30–60 s
  while the container starts (the dashboard shows its loading state; the web app waits
  up to 75 s). Open the site a minute before a demo.
- **Neon scales to zero** too; its wake-up adds 1–3 s to the first query.
- **Gemini free tier** has per-minute and per-day request limits. Over the limit, postings
  are saved as `needs_review` / `llm_unavailable` and can be reprocessed later. The
  API's own limit (10 postings and 5 resumes per minute per IP) keeps visitors from
  burning through it.
- There is **no login**: anyone with the URL can add postings and edit the single profile.
  That's the documented v1 trade-off (see README, Known limitations).
