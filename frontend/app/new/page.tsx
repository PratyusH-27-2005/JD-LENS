"use client";

import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { Button, PageHeader, Spinner } from "@/components/ui";
import { ApiError, api } from "@/lib/api";

const MIN = 200;
const MAX = 50_000;

export default function NewPostingPage() {
  const router = useRouter();
  const [text, setText] = useState("");
  const [label, setLabel] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [elapsed, setElapsed] = useState(0);
  const [error, setError] = useState<ApiError | null>(null);

  useEffect(() => {
    if (!submitting) return;
    const started = Date.now();
    const t = setInterval(() => setElapsed(Math.floor((Date.now() - started) / 1000)), 500);
    return () => clearInterval(t);
  }, [submitting]);

  const length = text.length;
  const tooShort = length > 0 && length < MIN;
  const tooLong = length > MAX;
  const valid = length >= MIN && !tooLong;

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!valid || submitting) return;
    setSubmitting(true);
    setElapsed(0);
    setError(null);
    try {
      const { posting, duplicate } = await api.createPosting(text, label.trim() || undefined);
      router.push(`/postings/${posting.id}${duplicate ? "?existing=1" : ""}`);
    } catch (err) {
      setError(err instanceof ApiError ? err : new ApiError(0, "unknown", String(err)));
      setSubmitting(false);
    }
  };

  return (
    <div className="max-w-3xl">
      <PageHeader
        title="Paste a posting"
        subtitle="A job description, placement notice or email. The model only quotes the text; code checks every quote, parses the numbers and scores the fit."
      />

      <form onSubmit={submit} className="space-y-4">
        <div>
          <label htmlFor="raw-text" className="mb-1.5 block text-sm font-medium text-stone-800">
            Posting text
          </label>
          <textarea
            id="raw-text"
            value={text}
            onChange={(e) => setText(e.target.value)}
            disabled={submitting}
            rows={16}
            placeholder="Paste the full posting here…"
            aria-invalid={Boolean(error?.issues.length) || tooLong}
            aria-describedby="raw-text-help"
            className="block w-full resize-y rounded-md border border-stone-300 bg-white p-3 font-mono text-sm leading-relaxed text-stone-900 placeholder:text-stone-400 focus:border-stone-500 focus:outline-none focus:ring-2 focus:ring-stone-200 disabled:bg-stone-50 disabled:text-stone-500"
          />
          <div id="raw-text-help" className="mt-1.5 flex justify-between gap-4 text-xs">
            <span className={tooShort || tooLong ? "text-rose-600" : "text-stone-500"}>
              {tooShort
                ? `At least ${MIN} characters: ${MIN - length} more to go.`
                : tooLong
                  ? `At most ${MAX.toLocaleString("en-IN")} characters.`
                  : "Between 200 and 50,000 characters."}
            </span>
            <span className={`tabular-nums ${tooShort || tooLong ? "text-rose-600" : "text-stone-500"}`}>
              {length.toLocaleString("en-IN")} / {MAX.toLocaleString("en-IN")}
            </span>
          </div>
        </div>

        <div>
          <label htmlFor="source-label" className="mb-1.5 block text-sm font-medium text-stone-800">
            Source <span className="font-normal text-stone-500">(optional)</span>
          </label>
          <input
            id="source-label"
            value={label}
            onChange={(e) => setLabel(e.target.value)}
            disabled={submitting}
            maxLength={200}
            placeholder="e.g. KIIT placement notice, LinkedIn, careers page"
            className="block w-full rounded-md border border-stone-300 bg-white px-3 py-2 text-sm focus:border-stone-500 focus:outline-none focus:ring-2 focus:ring-stone-200"
          />
        </div>

        {error && <SubmitError error={error} />}

        <div className="flex items-center gap-4">
          <Button type="submit" disabled={!valid || submitting}>
            {submitting && <Spinner />}
            {submitting ? "Extracting…" : "Extract and score"}
          </Button>
          {submitting && (
            <p className="text-sm text-stone-600" aria-live="polite">
              {elapsed}s · usually 5–20 s. The model reads, then code checks every quote.
            </p>
          )}
        </div>
      </form>
    </div>
  );
}

function SubmitError({ error }: { error: ApiError }) {
  let message = error.message;
  if (error.code === "rate_limited") {
    message = "You've submitted a lot of postings in the last minute. Wait a moment and try again.";
  } else if (error.issues.length) {
    message = error.issues.map((i) => i.msg).join(" ");
  } else if (error.code === "timeout") {
    message =
      "No answer after 75 s. The posting may still have been saved; check the dashboard before retrying.";
  }
  return (
    <p role="alert" className="rounded-md border border-rose-200 bg-rose-50 px-3 py-2 text-sm text-rose-800">
      {message}
    </p>
  );
}
