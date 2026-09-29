"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useMemo, useState } from "react";
import { FieldCard, fieldKey } from "@/components/FieldCard";
import { PostingText } from "@/components/PostingText";
import { ScoreBreakdown } from "@/components/ScoreBreakdown";
import {
  Button,
  EmptyState,
  ErrorState,
  PageHeader,
  Skeleton,
  Spinner,
  StatusBadge,
} from "@/components/ui";
import { ApiError, api } from "@/lib/api";
import { dateTime } from "@/lib/format";
import { findSpan, type Span } from "@/lib/highlight";
import type { Field, FieldName, PostingDetail } from "@/lib/types";
import { useAsync } from "@/lib/useAsync";

const ORDER: FieldName[] = [
  "company",
  "role_title",
  "location",
  "work_mode",
  "stipend",
  "ctc",
  "eligibility",
  "application_deadline",
  "apply_instructions",
  "required_skills",
];

export function PostingView({ id, existing }: { id: string; existing: boolean }) {
  const { data, error, reload, setData } = useAsync(() => api.getPosting(id), id);

  if (error?.status === 404) {
    return (
      <EmptyState title="Posting not found" action={{ href: "/", label: "Back to dashboard" }}>
        It may have been deleted.
      </EmptyState>
    );
  }
  if (error) return <ErrorState error={error} onRetry={reload} />;
  if (!data) return <DetailSkeleton />;
  return <Detail posting={data} existing={existing} onChange={setData} />;
}

function Detail({
  posting,
  existing,
  onChange,
}: {
  posting: PostingDetail;
  existing: boolean;
  onChange: (p: PostingDetail) => void;
}) {
  const router = useRouter();
  const [active, setActive] = useState<string | null>(null);
  const [flash, setFlash] = useState<{ key: string | null; n: number }>({ key: null, n: 0 });
  const [busy, setBusy] = useState<"reprocess" | "delete" | null>(null);
  const [actionError, setActionError] = useState<ApiError | null>(null);

  const groups = useMemo(() => {
    const by = new Map<FieldName, Field[]>();
    for (const f of posting.fields) by.set(f.field_name, [...(by.get(f.field_name) ?? []), f]);
    return ORDER.filter((name) => by.has(name)).map((name) => ({ name, fields: by.get(name)! }));
  }, [posting.fields]);

  const spans = useMemo<Span[]>(
    () =>
      posting.fields.flatMap((f) => {
        const span = f.evidence ? findSpan(posting.clean_text, f.evidence) : null;
        return span ? [{ key: fieldKey(f), start: span[0], end: span[1] }] : [];
      }),
    [posting],
  );
  const flagged = useMemo(
    () => new Set(posting.fields.filter((f) => f.flag === "ambiguous" || f.flag === "conflict").map(fieldKey)),
    [posting.fields],
  );

  const showInText = (key: string) => {
    setActive(key);
    setFlash((f) => ({ key, n: f.n + 1 })); // a new n remounts the mark, restarting the flash
    document.getElementById(`ev-${key}`)?.scrollIntoView({ behavior: "smooth", block: "center" });
  };

  const showCard = (key: string) => {
    setActive(key);
    document.getElementById(`card-${key}`)?.scrollIntoView({ behavior: "smooth", block: "nearest" });
  };

  const reprocess = async () => {
    setBusy("reprocess");
    setActionError(null);
    try {
      onChange(await api.reprocess(posting.id));
    } catch (e) {
      setActionError(e as ApiError);
    } finally {
      setBusy(null);
    }
  };

  const remove = async () => {
    if (!window.confirm("Delete this posting and everything extracted from it?")) return;
    setBusy("delete");
    setActionError(null);
    try {
      await api.deletePosting(posting.id);
      router.push("/");
    } catch (e) {
      setActionError(e as ApiError);
      setBusy(null);
    }
  };

  const company = posting.fields.find((f) => f.field_name === "company")?.value;
  const role = posting.fields.find((f) => f.field_name === "role_title")?.value;

  return (
    <>
      <Link href="/" className="mb-3 inline-block text-sm text-stone-500 hover:text-stone-900">
        ← All postings
      </Link>
      <PageHeader
        title={company && role ? `${role} · ${company}` : (company ?? role ?? "Untitled posting")}
        subtitle={
          <span className="flex flex-wrap items-center gap-x-2 gap-y-1">
            <StatusBadge status={posting.status} />
            {posting.source_label && <span>{posting.source_label} ·</span>}
            <span>Added {dateTime(posting.created_at)}</span>
            {posting.model_name && (
              <span className="text-stone-400">
                · {posting.model_name} · {posting.prompt_version} · schema {posting.schema_version}
              </span>
            )}
          </span>
        }
        actions={
          <>
            <Button variant="secondary" onClick={reprocess} disabled={busy !== null}>
              {busy === "reprocess" && <Spinner />}
              {busy === "reprocess" ? "Re-extracting… 5–20 s" : "Reprocess"}
            </Button>
            <Button variant="danger" onClick={remove} disabled={busy !== null}>
              {busy === "delete" && <Spinner />}
              Delete
            </Button>
          </>
        }
      />

      {existing && (
        <Banner tone="blue">You&apos;d already saved this posting, so here it is. The model wasn&apos;t called again.</Banner>
      )}
      <StatusBanner posting={posting} />
      {actionError && (
        <Banner tone="red">
          {actionError.message}
          {actionError.code === "timeout" && " Refresh in a moment to see whether it finished."}
        </Banner>
      )}

      <div className="grid gap-6 lg:grid-cols-[minmax(0,1fr)_minmax(0,1fr)]">
        <section aria-label="Extracted fields" className="space-y-3">
          {groups.length === 0 ? (
            <EmptyState title="Nothing extracted">
              The model&apos;s answer couldn&apos;t be used, so no values are shown. Reprocess to try again.
            </EmptyState>
          ) : (
            groups.map((g) => (
              <FieldCard
                key={g.name}
                name={g.name}
                fields={g.fields}
                active={active}
                located={new Set(spans.map((s) => s.key))}
                onShow={showInText}
              />
            ))
          )}
        </section>

        <section aria-label="Posting text" className="lg:sticky lg:top-4 lg:self-start">
          <PostingText
            text={posting.clean_text}
            spans={spans}
            flagged={flagged}
            active={active}
            flash={flash}
            onSelect={showCard}
          />
        </section>
      </div>

      {posting.score && (
        <section aria-label="Fit score" className="mt-8">
          <ScoreBreakdown score={posting.score} />
        </section>
      )}
    </>
  );
}

