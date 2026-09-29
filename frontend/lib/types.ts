// Mirrors backend/app/schemas/api.py. Keep the two in sync.

export type Status = "pending" | "verified" | "partial" | "needs_review";
export type Flag = "none" | "ambiguous" | "conflict" | "unverified" | "missing";
export type Badge = "eligible" | "not_eligible" | "check_manually" | "closed";
export type Sort = "deadline" | "score";

export type FieldName =
  | "company"
  | "role_title"
  | "location"
  | "work_mode"
  | "stipend"
  | "ctc"
  | "eligibility"
  | "application_deadline"
  | "apply_instructions"
  | "required_skills";

// Shapes written by the backend normalizers into `normalized`.
export interface StipendNorm {
  period: "month" | "year";
  min_inr: number;
  max_inr: number;
}
export interface CtcNorm {
  cash_min_inr: number | null;
  cash_max_inr: number | null;
  total_min_inr: number | null;
  total_max_inr: number | null;
  has_equity: boolean;
}
export interface DeadlineNorm {
  iso: string;
  tz_assumed: boolean;
  time_assumed: boolean;
}
export interface EligibilityNorm {
  cgpa_min: number | null;
  backlogs_allowed: boolean | null;
}
export interface WorkModeNorm {
  mode: "onsite" | "remote" | "hybrid";
  days_per_week: number | null;
}

export interface Field {
  field_name: FieldName;
  mention_index: number;
  /** null unless the evidence was found in the posting */
  value: string | null;
  /** null unless it was found in the posting */
  evidence: string | null;
  evidence_verified: boolean;
  normalized: Record<string, unknown> | null;
  flag: Flag;
  flag_reason: string | null;
}

export type PartName = "skills" | "location" | "pay";

export interface ScorePart {
  name: PartName;
  weight: number;
  included: boolean;
  points: number;
  inputs: Record<string, unknown>;
  note: string;
}

export interface Breakdown {
  score: number | null;
  parts: Record<PartName, ScorePart>;
  eligibility: { status: Badge; eligible: boolean | null; reasons: string[] };
}

export interface Score {
  score: number | null;
  eligible: boolean | null;
  badge: Badge;
  breakdown: Breakdown;
  computed_at: string;
}

export interface PostingDetail {
  id: string;
  status: Status;
  status_reason: string | null;
  source_label: string | null;
  raw_text: string;
  clean_text: string;
  schema_version: string | null;
  prompt_version: string | null;
  model_name: string | null;
  created_at: string;
  processed_at: string | null;
  fields: Field[];
  score: Score | null;
}

export interface PostingSummary {
  id: string;
  status: Status;
  source_label: string | null;
  company: string | null;
  role_title: string | null;
  deadline: string | null;
  cash_min_inr: number | null;
  cash_max_inr: number | null;
  score: number | null;
  scored_on: PartName[];
  eligible: boolean | null;
  badge: Badge;
  created_at: string;
}

export interface ProfileInput {
  name: string;
  skills: string[];
  cgpa: number | null;
  has_backlogs: boolean | null;
  preferred_locations: string[];
  min_cash_inr: number | null;
}

export interface Profile extends ProfileInput {
  updated_at: string | null;
}

export interface Health {
  db: "ok" | "error";
  llm_configured: boolean;
}

export interface ValidationIssue {
  loc: (string | number)[];
  msg: string;
  type: string;
}
