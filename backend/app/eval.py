"""Field-level eval against the real model.

    python -m app.eval [--runs 3] [--out ../docs/eval.md]

For every `<name>.txt` fixture with a `<name>.expected.json` next to it, runs the full
pipeline (real LLM, no database) `--runs` times and checks what the *code* decided:
status, each field's flag, parsed values, and the verified skill set. Expectations are
written by hand from the posting text, not copied from model output.

Also reports what the design's risk table asks to watch: how often the model's quotes
are rejected (evidence rejection rate), how often the retry is needed, latency, tokens.
"""

import argparse
import asyncio
import json
import statistics
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from app.config import get_settings
from app.llm.client import GeminiClient
from app.llm.prompt import PROMPT_VERSION
from app.llm.types import LLMClient
from app.pipeline.ingest import clean
from app.pipeline.run import FieldResult, PipelineResult, run_extraction
from app.pipeline.scoring import canonical_skill

DEFAULT_FIXTURES = Path(__file__).parents[1] / "tests" / "fixtures" / "postings"


@dataclass(frozen=True)
class Check:
    name: str  # "status" or a field name
    passed: bool
    detail: str = ""  # what was wrong, when it failed


@dataclass
class RunReport:
    fixture: str
    checks: list[Check]
    result: PipelineResult

    @property
    def passed(self) -> int:
        return sum(c.passed for c in self.checks)


@dataclass
class Summary:
    reports: list[RunReport] = field(default_factory=list)

    def rejection_rate(self) -> tuple[int, int]:
        """(unverified mentions, mentions the model gave a quote or value for)."""
        attempted = [f for r in self.reports for f in r.result.fields if f.flag != "missing"]
        return sum(f.flag == "unverified" for f in attempted), len(attempted)


# --- comparing one pipeline result with its expectation ------------------------------


def check_result(result: PipelineResult, expected: dict[str, Any]) -> list[Check]:
    checks = [
        Check(
            "status",
            result.status == expected["status"],
            f"got {result.status} ({result.status_reason})",
        )
    ]
    for name, exp in expected["fields"].items():
        mentions = [f for f in result.fields if f.field_name == name]
        check = (
            _check_skills(mentions, exp)
            if name == "required_skills"
            else _check_field(name, mentions, exp)
        )
        checks.append(check)
    return checks


def _check_field(name: str, mentions: list[FieldResult], exp: dict[str, Any]) -> Check:
    if not mentions:
        return Check(name, False, "field absent from the result")
    first = mentions[0]
    problems = []
    flags = sorted({m.flag for m in mentions})
    if flags != [exp["flag"]]:
        problems.append(f"flag {'/'.join(flags)} (expected {exp['flag']})")
    if "normalized" in exp:
        got = first.normalized or {}
        wrong = {k: got.get(k) for k, v in exp["normalized"].items() if got.get(k) != v}
        if wrong:
            problems.append(f"parsed {wrong}")
    if "value_contains" in exp:
        value = first.display_value or ""
        if exp["value_contains"].casefold() not in value.casefold():
            problems.append(f"value {value[:60]!r}")
    return Check(name, not problems, "; ".join(problems))


def _check_skills(mentions: list[FieldResult], exp: dict[str, Any]) -> Check:
    got = {canonical_skill(m.raw_value) for m in mentions if m.flag == "none" and m.raw_value}
    required = {canonical_skill(s) for s in exp["required"]}
    allowed = required | {canonical_skill(s) for s in exp["allowed_extra"]}
    missing, extra = required - got, got - allowed
    hidden = sum(m.flag == "unverified" for m in mentions)
    problems = []
    if missing:
        problems.append(f"missing {sorted(missing)}")
    if extra:
        problems.append(f"unexpected {sorted(extra)}")
    if hidden:
        problems.append(f"{hidden} rejected quote(s)")
    return Check("required_skills", not (missing or extra), "; ".join(problems))


# --- running and reporting -----------------------------------------------------------


@dataclass(frozen=True)
class Case:
    name: str
    text: str
    expected: dict[str, Any]


