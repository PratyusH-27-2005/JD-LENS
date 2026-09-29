"use client";

import { useEffect, useState } from "react";
import { countdown, dateTime } from "@/lib/format";

/** Deadline countdown: red under 24 h, grey once closed. Ticks every 30 s. */
export function Countdown({ iso }: { iso: string }) {
  const [now, setNow] = useState(() => Date.now());
  useEffect(() => {
    const t = setInterval(() => setNow(Date.now()), 30_000);
    return () => clearInterval(t);
  }, []);

  const { label, tone } = countdown(iso, now);
  const color = {
    closed: "text-stone-400 line-through decoration-stone-300",
    urgent: "font-semibold text-rose-600",
    normal: "text-stone-800",
  }[tone];

  return (
    <span className="flex flex-col leading-tight" title={dateTime(iso)}>
      <span className={`text-sm ${color}`}>{label}</span>
      <span className="text-xs text-stone-500">{dateTime(iso)}</span>
    </span>
  );
}
