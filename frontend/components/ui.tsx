import Link from "next/link";
import type { ReactNode } from "react";
import type { ApiError } from "@/lib/api";
import type { Badge, Flag, Status } from "@/lib/types";

type Tone = "green" | "amber" | "red" | "grey" | "blue";

const TONES: Record<Tone, string> = {
  green: "bg-emerald-50 text-emerald-800 ring-emerald-600/20",
  amber: "bg-amber-50 text-amber-800 ring-amber-600/25",
  red: "bg-rose-50 text-rose-700 ring-rose-600/20",
  grey: "bg-stone-100 text-stone-600 ring-stone-500/20",
  blue: "bg-sky-50 text-sky-800 ring-sky-600/20",
};

export function Pill({ tone, children, title }: { tone: Tone; children: ReactNode; title?: string }) {
  return (
    <span
      title={title}
      className={`inline-flex items-center gap-1 whitespace-nowrap rounded-full px-2 py-0.5 text-xs font-medium ring-1 ring-inset ${TONES[tone]}`}
    >
      {children}
    </span>
  );
}

const STATUS: Record<Status, [Tone, string]> = {
  verified: ["green", "Verified"],
  partial: ["amber", "Partial"],
  needs_review: ["red", "Needs review"],
  pending: ["grey", "Pending"],
};

export function StatusBadge({ status, reason }: { status: Status; reason?: string | null }) {
  const [tone, label] = STATUS[status];
  return (
    <Pill tone={tone} title={reason ?? undefined}>
      {label}
    </Pill>
  );
}

const FLAG: Record<Flag, [Tone, string]> = {
  none: ["green", "✓ Verified"],
  ambiguous: ["red", "Ambiguous"],
  conflict: ["red", "Conflict"],
  unverified: ["red", "Not found in text"],
  missing: ["grey", "Not stated"],
};

export function FlagBadge({ flag }: { flag: Flag }) {
  const [tone, label] = FLAG[flag];
  return <Pill tone={tone}>{label}</Pill>;
}

const ELIGIBILITY: Record<Badge, [Tone, string]> = {
  eligible: ["green", "Eligible"],
  not_eligible: ["red", "Not eligible"],
  check_manually: ["amber", "Check manually"],
  closed: ["grey", "Closed"],
};

export function EligibilityBadge({ badge, title }: { badge: Badge; title?: string }) {
  const [tone, label] = ELIGIBILITY[badge];
  return (
    <Pill tone={tone} title={title}>
      {label}
    </Pill>
  );
}

export function Button({
  variant = "primary",
  className = "",
  ...props
}: React.ButtonHTMLAttributes<HTMLButtonElement> & { variant?: "primary" | "secondary" | "danger" }) {
  const styles = {
    primary: "bg-stone-900 text-white hover:bg-stone-700 disabled:bg-stone-400",
    secondary:
      "bg-white text-stone-800 ring-1 ring-inset ring-stone-300 hover:bg-stone-50 disabled:text-stone-400",
    danger: "bg-white text-rose-700 ring-1 ring-inset ring-rose-300 hover:bg-rose-50 disabled:text-rose-300",
  }[variant];
  return (
    <button
      {...props}
      className={`inline-flex items-center justify-center gap-2 rounded-md px-3.5 py-2 text-sm font-medium transition-colors disabled:cursor-not-allowed ${styles} ${className}`}
    />
  );
}

export function Spinner({ className = "" }: { className?: string }) {
  return (
    <span
      aria-hidden
      className={`inline-block size-4 animate-spin rounded-full border-2 border-current border-r-transparent ${className}`}
    />
  );
}

export function ErrorState({ error, onRetry }: { error: ApiError; onRetry?: () => void }) {
  const down = error.status === 0;
  return (
    <div role="alert" className="rounded-lg border border-rose-200 bg-rose-50 p-5 text-sm text-rose-900">
      <p className="font-semibold">{down ? "The API is unreachable" : "Something went wrong"}</p>
      <p className="mt-1 text-rose-800">{error.message}</p>
      {down && (
        <p className="mt-2 text-rose-800">
          Start it with <code className="rounded bg-rose-100 px-1">uvicorn app.main:app --reload</code>{" "}
          in <code className="rounded bg-rose-100 px-1">backend/</code>.
        </p>
      )}
      {onRetry && (
        <Button variant="secondary" className="mt-4" onClick={onRetry}>
          Try again
        </Button>
      )}
    </div>
  );
}

export function EmptyState({ title, children, action }: { title: string; children?: ReactNode; action?: { href: string; label: string } }) {
  return (
    <div className="rounded-lg border border-dashed border-stone-300 bg-white px-6 py-14 text-center">
      <p className="text-base font-semibold text-stone-900">{title}</p>
      {children && <div className="mx-auto mt-2 max-w-md text-sm text-stone-600">{children}</div>}
      {action && (
        <Link
          href={action.href}
          className="mt-5 inline-flex rounded-md bg-stone-900 px-3.5 py-2 text-sm font-medium text-white hover:bg-stone-700"
        >
          {action.label}
        </Link>
      )}
    </div>
  );
}

export function Skeleton({ className = "" }: { className?: string }) {
  return <div className={`animate-pulse rounded bg-stone-200/70 ${className}`} />;
}

export function PageHeader({ title, subtitle, actions }: { title: string; subtitle?: ReactNode; actions?: ReactNode }) {
  return (
    <div className="mb-6 flex flex-wrap items-end justify-between gap-4">
      <div>
        <h1 className="text-2xl font-semibold tracking-tight text-stone-900">{title}</h1>
        {subtitle && <p className="mt-1 text-sm text-stone-600">{subtitle}</p>}
      </div>
      {actions && <div className="flex flex-wrap items-center gap-2">{actions}</div>}
    </div>
  );
}