def load_cases(fixtures: Path) -> list[Case]:
    """Every `<name>.txt` that has a `<name>.expected.json` next to it."""
    return [
        Case(
            name=path.name.removesuffix(".expected.json"),
            text=clean((fixtures / path.name.replace(".expected.json", ".txt")).read_text("utf-8")),
            expected=json.loads(path.read_text(encoding="utf-8")),
        )
        for path in sorted(fixtures.glob("*.expected.json"))
    ]


async def run_eval(cases: list[Case], runs: int, client: LLMClient) -> Summary:
    summary = Summary()
    for case in cases:
        for run in range(1, runs + 1):
            result = await run_extraction(case.text, client)
            report = RunReport(case.name, check_result(result, case.expected), result)
            summary.reports.append(report)
            print(
                f"  {case.name} run {run}: {report.passed}/{len(report.checks)} checks", flush=True
            )
    return summary


def to_markdown(summary: Summary, runs: int, model: str) -> str:
    by_fixture: dict[str, list[RunReport]] = {}
    for r in summary.reports:
        by_fixture.setdefault(r.fixture, []).append(r)

    lines = [f"Model `{model}`, prompt `{PROMPT_VERSION}`, {runs} run(s) per posting.", ""]
    total = sum(len(r.checks) for r in summary.reports)
    passed = sum(r.passed for r in summary.reports)
    lines.append(f"**{passed}/{total} checks passed.**")
    lines.append("")

    header = "| Check | " + " | ".join(by_fixture) + " |"
    lines += [header, "|---" * (len(by_fixture) + 1) + "|"]
    names = [c.name for c in next(iter(by_fixture.values()))[0].checks]
    for name in names:
        cells = []
        for reports in by_fixture.values():
            results = [next(c for c in r.checks if c.name == name) for r in reports]
            ok = sum(c.passed for c in results)
            cell = "✓" if ok == len(results) else f"✗ {ok}/{len(results)}"
            failed = next((c.detail for c in results if not c.passed), "")
            cells.append(cell + (f" ({failed})" if failed else ""))
        lines.append(f"| {name} | " + " | ".join(cells) + " |")

    rejected, attempted = summary.rejection_rate()
    calls = [c for r in summary.reports for c in r.result.calls]
    retried = sum(len(r.result.calls) > 1 for r in summary.reports)
    closed = sum(r.result.status == "needs_review" for r in summary.reports)
    latencies = [c.latency_ms for c in calls if c.latency_ms is not None]
    tokens_in = [c.input_tokens for c in calls if c.input_tokens]
    tokens_out = [c.output_tokens for c in calls if c.output_tokens]
    lines += [
        "",
        f"- Evidence rejection rate: {rejected}/{attempted} quoted mentions "
        f"({100 * rejected / max(attempted, 1):.0f}%) were not found in the posting.",
        f"- Retries: {retried}/{len(summary.reports)} extractions needed the second attempt; "
        f"{closed} ended in needs_review.",
    ]
    if latencies:
        lines.append(
            f"- Latency per call: median {statistics.median(latencies) / 1000:.1f} s, "
            f"max {max(latencies) / 1000:.1f} s."
        )
    if tokens_in and tokens_out:
        lines.append(
            f"- Tokens per call: ~{statistics.mean(tokens_in):.0f} in, "
            f"~{statistics.mean(tokens_out):.0f} out."
        )
    return "\n".join(lines) + "\n"


async def _main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--runs", type=int, default=3)
    parser.add_argument("--fixtures", type=Path, default=DEFAULT_FIXTURES)
    parser.add_argument("--out", type=Path, help="also write the markdown report here")
    args = parser.parse_args()

    settings = get_settings()
    if not settings.llm_configured:
        raise SystemExit("LLM_API_KEY is not set (put it in the repo-root .env)")
    client = GeminiClient.from_settings(settings)
    summary = await run_eval(load_cases(args.fixtures), args.runs, client)
    report = to_markdown(summary, args.runs, client.model_name)
    print("\n" + report)
    if args.out:
        args.out.write_text(report, encoding="utf-8")


if __name__ == "__main__":
    asyncio.run(_main())
