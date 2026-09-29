"use client";

import { useState } from "react";
import { TagInput } from "@/components/TagInput";
import { Button, ErrorState, PageHeader, Skeleton, Spinner } from "@/components/ui";
import { ApiError, api } from "@/lib/api";
import { dateTime } from "@/lib/format";
import type { Profile, ProfileInput } from "@/lib/types";
import { useAsync } from "@/lib/useAsync";

export default function ProfilePage() {
  const { data, error, reload } = useAsync(() => api.getProfile(), "profile");

  return (
    <div className="max-w-2xl">
      <PageHeader
        title="Your profile"
        subtitle="Used for the fit score and the eligibility badge. Saving rescores every posting."
      />
      {error ? (
        <ErrorState error={error} onRetry={reload} />
      ) : !data ? (
        <FormSkeleton />
      ) : (
        <ProfileForm key={data.updated_at ?? "new"} initial={data} />
      )}
    </div>
  );
}

type Form = {
  name: string;
  skills: string[];
  cgpa: string;
  backlogs: "" | "yes" | "no";
  preferred_locations: string[];
  min_cash_lpa: string;
};

const toForm = (p: Profile): Form => ({
  name: p.name,
  skills: p.skills,
  cgpa: p.cgpa == null ? "" : String(p.cgpa),
  backlogs: p.has_backlogs == null ? "" : p.has_backlogs ? "yes" : "no",
  preferred_locations: p.preferred_locations,
  min_cash_lpa: p.min_cash_inr == null ? "" : String(p.min_cash_inr / 1_00_000),
});

function toInput(f: Form): ProfileInput {
  return {
    name: f.name.trim(),
    skills: f.skills,
    cgpa: f.cgpa.trim() === "" ? null : Number(f.cgpa),
    has_backlogs: f.backlogs === "" ? null : f.backlogs === "yes",
    preferred_locations: f.preferred_locations,
    min_cash_inr: f.min_cash_lpa.trim() === "" ? null : Math.round(Number(f.min_cash_lpa) * 1_00_000),
  };
}

/** Client-side checks mirror the API's (cgpa 0–10, cash ≥ 0); the API still has the last word. */
function validate(f: Form): Partial<Record<keyof ProfileInput, string>> {
  const errors: Partial<Record<keyof ProfileInput, string>> = {};
  const cgpa = Number(f.cgpa);
  if (f.cgpa.trim() && (Number.isNaN(cgpa) || cgpa < 0 || cgpa > 10)) errors.cgpa = "CGPA must be between 0 and 10.";
  const lpa = Number(f.min_cash_lpa);
  if (f.min_cash_lpa.trim() && (Number.isNaN(lpa) || lpa < 0)) errors.min_cash_inr = "Enter a positive number of lakhs.";
  return errors;
}

