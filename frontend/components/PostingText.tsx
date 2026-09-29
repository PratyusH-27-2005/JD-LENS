"use client";

import { Fragment, useMemo } from "react";
import { segments, type Span } from "@/lib/highlight";

/** The posting as stored, with every verified quote highlighted. */
export function PostingText({
  text,
  spans,
  flagged,
  active,
  flash,
  onSelect,
}: {
  text: string;
  spans: Span[];
  flagged: Set<string>;
  active: string | null;
  flash: { key: string | null; n: number };
  onSelect: (key: string) => void;
}) {
  const pieces = useMemo(() => segments(text.length, spans), [text, spans]);
  const firstPiece = useMemo(() => {
    // The first piece of each quote carries the id that "Show in posting" scrolls to.
    const seen = new Map<string, number>();
    pieces.forEach((p, i) => p.keys.forEach((k) => !seen.has(k) && seen.set(k, i)));
    return seen;
  }, [pieces]);

  return (
    <div className="rounded-lg border border-stone-200 bg-white">
      <div className="flex items-center justify-between border-b border-stone-100 px-4 py-2 text-xs text-stone-500">
        <span className="font-semibold uppercase tracking-wide">Posting</span>
        <span className="flex items-center gap-3">
          <Legend className="bg-amber-100" label="quoted" />
          <Legend className="bg-rose-100" label="flagged" />
        </span>
      </div>
      <div className="max-h-[75vh] overflow-auto px-4 py-3">
        <p className="whitespace-pre-wrap break-words font-mono text-[13px] leading-relaxed text-stone-800">
          {pieces.map((p, i) => {
            const chunk = text.slice(p.start, p.end);
            if (!p.keys.length) return <Fragment key={i}>{chunk}</Fragment>;
            const key = p.keys.includes(active ?? "") ? (active as string) : p.keys[0];
            const isActive = p.keys.includes(active ?? "");
            const isFlagged = p.keys.some((k) => flagged.has(k));
            const anchor = p.keys.find((k) => firstPiece.get(k) === i);
            const flashing = flash.key !== null && p.keys.includes(flash.key);
            return (
              <mark
                key={flashing ? `${i}-${flash.n}` : i}
                id={anchor ? `ev-${anchor}` : undefined}
                onClick={() => onSelect(key)}
                className={`cursor-pointer rounded-sm px-px text-inherit transition-colors ${flashing ? "evidence-flash " : ""}${
                  isActive
                    ? "bg-amber-300 ring-1 ring-amber-500"
                    : isFlagged
                      ? "bg-rose-100 hover:bg-rose-200"
                      : "bg-amber-100 hover:bg-amber-200"
                }`}
              >
                {chunk}
              </mark>
            );
          })}
        </p>
      </div>
    </div>
  );
}

function Legend({ className, label }: { className: string; label: string }) {
  return (
    <span className="flex items-center gap-1">
      <span className={`inline-block size-2.5 rounded-sm ${className}`} />
      {label}
    </span>
  );
}
