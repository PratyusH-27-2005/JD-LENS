import Link from "next/link";
import { EligibilityBadge, Pill } from "@/components/ui";
import { money } from "@/lib/format";
import type { PartName, Score, ScorePart } from "@/lib/types";

const LABELS: Record<PartName, string> = { skills: "Skills", location: "Location", pay: "Pay" };

export function ScoreBreakdown({ score }: { score: Score }) {
  const parts = (["skills", "location", "pay"] as const).map((n) => score.breakdown.parts[n]);
  const included = parts.filter((p) => p.included);
  const reasons = score.breakdown.eligibility.reasons;

  return (
    <div className="rounded-lg border border-stone-200 bg-white">
      <div className="flex flex-wrap items-start justify-between gap-6 border-b border-stone-100 p-5">
        <div>
          <h2 className="text-xs font-semibold uppercase tracking-wide text-stone-500">Fit score</h2>
          <p className="mt-1 flex items-baseline gap-2">
            <span className="text-4xl font-semibold tabular-nums text-stone-900">{score.score ?? "—"}</span>
            {score.score != null && <span className="text-stone-500">/ 100</span>}
          </p>
          <p className={`mt-1 text-sm ${included.length < 3 ? "text-amber-700" : "text-stone-500"}`}>
            {included.length === 0
              ? "Nothing verified to score yet."
              : included.length < 3
                ? `Based on ${included.map((p) => LABELS[p.name].toLowerCase()).join(" and ")} only: the other part had no verified data, so weights were rescaled.`
                : "Based on all three parts."}
          </p>
        </div>
        <div className="max-w-sm">
          <h2 className="text-xs font-semibold uppercase tracking-wide text-stone-500">Eligibility</h2>
          <div className="mt-2">
            <EligibilityBadge badge={score.badge} />
          </div>
          {reasons.length > 0 && (
            <ul className="mt-2 list-disc space-y-0.5 pl-4 text-sm text-stone-600">
              {reasons.map((r) => (
                <li key={r}>{r}</li>
              ))}
            </ul>
          )}
        </div>
      </div>

      <div className="grid gap-px bg-stone-100 sm:grid-cols-3">
        {parts.map((p) => (
          <PartTile key={p.name} part={p} />
        ))}
      </div>
      <p className="border-t border-stone-100 px-5 py-3 text-xs text-stone-500">
        Only verified, unflagged fields count. Change your skills, CGPA or preferences on the{" "}
        <Link href="/profile" className="underline hover:text-stone-900">
          profile page
        </Link>{" "}
        to rescore every posting.
      </p>
    </div>
  );
}

function PartTile({ part }: { part: ScorePart }) {
  const pct = part.included ? (part.points / part.weight) * 100 : 0;
  return (
    <div className="space-y-2 bg-white p-5">
      <div className="flex items-baseline justify-between">
        <h3 className="text-sm font-medium text-stone-900">{LABELS[part.name]}</h3>
        <span className="text-sm tabular-nums text-stone-600">
          {part.included ? `${Math.round(part.points * 10) / 10} / ${part.weight}` : `— / ${part.weight}`}
        </span>
      </div>
      <div className="h-1.5 overflow-hidden rounded-full bg-stone-100">
        <div className="h-full rounded-full bg-stone-800" style={{ width: `${pct}%` }} />
      </div>
      <p className={`text-xs ${part.included ? "text-stone-600" : "text-amber-700"}`}>
        {part.included ? part.note : `Left out: ${part.note}`}
      </p>
      <PartInputs part={part} />
    </div>
  );
}

function PartInputs({ part }: { part: ScorePart }) {
  const i = part.inputs;
  if (part.name === "skills" && part.included) {
    const matched = (i.matched as string[]) ?? [];
    const missing = (i.missing as string[]) ?? [];
    return (
      <div className="flex flex-wrap gap-1">
        {matched.map((s) => (
          <Pill key={s} tone="green">
            {s}
          </Pill>
        ))}
        {missing.map((s) => (
          <Pill key={s} tone="grey" title="Required, not in your profile">
            {s}
          </Pill>
        ))}
      </div>
    );
  }
  if (part.name === "pay" && part.included) {
    return (
      <p className="text-xs text-stone-500">
        Cash up to {money(i.cash_max_inr as number)} vs your minimum {money(i.min_cash_inr as number)}. Equity
        never counts as cash.
      </p>
    );
  }
  return null;
}
