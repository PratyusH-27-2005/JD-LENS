// Every call to the backend lives here. Errors always arrive as ApiError, whether the API
// answered with its {"error": {...}} shape or couldn't be reached at all.

import type {
  Health,
  PostingDetail,
  PostingSummary,
  Profile,
  ProfileInput,
  Sort,
  Status,
  ValidationIssue,
} from "./types";

export const API_URL = (process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000").replace(
  /\/$/,
  "",
);

// Extraction takes 5–20 s; give the model its 30 s plus the retry some headroom.
const TIMEOUT_MS = 75_000;

export class ApiError extends Error {
  constructor(
    public status: number, // 0 = network error / timeout
    public code: string,
    message: string,
    public details?: unknown,
  ) {
    super(message);
    this.name = "ApiError";
  }

  get issues(): ValidationIssue[] {
    return this.code === "validation_error" && Array.isArray(this.details)
      ? (this.details as ValidationIssue[])
      : [];
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<{ status: number; body: T }> {
  let res: Response;
  try {
    res = await fetch(`${API_URL}${path}`, {
      ...init,
      headers: { "content-type": "application/json", ...init?.headers },
      signal: init?.signal ?? AbortSignal.timeout(TIMEOUT_MS),
    });
  } catch (e) {
    const timedOut = e instanceof DOMException && e.name === "TimeoutError";
    throw new ApiError(
      0,
      timedOut ? "timeout" : "network_error",
      timedOut
        ? "The API took too long to answer."
        : `Can't reach the API at ${API_URL}. Is the backend running?`,
    );
  }
  if (res.status === 204) return { status: 204, body: undefined as T };
  const body = await res.json().catch(() => null);
  if (!res.ok) {
    const err = body?.error;
    throw new ApiError(
      res.status,
      err?.code ?? "http_error",
      err?.message ?? `HTTP ${res.status}`,
      err?.details,
    );
  }
  return { status: res.status, body: body as T };
}

const get = async <T>(path: string) => (await request<T>(path)).body;

export const api = {
  health: () => get<Health>("/health"),

  listPostings: (opts: { sort?: Sort; status?: Status } = {}) => {
    const qs = new URLSearchParams();
    if (opts.sort) qs.set("sort", opts.sort);
    if (opts.status) qs.set("status", opts.status);
    return get<PostingSummary[]>(`/postings${qs.size ? `?${qs}` : ""}`);
  },

  getPosting: (id: string) => get<PostingDetail>(`/postings/${encodeURIComponent(id)}`),

  /** `duplicate` is true when the same text was already saved (HTTP 200, no LLM call). */
  createPosting: async (rawText: string, sourceLabel?: string) => {
    const { status, body } = await request<PostingDetail>("/postings", {
      method: "POST",
      body: JSON.stringify({ raw_text: rawText, source_label: sourceLabel || null }),
    });
    return { posting: body, duplicate: status === 200 };
  },

  reprocess: async (id: string) =>
    (
      await request<PostingDetail>(`/postings/${encodeURIComponent(id)}/reprocess`, {
        method: "POST",
      })
    ).body,

  deletePosting: async (id: string) => {
    await request<void>(`/postings/${encodeURIComponent(id)}`, { method: "DELETE" });
  },

  getProfile: () => get<Profile>("/profile"),

  putProfile: async (profile: ProfileInput) =>
    (await request<Profile>("/profile", { method: "PUT", body: JSON.stringify(profile) })).body,
};
