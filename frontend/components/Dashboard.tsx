"use client";

import Link from "next/link";
import { usePathname, useRouter, useSearchParams } from "next/navigation";
import { Countdown } from "@/components/Countdown";
import {
  EligibilityBadge,
  EmptyState,
  ErrorState,
  PageHeader,
  Skeleton,
  Spinner,
  StatusBadge,
} from "@/components/ui";
import { api } from "@/lib/api";
import { moneyRange } from "@/lib/format";
import type { PostingSummary, Sort, Status } from "@/lib/types";
import { useAsync } from "@/lib/useAsync";

const STATUSES: { value: Status | ""; label: string }[] = [
  { value: "", label: "All statuses" },
  { value: "verified", label: "Verified" },
  { value: "partial", label: "Partial" },
  { value: "needs_review", label: "Needs review" },
];

export function Dashboard() {
  const params = useSearchParams();
  const router = useRouter();
  const pathname = usePathname();
  const sort: Sort = params.get("sort") === "score" ? "score" : "deadline";
  const status = (STATUSES.find((s) => s.value === params.get("status"))?.value || undefined) as
    | Status
    | undefined;

  const { data, error, loading, reload } = useAsync(
    () => api.listPostings({ sort, status }),
    `${sort}|${status ?? ""}`,
  );

  const setParam = (key: string, value: string) => {
    const next = new URLSearchParams(params);
    if (value) next.set(key, value);
    else next.delete(key);
    router.replace(`${pathname}${next.size ? `?${next}` : ""}`, { scroll: false });
  };

  const filtered = Boolean(status);

  return (
    <>
      <PageHeader
        title="Postings"
        subtitle="Only values backed by a quote from the posting are shown. Flagged values stay blank here; open a posting to see why."
        actions={
          <Link
            href="/new"
            className="rounded-md bg-stone-900 px-3.5 py-2 text-sm font-medium text-white hover:bg-stone-700"
          >
            Paste a posting
          </Link>
        }
      />

      <div className="mb-4 flex flex-wrap items-center gap-3 text-sm">
        <div role="group" aria-label="Sort by" className="inline-flex rounded-md bg-stone-200/60 p-0.5">
          {(["deadline", "score"] as const).map((s) => (
            <button
              key={s}
              onClick={() => setParam("sort", s === "deadline" ? "" : s)}
              aria-pressed={sort === s}
              className={`rounded px-3 py-1 ${sort === s ? "bg-white font-medium shadow-sm" : "text-stone-600 hover:text-stone-900"}`}
            >
              {s === "deadline" ? "By deadline" : "By score"}
            </button>
          ))}
        </div>
        <label className="sr-only" htmlFor="status-filter">
          Filter by status
        </label>
        <select
          id="status-filter"
          value={status ?? ""}
          onChange={(e) => setParam("status", e.target.value)}
          className="rounded-md border border-stone-300 bg-white px-2.5 py-1.5"
        >
          {STATUSES.map((s) => (
            <option key={s.value} value={s.value}>
              {s.label}
            </option>
          ))}
        </select>
        {loading && data && <Spinner className="text-stone-400" />}
      </div>

      {error ? (
        <ErrorState error={error} onRetry={reload} />
      ) : !data ? (
        <TableSkeleton />
      ) : data.length === 0 ? (
        filtered ? (
          <EmptyState title="No postings with this status">Try another filter.</EmptyState>
        ) : (
          <EmptyState title="Paste your first posting" action={{ href: "/new", label: "Paste a posting" }}>
            Drop in a job description or placement notice. JD Lens pulls out the facts, checks each one
            against the text, and scores it against your profile.
          </EmptyState>
        )
      ) : (
        <PostingTable rows={data} />
      )}
    </>
  );
}

function PostingTable({ rows }: { rows: PostingSummary[] }) {
  return (
    <div className="overflow-x-auto rounded-lg border border-stone-200 bg-white">
      <table className="w-full min-w-[760px] text-left text-sm">
        <thead className="border-b border-stone-200 bg-stone-50 text-xs uppercase tracking-wide text-stone-500">
          <tr>
            <th className="px-4 py-2.5 font-medium">Company / role</th>
            <th className="px-4 py-2.5 font-medium">Deadline</th>
            <th className="px-4 py-2.5 font-medium">Cash (yearly)</th>
            <th className="px-4 py-2.5 font-medium">Score</th>
            <th className="px-4 py-2.5 font-medium">Eligibility</th>
            <th className="px-4 py-2.5 font-medium">Status</th>
          </tr>
        </thead>
        <tbody className="divide-y divide-stone-100">
          {rows.map((p) => (
            <tr key={p.id} className="group relative hover:bg-stone-50">
              <td className="px-4 py-3">
                <Link href={`/postings/${p.id}`} className="after:absolute after:inset-0">
                  <span className="block font-medium text-stone-900 group-hover:underline">
                    {p.company ?? <span className="italic text-stone-400">Company not verified</span>}
                  </span>
                  <span className="block text-stone-600">{p.role_title ?? "—"}</span>
                </Link>
                {p.source_label && <span className="text-xs text-stone-400">{p.source_label}</span>}
              </td>
              <td className="px-4 py-3">{p.deadline ? <Countdown iso={p.deadline} /> : <Muted>Unknown</Muted>}</td>
              <td className="px-4 py-3 tabular-nums">
                {moneyRange(p.cash_min_inr, p.cash_max_inr) ?? <Muted>Unknown</Muted>}
              </td>
              <td className="px-4 py-3">
                <ScoreCell score={p.score} scoredOn={p.scored_on} />
              </td>
              <td className="px-4 py-3">
                <EligibilityBadge badge={p.badge} />
              </td>
              <td className="px-4 py-3">
                <StatusBadge status={p.status} />
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function ScoreCell({ score, scoredOn }: { score: number | null; scoredOn: string[] }) {
  if (score == null) return <Muted>—</Muted>;
  const partial = scoredOn.length < 3;
  return (
    <span className="flex flex-col leading-tight">
      <span className="text-base font-semibold tabular-nums text-stone-900">{score}</span>
      <span
        className={`text-xs ${partial ? "text-amber-700" : "text-stone-500"}`}
        title={`Based on: ${scoredOn.join(", ")}`}
      >
        {partial ? `on ${scoredOn.length} of 3 parts` : "all 3 parts"}
      </span>
    </span>
  );
}

function Muted({ children }: { children: React.ReactNode }) {
  return <span className="text-stone-400">{children}</span>;
}

function TableSkeleton() {
  return (
    <div className="space-y-px overflow-hidden rounded-lg border border-stone-200 bg-white" aria-busy>
      <div className="h-10 bg-stone-50" />
      {[0, 1, 2].map((i) => (
        <div key={i} className="flex items-center gap-6 px-4 py-4">
          <div className="flex-1 space-y-2">
            <Skeleton className="h-4 w-40" />
            <Skeleton className="h-3 w-56" />
          </div>
          <Skeleton className="h-4 w-24" />
          <Skeleton className="h-4 w-20" />
          <Skeleton className="h-4 w-10" />
          <Skeleton className="h-5 w-20 rounded-full" />
        </div>
      ))}
    </div>
  );
}

export function DashboardSkeleton() {
  return (
    <>
      <div className="mb-6 space-y-2">
        <Skeleton className="h-7 w-32" />
        <Skeleton className="h-4 w-96 max-w-full" />
      </div>
      <TableSkeleton />
    </>
  );
}