function StatusBanner({ posting }: { posting: PostingDetail }) {
  if (posting.status === "needs_review") {
    const reason = posting.status_reason ?? "";
    const text = reason.startsWith("llm_unavailable")
      ? "The model couldn't be reached (timeout, quota or outage). The posting is saved; press Reprocess to try again."
      : reason.startsWith("extraction_invalid")
        ? `The model's answer failed validation twice, so nothing from it is shown. ${reason}`
        : `Company or role couldn't be verified against the text (${reason}). Treat the values below with care.`;
    return (
      <Banner tone="red">
        <strong className="font-semibold">Needs review.</strong> {text}
      </Banner>
    );
  }
  if (posting.status === "partial") {
    return (
      <Banner tone="amber">
        <strong className="font-semibold">
          Some values are flagged: {(posting.status_reason ?? "").replace(/^flagged: /, "")}.
        </strong>{" "}
        They&apos;re shown in red with the reason, and aren&apos;t used in the score.
      </Banner>
    );
  }
  return null;
}

function Banner({ tone, children }: { tone: "red" | "amber" | "blue"; children: React.ReactNode }) {
  const styles = {
    red: "border-rose-200 bg-rose-50 text-rose-900",
    amber: "border-amber-200 bg-amber-50 text-amber-900",
    blue: "border-sky-200 bg-sky-50 text-sky-900",
  }[tone];
  return (
    <div role={tone === "red" ? "alert" : "status"} className={`mb-4 rounded-lg border px-4 py-3 text-sm ${styles}`}>
      {children}
    </div>
  );
}

function DetailSkeleton() {
  return (
    <div aria-busy>
      <Skeleton className="mb-3 h-4 w-24" />
      <Skeleton className="mb-2 h-7 w-80 max-w-full" />
      <Skeleton className="mb-6 h-4 w-64" />
      <div className="grid gap-6 lg:grid-cols-2">
        <div className="space-y-3">
          {[0, 1, 2, 3].map((i) => (
            <Skeleton key={i} className="h-24 w-full" />
          ))}
        </div>
        <Skeleton className="h-96 w-full" />
      </div>
    </div>
  );
}
