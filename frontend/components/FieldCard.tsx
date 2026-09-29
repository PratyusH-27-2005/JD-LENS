"use client";

import { FlagBadge, Pill } from "@/components/ui";
import { FIELD_LABELS, describeNormalized } from "@/lib/format";
import type { Field, FieldName } from "@/lib/types";

export const fieldKey = (f: Field) => `${f.field_name}-${f.mention_index}`;

export function FieldCard({
  name,
  fields,
  active,
  located,
  onShow,
}: {
  name: FieldName;
  fields: Field[];
  active: string | null;
  located: Set<string>;
  onShow: (key: string) => void;
}) {
  if (name === "required_skills") return <SkillsCard fields={fields} active={active} onShow={onShow} />;

  return (
    <article className="rounded-lg border border-stone-200 bg-white">
      <h2 className="border-b border-stone-100 px-4 py-2 text-xs font-semibold uppercase tracking-wide text-stone-500">
        {FIELD_LABELS[name]}
        {fields.length > 1 && <span className="ml-1 font-normal normal-case">· {fields.length} mentions</span>}
      </h2>
      <div className="divide-y divide-stone-100">
        {fields.map((f) => (
          <Mention key={fieldKey(f)} field={f} active={active === fieldKey(f)} located={located.has(fieldKey(f))} onShow={onShow} />
        ))}
      </div>
    </article>
  );
}

function Mention({
  field,
  active,
  located,
  onShow,
}: {
  field: Field;
  active: boolean;
  located: boolean;
  onShow: (key: string) => void;
}) {
  const key = fieldKey(field);
  const parsed = describeNormalized(field);
  const bad = field.flag === "ambiguous" || field.flag === "conflict";

  if (field.flag === "missing") {
    return (
      <div id={`card-${key}`} className="flex items-center justify-between gap-3 px-4 py-3">
        <span className="text-sm text-stone-400">Not stated in the posting</span>
        <FlagBadge flag="missing" />
      </div>
    );
  }

  if (field.flag === "unverified") {
    return (
      <div id={`card-${key}`} className="space-y-1 bg-rose-50/60 px-4 py-3">
        <div className="flex items-center justify-between gap-3">
          <span className="text-sm font-medium text-rose-700">Value hidden</span>
          <FlagBadge flag="unverified" />
        </div>
        <p className="text-xs text-rose-700">
          {field.flag_reason ?? "The model's quote isn't in the posting."} Unverified values are never shown.
        </p>
      </div>
    );
  }

  return (
    <div
      id={`card-${key}`}
      className={`space-y-2 px-4 py-3 transition-colors ${active ? "bg-amber-50" : ""} ${bad ? "bg-rose-50/40" : ""}`}
    >
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0">
          {parsed && !bad ? (
            <>
              <p className="font-medium text-stone-900">{parsed}</p>
              <p className="mt-0.5 text-xs text-stone-500">As written: {field.value}</p>
            </>
          ) : (
            <p className={`whitespace-pre-line font-medium line-clamp-5 ${bad ? "text-rose-700" : "text-stone-900"}`}>
              {field.value}
            </p>
          )}
        </div>
        <FlagBadge flag={field.flag} />
      </div>

      {bad && field.flag_reason && (
        <p className="rounded bg-rose-100/70 px-2 py-1 text-xs text-rose-800">
          {field.flag === "conflict" ? "Mentions disagree: " : "Couldn't parse cleanly: "}
          {field.flag_reason.replace(/^mentions disagree: /, "")}
        </p>
      )}

      {field.evidence && (
        <button
          type="button"
          onClick={() => onShow(key)}
          disabled={!located}
          className="group block w-full rounded border-l-2 border-amber-300 bg-stone-50 px-2.5 py-1.5 text-left text-xs text-stone-600 hover:border-amber-500 hover:bg-amber-50 disabled:cursor-default"
          title={located ? "Show in posting" : undefined}
        >
          <span className="line-clamp-3 font-mono">“{field.evidence}”</span>
          {located && <span className="mt-0.5 block text-[11px] text-amber-700 group-hover:underline">Show in posting →</span>}
        </button>
      )}
    </div>
  );
}

function SkillsCard({ fields, active, onShow }: { fields: Field[]; active: string | null; onShow: (key: string) => void }) {
  const verified = fields.filter((f) => f.flag === "none");
  const hidden = fields.filter((f) => f.flag === "unverified").length;
  const missing = fields.every((f) => f.flag === "missing");

  return (
    <article className="rounded-lg border border-stone-200 bg-white">
      <h2 className="border-b border-stone-100 px-4 py-2 text-xs font-semibold uppercase tracking-wide text-stone-500">
        {FIELD_LABELS.required_skills}
      </h2>
      <div className="px-4 py-3">
        {missing ? (
          <div className="flex items-center justify-between gap-3">
            <span className="text-sm text-stone-400">No skills named in the posting</span>
            <FlagBadge flag="missing" />
          </div>
        ) : (
          <div className="flex flex-wrap gap-1.5">
            {verified.map((f) => (
              <button
                key={fieldKey(f)}
                id={`card-${fieldKey(f)}`}
                type="button"
                onClick={() => onShow(fieldKey(f))}
                title={`“${f.evidence}”`}
                className={`rounded-full px-2.5 py-0.5 text-sm ring-1 ring-inset transition-colors ${
                  active === fieldKey(f)
                    ? "bg-amber-100 ring-amber-400"
                    : "bg-emerald-50 text-emerald-900 ring-emerald-600/20 hover:bg-emerald-100"
                }`}
              >
                {f.value}
              </button>
            ))}
            {hidden > 0 && (
              <Pill tone="red" title="Their quotes weren't found in the posting, so they're hidden">
                {hidden} not found in text
              </Pill>
            )}
          </div>
        )}
      </div>
    </article>
  );
}