function ProfileForm({ initial }: { initial: Profile }) {
  const [form, setForm] = useState<Form>(() => toForm(initial));
  const [saved, setSaved] = useState<Profile>(initial);
  const [state, setState] = useState<"idle" | "saving" | "saved">("idle");
  const [serverError, setServerError] = useState<ApiError | null>(null);
  const [touched, setTouched] = useState(false);

  const errors = validate(form);
  const serverFieldErrors = Object.fromEntries(
    (serverError?.issues ?? []).map((i) => [String(i.loc[i.loc.length - 1]), i.msg]),
  ) as Partial<Record<keyof ProfileInput, string>>;
  const fieldError = (k: keyof ProfileInput) => (touched ? errors[k] : undefined) ?? serverFieldErrors[k];
  const dirty = JSON.stringify(toInput(form)) !== JSON.stringify(toInput(toForm(saved)));

  const update = <K extends keyof Form>(key: K, value: Form[K]) => {
    setForm((f) => ({ ...f, [key]: value }));
    setState("idle");
  };

  const save = async (e: React.FormEvent) => {
    e.preventDefault();
    setTouched(true);
    if (Object.keys(errors).length) return;
    setState("saving");
    setServerError(null);
    try {
      const next = await api.putProfile(toInput(form));
      setSaved(next);
      setForm(toForm(next));
      setState("saved");
    } catch (err) {
      setServerError(err as ApiError);
      setState("idle");
    }
  };

  return (
    <form onSubmit={save} className="space-y-5 rounded-lg border border-stone-200 bg-white p-6" noValidate>
      <Row label="Name" htmlFor="name">
        <input id="name" value={form.name} onChange={(e) => update("name", e.target.value)} className={input} />
      </Row>

      <Row
        label="Skills"
        htmlFor="skills"
        hint="Press Enter or comma after each. Matching ignores case and knows common aliases (postgres = PostgreSQL, nextjs = Next.js)."
      >
        <TagInput id="skills" value={form.skills} onChange={(v) => update("skills", v)} placeholder="Python, React, …" />
      </Row>

      <div className="grid gap-5 sm:grid-cols-2">
        <Row label="CGPA" htmlFor="cgpa" hint="On a 10-point scale." error={fieldError("cgpa")}>
          <input
            id="cgpa"
            inputMode="decimal"
            value={form.cgpa}
            onChange={(e) => update("cgpa", e.target.value)}
            placeholder="e.g. 8.1"
            aria-invalid={Boolean(fieldError("cgpa"))}
            className={input}
          />
        </Row>
        <Row label="Active backlogs" htmlFor="backlogs" hint="Unset means eligibility shows “Check manually”.">
          <select
            id="backlogs"
            value={form.backlogs}
            onChange={(e) => update("backlogs", e.target.value as Form["backlogs"])}
            className={input}
          >
            <option value="">Not set</option>
            <option value="no">No backlogs</option>
            <option value="yes">I have backlogs</option>
          </select>
        </Row>
      </div>

      <Row label="Preferred locations" htmlFor="locations" hint="Remote roles always count as a match. Bangalore = Bengaluru.">
        <TagInput
          id="locations"
          value={form.preferred_locations}
          onChange={(v) => update("preferred_locations", v)}
          placeholder="Bengaluru, Pune, …"
        />
      </Row>

      <Row
        label="Minimum cash (LPA)"
        htmlFor="min-cash"
        hint="Yearly cash in lakhs. Compared with the CTC's cash part; equity never counts."
        error={fieldError("min_cash_inr")}
      >
        <input
          id="min-cash"
          inputMode="decimal"
          value={form.min_cash_lpa}
          onChange={(e) => update("min_cash_lpa", e.target.value)}
          placeholder="e.g. 6"
          aria-invalid={Boolean(fieldError("min_cash_inr"))}
          className={input}
        />
      </Row>

      {serverError && !serverError.issues.length && (
        <p role="alert" className="rounded-md border border-rose-200 bg-rose-50 px-3 py-2 text-sm text-rose-800">
          {serverError.message}
        </p>
      )}

      <div className="flex items-center gap-4 border-t border-stone-100 pt-5">
        <Button type="submit" disabled={state === "saving" || !dirty}>
          {state === "saving" && <Spinner />}
          {state === "saving" ? "Saving and rescoring…" : "Save profile"}
        </Button>
        <span className="text-sm text-stone-500" aria-live="polite">
          {state === "saved"
            ? "✓ Saved. Every posting has been rescored."
            : dirty
              ? "Unsaved changes"
              : saved.updated_at
                ? `Last saved ${dateTime(saved.updated_at)}`
                : ""}
        </span>
      </div>
    </form>
  );
}

const input =
  "block w-full rounded-md border border-stone-300 bg-white px-3 py-2 text-sm focus:border-stone-500 focus:outline-none focus:ring-2 focus:ring-stone-200 aria-[invalid=true]:border-rose-400";

function Row({
  label,
  htmlFor,
  hint,
  error,
  children,
}: {
  label: string;
  htmlFor: string;
  hint?: string;
  error?: string;
  children: React.ReactNode;
}) {
  return (
    <div>
      <label htmlFor={htmlFor} className="mb-1.5 block text-sm font-medium text-stone-800">
        {label}
      </label>
      {children}
      {error ? (
        <p className="mt-1 text-xs text-rose-600">{error}</p>
      ) : (
        hint && <p className="mt-1 text-xs text-stone-500">{hint}</p>
      )}
    </div>
  );
}

function FormSkeleton() {
  return (
    <div className="space-y-5 rounded-lg border border-stone-200 bg-white p-6" aria-busy>
      {[0, 1, 2, 3, 4].map((i) => (
        <div key={i} className="space-y-2">
          <Skeleton className="h-4 w-28" />
          <Skeleton className="h-9 w-full" />
        </div>
      ))}
    </div>
  );
}
