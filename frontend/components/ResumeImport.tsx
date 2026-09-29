"use client";

import { useRef, useState } from "react";
import { Button, Pill, Spinner } from "@/components/ui";
import { ApiError, api } from "@/lib/api";
import type { ResumeImport as ResumeResult } from "@/lib/types";

const MAX_BYTES = 5 * 1024 * 1024;

/**
 * Upload a PDF resume and get suggestions for the form. The parent decides how to merge
 * them (add, don't replace); nothing is saved until the user clicks Save.
 */
export function ResumeImport({ onResult }: { onResult: (r: ResumeResult) => void }) {
  const input = useRef<HTMLInputElement>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const upload = async (file: File) => {
    setError(null);
    if (file.type && file.type !== "application/pdf") return setError("Choose a PDF file.");
    if (file.size > MAX_BYTES) return setError("The resume must be under 5 MB.");
    setBusy(true);
    try {
      onResult(await api.importResume(file));
    } catch (e) {
      const err = e as ApiError;
      setError(
        err.code === "rate_limited"
          ? "Too many uploads in a minute. Wait a moment and try again."
          : err.code === "llm_unavailable"
            ? "The model couldn't be reached. Try again in a minute."
            : `Couldn't read that resume: ${err.message}.`,
      );
    } finally {
      setBusy(false);
      if (input.current) input.current.value = ""; // allow re-uploading the same file
    }
  };

  return (
    <section
      aria-label="Import from resume"
      className="mb-6 rounded-lg border border-dashed border-stone-300 bg-white p-5"
    >
      <div className="flex flex-wrap items-center justify-between gap-4">
        <div className="max-w-md">
          <h2 className="text-sm font-semibold text-stone-900">Fill from your resume</h2>
          <p className="mt-1 text-xs text-stone-600">
            PDF, up to 5 MB. We suggest your name, CGPA and skills, each backed by a quote from the resume.
            Nothing is saved until you review and click Save.
          </p>
        </div>
        <input
          ref={input}
          type="file"
          accept="application/pdf,.pdf"
          className="sr-only"
          id="resume-file"
          onChange={(e) => e.target.files?.[0] && upload(e.target.files[0])}
        />
        <Button type="button" variant="secondary" disabled={busy} onClick={() => input.current?.click()}>
          {busy && <Spinner />}
          {busy ? "Reading resume… 5–20 s" : "Upload resume (PDF)"}
        </Button>
      </div>
      <p className="mt-3 rounded bg-stone-50 px-3 py-2 text-xs text-stone-500">
        <strong className="font-medium text-stone-700">Privacy:</strong> the resume&apos;s text is sent to Google
        Gemini to find these details. On Gemini&apos;s free tier Google may use it to improve its products. JD Lens
        doesn&apos;t store the file or its text.
      </p>
      {error && (
        <p role="alert" className="mt-3 text-sm text-rose-700">
          {error}
        </p>
      )}
    </section>
  );
}

/** What the import changed in the form, with the quotes behind it. */
export function ResumeReport({
  result,
  added,
  offers,
}: {
  result: ResumeResult;
  added: { skills: string[]; name: boolean; cgpa: boolean };
  offers: { label: string; current: string; suggested: string; evidence: string; accept: () => void }[];
}) {
  const nothing = !added.skills.length && !added.name && !added.cgpa && !offers.length;
  return (
    <div role="status" className="mb-6 space-y-3 rounded-lg border border-sky-200 bg-sky-50 p-4 text-sm text-sky-950">
      <p className="font-medium">
        {nothing
          ? "Your profile already has everything the resume says."
          : "From your resume (review below, then Save):"}
      </p>
      {(added.name || added.cgpa || added.skills.length > 0) && (
        <ul className="space-y-1">
          {added.name && result.name && <Quoted label={`Name: ${result.name.value}`} evidence={result.name.evidence} />}
          {added.cgpa && result.cgpa && (
            <Quoted label={`CGPA: ${result.cgpa.value}`} evidence={result.cgpa.evidence} />
          )}
          {added.skills.length > 0 && (
            <li>
              Added {added.skills.length} skill{added.skills.length > 1 ? "s" : ""}:{" "}
              <span className="inline-flex flex-wrap gap-1 align-middle">
                {added.skills.map((s) => (
                  <Pill key={s} tone="blue" title={`“${result.skills.find((x) => x.value === s)?.evidence}”`}>
                    {s}
                  </Pill>
                ))}
              </span>
            </li>
          )}
        </ul>
      )}
      {offers.map((o) => (
        <div key={o.label} className="flex flex-wrap items-center gap-2 rounded bg-white/70 px-3 py-2">
          <span>
            Resume says {o.label} <strong>{o.suggested}</strong> (you have {o.current}).
          </span>
          <span className="font-mono text-xs text-stone-500">“{o.evidence}”</span>
          <Button type="button" variant="secondary" className="!py-1" onClick={o.accept}>
            Use {o.suggested}
          </Button>
        </div>
      ))}
      {result.rejected.length > 0 && (
        <details className="text-xs text-sky-900">
          <summary className="cursor-pointer">
            {result.rejected.length} suggestion{result.rejected.length > 1 ? "s" : ""} dropped (quote didn&apos;t
            check out)
          </summary>
          <ul className="mt-1 list-disc pl-5">
            {result.rejected.map((r, i) => (
              <li key={i}>
                {r.field} “{r.value}”: {r.reason}
              </li>
            ))}
          </ul>
        </details>
      )}
    </div>
  );
}

function Quoted({ label, evidence }: { label: string; evidence: string }) {
  return (
    <li>
      {label} <span className="font-mono text-xs text-stone-500">“{evidence}”</span>
    </li>
  );
}
