// Display helpers. Every number the UI shows comes from the backend's `normalized` data
// (parsed by code from a verified quote), never from the model's free-text value.

import type {
  CtcNorm,
  DeadlineNorm,
  EligibilityNorm,
  Field,
  FieldName,
  StipendNorm,
  WorkModeNorm,
} from "./types";

export const FIELD_LABELS: Record<FieldName, string> = {
  company: "Company",
  role_title: "Role",
  location: "Location",
  work_mode: "Work mode",
  stipend: "Stipend",
  ctc: "CTC",
  eligibility: "Eligibility",
  application_deadline: "Deadline",
  apply_instructions: "How to apply",
  required_skills: "Required skills",
};

const inr = new Intl.NumberFormat("en-IN", {
  style: "currency",
  currency: "INR",
  maximumFractionDigits: 0,
});

const trim = (n: number) => (Number.isInteger(n) ? String(n) : n.toFixed(2).replace(/0+$/, ""));

/** ₹25,000 below a lakh; ₹5 L / ₹1.2 Cr above. */
export function money(n: number): string {
  if (n >= 1_00_00_000) return `₹${trim(n / 1_00_00_000)} Cr`;
  if (n >= 1_00_000) return `₹${trim(n / 1_00_000)} L`;
  return inr.format(n);
}

export function moneyRange(min: number | null, max: number | null): string | null {
  if (min == null && max == null) return null;
  if (min == null || max == null || min === max) return money((min ?? max) as number);
  if (min >= 1_00_000 && max < 1_00_00_000) return `₹${trim(min / 1_00_000)}–${trim(max / 1_00_000)} L`;
  return `${money(min)}–${money(max)}`;
}

export function dateTime(iso: string): string {
  return new Date(iso).toLocaleString("en-IN", {
    day: "numeric",
    month: "short",
    year: "numeric",
    hour: "numeric",
    minute: "2-digit",
    timeZoneName: "short",
  });
}

export function shortDate(iso: string): string {
  return new Date(iso).toLocaleDateString("en-IN", { day: "numeric", month: "short", year: "numeric" });
}

export type Tone = "closed" | "urgent" | "normal";

export function countdown(iso: string, now: number): { label: string; tone: Tone } {
  const ms = new Date(iso).getTime() - now;
  if (ms <= 0) return { label: "Closed", tone: "closed" };
  const mins = Math.floor(ms / 60_000);
  const days = Math.floor(mins / 1440);
  const hours = Math.floor((mins % 1440) / 60);
  const label =
    days > 0 ? `${days}d ${hours}h left` : hours > 0 ? `${hours}h ${mins % 60}m left` : `${mins}m left`;
  return { label, tone: ms < 24 * 3_600_000 ? "urgent" : "normal" };
}

/** A readable line from a field's normalized data, or null if there's nothing parsed. */
export function describeNormalized(field: Field): string | null {
  const n = field.normalized;
  if (!n) return null;
  switch (field.field_name) {
    case "stipend": {
      const s = n as unknown as StipendNorm;
      return `${moneyRange(s.min_inr, s.max_inr)} per ${s.period}`;
    }
    case "ctc": {
      const c = n as unknown as CtcNorm;
      const parts = [];
      const cash = moneyRange(c.cash_min_inr, c.cash_max_inr);
      const total = moneyRange(c.total_min_inr, c.total_max_inr);
      const equity = c.has_equity ? " + equity" : "";
      if (cash) parts.push(`${cash} cash${equity}`);
      else if (equity) parts.push("Equity");
      if (total && total !== cash) parts.push(`${total} total`);
      return parts.join(" · ") + " per year";
    }
    case "application_deadline": {
      const d = n as unknown as DeadlineNorm;
      const notes = [d.tz_assumed && "IST assumed", d.time_assumed && "end of day assumed"].filter(Boolean);
      return dateTime(d.iso) + (notes.length ? ` (${notes.join(", ")})` : "");
    }
    case "eligibility": {
      const e = n as unknown as EligibilityNorm;
      const parts = [];
      if (e.cgpa_min != null) parts.push(`CGPA ≥ ${e.cgpa_min.toFixed(1)}`);
      if (e.backlogs_allowed === false) parts.push("no backlogs");
      if (e.backlogs_allowed === true) parts.push("backlogs allowed");
      return parts.join(" · ");
    }
    case "work_mode": {
      const w = n as unknown as WorkModeNorm;
      const mode = w.mode === "onsite" ? "On-site" : w.mode[0].toUpperCase() + w.mode.slice(1);
      return w.days_per_week ? `${mode} · ${w.days_per_week} days/week` : mode;
    }
    default:
      return null;
  }
}
