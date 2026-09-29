from datetime import datetime

from app.llm.types import LLMUnavailable
from app.pipeline.normalize.dates import IST
from app.pipeline.run import FieldResult, PipelineResult, run_extraction
from tests.pipeline.fakes import (
    NULL,
    FakeLLMClient,
    acme_response,
    kasparro_response,
    m,
    posting,
)

ACME = posting("acme.txt")
KASPARRO = posting("kasparro.txt")


def field(result: PipelineResult, name: str, index: int = 0) -> FieldResult:
    return next(f for f in result.fields if f.field_name == name and f.mention_index == index)


# --- the six pipeline tests from the design -------------------------------------------


async def test_valid_response_is_verified_with_one_call_logged():
    result = await run_extraction(ACME, FakeLLMClient(acme_response()))

    assert result.status == "verified"
    assert result.status_reason is None
    assert len(result.calls) == 1
    assert result.calls[0].parse_ok
    assert result.calls[0].raw_response is not None
    assert {f.flag for f in result.fields} == {"none"}


async def test_invalid_json_then_valid_retries_with_the_error():
    fake = FakeLLMClient("Sure! Here is the JSON: {", acme_response())
    result = await run_extraction(ACME, fake)

    assert result.status == "verified"
    assert [c.parse_ok for c in result.calls] == [False, True]
    assert [c.attempt for c in result.calls] == [1, 2]
    first_error = result.calls[0].error
    assert first_error and "Invalid JSON" in first_error
    assert first_error not in fake.prompts[0]
    assert first_error in fake.prompts[1]


async def test_invalid_twice_fails_closed_after_exactly_two_calls():
    bad_schema = acme_response(schema_version="2.0", salary=m("lots"))
    fake = FakeLLMClient("not json", bad_schema)
    result = await run_extraction(ACME, fake)

    assert result.status == "needs_review"
    assert result.status_reason.startswith("extraction_invalid: ")
    assert "schema_version" in result.status_reason
    assert len(result.calls) == 2
    assert len(fake.prompts) == 2
    assert result.fields == []  # never partial, invented values


async def test_invented_quote_marks_field_unverified_and_hides_value():
    response = acme_response(location=m("Mumbai", "Location: Mumbai"))
    result = await run_extraction(ACME, FakeLLMClient(response))

    location = field(result, "location")
    assert location.flag == "unverified"
    assert not location.evidence_verified
    assert location.display_value is None
    assert location.normalized is None
    assert result.facts.location is None
    assert result.status == "partial"


async def test_two_disagreeing_stipend_mentions_are_a_conflict_and_both_kept():
    text = ACME + "\nFor the first two months the stipend is ₹ 25,000 per month."
    response = acme_response(stipend=[m("₹ 30,000 per month"), m("₹ 25,000 per month")])
    result = await run_extraction(text, FakeLLMClient(response))

    first, second = field(result, "stipend", 0), field(result, "stipend", 1)
    assert (first.flag, second.flag) == ("conflict", "conflict")
    assert first.normalized == {"period": "month", "min_inr": 30_000, "max_inr": 30_000}
    assert second.normalized == {"period": "month", "min_inr": 25_000, "max_inr": 25_000}
    assert first.display_value and second.display_value
    assert result.status == "partial"


async def test_provider_timeout_is_needs_review_llm_unavailable():
    fake = FakeLLMClient(LLMUnavailable("timeout after 30s"))
    result = await run_extraction(ACME, fake)

    assert result.status == "needs_review"
    assert result.status_reason == "llm_unavailable"
    assert len(result.calls) == 1
    assert "timeout" in result.calls[0].error
    assert result.calls[0].raw_response is None


# --- beyond the minimum --------------------------------------------------------------


async def test_facts_for_scoring_come_from_verified_fields():
    result = await run_extraction(ACME, FakeLLMClient(acme_response()))

    facts = result.facts
    assert facts.required_skills == ["Python", "FastAPI", "PostgreSQL", "Docker"]
    assert facts.location == "Pune, Maharashtra"
    assert facts.work_mode == "hybrid"
    assert facts.cash_max_inr == 1_200_000
    assert (facts.cgpa_min, facts.backlogs_allowed) == (7.0, False)
    assert facts.deadline == datetime(2026, 10, 15, 23, 59, tzinfo=IST)


async def test_kasparro_notice():
    result = await run_extraction(KASPARRO, FakeLLMClient(kasparro_response()))

    stipend = field(result, "stipend")
    assert stipend.flag == "ambiguous"
    assert '"25,00" is not a valid digit grouping' in stipend.flag_reason
    assert stipend.normalized is None
    assert field(result, "ctc").normalized["cash_max_inr"] == 800_000
    assert field(result, "ctc").normalized["has_equity"] is True
    assert field(result, "application_deadline").normalized["iso"] == "2026-09-30T09:00:00+05:30"
    assert field(result, "work_mode").flag == "missing"
    assert field(result, "required_skills").flag == "missing"
    assert result.status == "partial"
    assert result.status_reason == "flagged: stipend (ambiguous)"
    assert result.facts.cash_max_inr == 800_000


async def test_model_that_fixes_the_stipend_value_is_not_trusted():
    # A "helpful" model turns Rs. 25,00 into ₹ 25,000. The quote is real; the value isn't.
    response = kasparro_response(stipend=[m("₹ 25,000 per month", "Rs. 25,00 Per Month")])
    result = await run_extraction(KASPARRO, FakeLLMClient(response))

    stipend = field(result, "stipend")
    assert stipend.flag == "unverified"
    assert stipend.flag_reason == "value does not appear in its own evidence"
    assert stipend.display_value is None


async def test_recruitment_drive_mode_is_not_a_work_mode():
    response = kasparro_response(work_mode=m("virtual", "in virtual mode"))
    result = await run_extraction(KASPARRO, FakeLLMClient(response))

    assert field(result, "work_mode").flag == "ambiguous"
    assert result.facts.work_mode is None


async def test_unverified_company_needs_review():
    response = acme_response(company=m("Acme Corp", "Acme Corp is hiring"))
    result = await run_extraction(ACME, FakeLLMClient(response))

    assert result.status == "needs_review"
    assert result.status_reason == "not verified: company"


async def test_missing_fields_do_not_downgrade_status():
    response = acme_response(work_mode=NULL, ctc=[], required_skills=[])
    result = await run_extraction(ACME, FakeLLMClient(response))

    assert result.status == "verified"
    assert field(result, "ctc").flag == "missing"
    assert result.facts.required_skills is None


async def test_skill_name_must_be_in_its_evidence():
    skills = [{"name": "Python", "evidence": "Python"}, {"name": "Django", "evidence": "FastAPI"}]
    result = await run_extraction(ACME, FakeLLMClient(acme_response(required_skills=skills)))

    assert field(result, "required_skills", 1).flag == "unverified"
    assert result.facts.required_skills == ["Python"]


async def test_numbers_are_parsed_from_the_evidence_not_the_value():
    # The value "30,000" alone has no period; the verified quote does.
    response = acme_response(stipend=[m("30,000", "₹ 30,000 per month")])
    result = await run_extraction(ACME, FakeLLMClient(response))

    stipend = field(result, "stipend")
    assert stipend.flag == "none"
    assert stipend.normalized == {"period": "month", "min_inr": 30_000, "max_inr": 30_000}
