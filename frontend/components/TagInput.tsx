"use client";

import { useState } from "react";

/** Type and press Enter or comma to add; Backspace on an empty box removes the last tag. */
export function TagInput({
  id,
  value,
  onChange,
  placeholder,
}: {
  id: string;
  value: string[];
  onChange: (next: string[]) => void;
  placeholder?: string;
}) {
  const [draft, setDraft] = useState("");

  const add = (raw: string) => {
    const tags = raw
      .split(",")
      .map((t) => t.trim())
      .filter((t) => t && !value.some((v) => v.toLowerCase() === t.toLowerCase()));
    if (tags.length) onChange([...value, ...tags]);
    setDraft("");
  };

  return (
    <div className="flex flex-wrap items-center gap-1.5 rounded-md border border-stone-300 bg-white px-2 py-1.5 focus-within:border-stone-500 focus-within:ring-2 focus-within:ring-stone-200">
      {value.map((tag) => (
        <span
          key={tag}
          className="inline-flex items-center gap-1 rounded bg-stone-100 py-0.5 pl-2 pr-1 text-sm text-stone-800"
        >
          {tag}
          <button
            type="button"
            aria-label={`Remove ${tag}`}
            onClick={() => onChange(value.filter((t) => t !== tag))}
            className="rounded px-1 text-stone-500 hover:bg-stone-200 hover:text-stone-900"
          >
            ×
          </button>
        </span>
      ))}
      <input
        id={id}
        value={draft}
        placeholder={value.length ? "" : placeholder}
        onChange={(e) => (e.target.value.includes(",") ? add(e.target.value) : setDraft(e.target.value))}
        onKeyDown={(e) => {
          if (e.key === "Enter") {
            e.preventDefault();
            add(draft);
          } else if (e.key === "Backspace" && !draft && value.length) {
            onChange(value.slice(0, -1));
          }
        }}
        onBlur={() => draft && add(draft)}
        className="min-w-32 flex-1 border-0 bg-transparent py-1 text-sm outline-none placeholder:text-stone-400"
      />
    </div>
  );
}
