// Locates evidence quotes inside the posting text for highlighting.
//
// Uses the same folding as backend/app/pipeline/evidence.py (curly quotes and dashes to
// ASCII, runs of whitespace to one space), so a quote the backend verified is found here
// too, then maps the match back to positions in the original text.

const FOLD: Record<string, string> = {
  "‘": "'",
  "’": "'",
  "‚": "'",
  "‛": "'",
  "′": "'",
  "“": '"',
  "”": '"',
  "„": '"',
  "″": '"',
  "‐": "-",
  "‑": "-",
  "‒": "-",
  "–": "-",
  "—": "-",
  "―": "-",
  "−": "-",
};

function fold(s: string): { text: string; map: number[] } {
  let text = "";
  const map: number[] = []; // folded index -> original index
  let lastWasSpace = false;
  for (let i = 0; i < s.length; i++) {
    let ch = FOLD[s[i]] ?? s[i];
    if (/\s/.test(ch)) {
      if (lastWasSpace) continue;
      ch = " ";
      lastWasSpace = true;
    } else {
      lastWasSpace = false;
    }
    text += ch;
    map.push(i);
  }
  return { text, map };
}

/** [start, end) of `evidence` in `text`, or null if it isn't there. */
export function findSpan(text: string, evidence: string): [number, number] | null {
  const needle = fold(evidence).text.trim();
  if (!needle) return null;
  const hay = fold(text);
  const at = hay.text.indexOf(needle);
  if (at < 0) return null;
  return [hay.map[at], hay.map[at + needle.length - 1] + 1];
}

export interface Span {
  key: string;
  start: number;
  end: number;
}

export interface Segment {
  start: number;
  end: number;
  keys: string[]; // which fields' evidence covers this piece (empty = plain text)
}

/** Cut the text into pieces so overlapping quotes can all be highlighted. */
export function segments(length: number, spans: Span[]): Segment[] {
  const cuts = new Set([0, length]);
  for (const s of spans) {
    cuts.add(s.start);
    cuts.add(s.end);
  }
  const points = [...cuts].sort((a, b) => a - b);
  const out: Segment[] = [];
  for (let i = 0; i < points.length - 1; i++) {
    const [start, end] = [points[i], points[i + 1]];
    const keys = spans.filter((s) => s.start <= start && s.end >= end).map((s) => s.key);
    out.push({ start, end, keys });
  }
  return out;
}
