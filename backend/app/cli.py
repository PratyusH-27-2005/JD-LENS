"""Run the real pipeline on a posting file and print what the code decided.

python -m app.cli tests/fixtures/postings/kasparro.txt [--raw]
"""

import argparse
import asyncio
import json
from pathlib import Path

from app.config import get_settings
from app.llm.client import GeminiClient
from app.pipeline.ingest import clean
from app.pipeline.run import PipelineResult, run_extraction


def _print(result: PipelineResult, show_raw: bool) -> None:
    print(f"status: {result.status}   reason: {result.status_reason}")
    for c in result.calls:
        tokens = f"{c.input_tokens}->{c.output_tokens} tok"
        print(f"call {c.attempt}: parse_ok={c.parse_ok} {c.latency_ms} ms {tokens} err={c.error}")
    print()
    for f in result.fields:
        name = f"{f.field_name}[{f.mention_index}]"
        print(f"{name:26} {f.flag:10} {f.display_value!r}")
        if f.flag_reason:
            print(f"{'':26}   reason: {f.flag_reason}")
        if f.normalized:
            print(f"{'':26}   normalized: {json.dumps(f.normalized, ensure_ascii=False)}")
    print(f"\nfacts for scoring: {result.facts}")
    if show_raw:
        for c in result.calls:
            print(f"\n--- raw response, attempt {c.attempt} ---\n{c.raw_response}")


async def _main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("posting", type=Path)
    parser.add_argument("--raw", action="store_true", help="print raw model responses")
    args = parser.parse_args()

    settings = get_settings()
    if not settings.llm_configured:
        raise SystemExit("LLM_API_KEY is not set (put it in the repo-root .env)")
    text = clean(args.posting.read_text(encoding="utf-8"))
    result = await run_extraction(text, GeminiClient.from_settings(settings))
    _print(result, args.raw)


if __name__ == "__main__":
    asyncio.run(_main())
