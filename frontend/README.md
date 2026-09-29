# JD Lens — web

Next.js (App Router, TypeScript, Tailwind). Talks to the FastAPI backend at `NEXT_PUBLIC_API_URL`
(default `http://localhost:8000`); every call is in `lib/api.ts`.

```bash
npm install
npm run dev     # http://localhost:3000 (start the API first: see the repo README)
npm run lint
npm run build
```

| Path | What |
|---|---|
| `app/page.tsx` + `components/Dashboard.tsx` | Postings table, sort by deadline/score, status filter |
| `app/new/page.tsx` | Paste a posting |
| `app/postings/[id]/page.tsx` + `components/PostingView.tsx` | Field cards, highlighted evidence, score breakdown |
| `app/profile/page.tsx` | Profile form; saving rescores every posting |
| `lib/highlight.ts` | Finds each quote in the text with the same folding as the backend's evidence check |
| `lib/useAsync.ts` | Loading / error / data state for every fetch |
