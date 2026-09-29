"""The eval's comparison logic, checked without the network: a well-behaved fake model
must pass every expectation, and each kind of mistake must be caught."""

import json

import pytest

from app.eval import check_result, load_cases, run_eval, to_markdown
from app.pipeline.run import run_extraction
from tests.pipeline.fakes import (
    FIXTURES,
    FakeLLMClient,
    acme_response,
    kasparro_response,
    m,
    posting,
)

EXPECTED = {
    name: json.loads((FIXTURES / f"{name}.expected.json").read_text(encoding="utf-8"))
    for name in ("acme", "kasparro")
}


def failed(checks) -> dict[str, str]:
    return {c.name: c.detail for c in checks if not c.passed}


@pytest.mark.parametrize(
    ("name", "response"), [("acme", acme_response()), ("kasparro", kasparro_response())]
)
async def test_expected_files_match_a_well_behaved_model(name, response):
    result = await run_extraction(posting(f"{name}.txt"), FakeLLMClient(response))
    assert failed(check_result(result, EXPECTED[name])) == {}


async def test_catches_a_model_that_fixes_the_stipend():
    response = kasparro_response(stipend=[m("₹ 25,000 per month", "Rs. 25,00 Per Month")])
    result = await run_extraction(posting("kasparro.txt"), FakeLLMClient(response))

    problems = failed(check_result(result, EXPECTED["kasparro"]))
    assert "flag unverified (expected ambiguous)" in problems["stipend"]


async def test_catches_a_split_ctc_as_a_false_conflict():
    # The near miss from NOTES.md: cash and total quoted as two separate mentions.
    ctc = [
        m("Rs. 5.00 –Rs. 8.00 LPA cash"),
        m("Total Rs. 10.00–Rs. 16.00 LPA"),
    ]
    result = await run_extraction(
        posting("kasparro.txt"), FakeLLMClient(kasparro_response(ctc=ctc))
    )

    assert "conflict" in failed(check_result(result, EXPECTED["kasparro"]))["ctc"]


async def test_catches_missing_and_unexpected_skills():
    skills = [{"name": s, "evidence": s} for s in ("Python", "FastAPI", "PostgreSQL")]
    skills.append({"name": "Kubernetes", "evidence": "Skills: Python"})  # invented
    result = await run_extraction(
        posting("acme.txt"), FakeLLMClient(acme_response(required_skills=skills))
    )

    detail = failed(check_result(result, EXPECTED["acme"]))["required_skills"]
    assert "missing ['docker']" in detail
    assert "1 rejected quote(s)" in detail


async def test_report_counts_and_rejection_rate(tmp_path):
    for name in ("acme", "kasparro"):
        (tmp_path / f"{name}.txt").write_text(posting(f"{name}.txt"), encoding="utf-8")
        (tmp_path / f"{name}.expected.json").write_text(
            json.dumps(EXPECTED[name]), encoding="utf-8"
        )
    fake = FakeLLMClient(
        acme_response(location=m("Mumbai", "Location: Mumbai")),  # one rejected quote
        "not json",  # kasparro: retry once
        kasparro_response(),
    )

    summary = await run_eval(load_cases(tmp_path), runs=1, client=fake)
    report = to_markdown(summary, runs=1, model="fake-model")

    assert "20/22 checks passed" in report  # acme: location + status fail
    assert "Retries: 1/2 extractions" in report
    assert "rejection rate: 1/" in report
