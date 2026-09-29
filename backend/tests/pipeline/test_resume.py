from app.llm.types import LLMUnavailable
from app.pipeline.resume import read_resume
from tests.pipeline.fakes import FakeLLMClient
from tests.resume_fixtures import RESUME_TEXT, mention, resume_response


async def test_verified_suggestions():
    result = await read_resume(RESUME_TEXT, FakeLLMClient(resume_response()))

    assert result.failure is None
    assert result.name.value == "Asha Verma"
    assert result.cgpa.value == 8.4
    assert result.cgpa.evidence == "CGPA: 8.4/10"
    assert [s.value for s in result.skills][:3] == ["Python", "TypeScript", "SQL"]
    assert result.rejected == []
    assert len(result.calls) == 1


async def test_invented_skill_is_rejected_not_suggested():
    skills = [{"name": "Python", "evidence": "Python"}, {"name": "Kubernetes", "evidence": "K8s"}]
    result = await read_resume(RESUME_TEXT, FakeLLMClient(resume_response(skills=skills)))

    assert [s.value for s in result.skills] == ["Python"]
    assert [(r.field, r.value, r.reason) for r in result.rejected] == [
        ("skill", "Kubernetes", "quote not found in the resume")
    ]


async def test_skill_named_differently_from_its_quote_is_rejected():
    skills = [{"name": "Kubernetes", "evidence": "Docker"}]  # real quote, invented value
    result = await read_resume(RESUME_TEXT, FakeLLMClient(resume_response(skills=skills)))

    assert result.skills == []
    assert result.rejected[0].reason == "value isn't in its own quote"


async def test_cgpa_number_comes_from_the_quote_not_the_value():
    # The model "rounds" 8.4 to 8.5 in its value: rejected, because 8.5 isn't in the quote.
    response = resume_response(cgpa=mention("8.5", "CGPA: 8.4/10"))
    result = await read_resume(RESUME_TEXT, FakeLLMClient(response))

    assert result.cgpa is None
    assert result.rejected[0].field == "cgpa"


async def test_cgpa_on_another_scale_is_rejected_with_reason():
    text = RESUME_TEXT.replace("CGPA: 8.4/10", "GPA: 3.7/4.0")
    response = resume_response(cgpa=mention("3.7/4.0", "GPA: 3.7/4.0"))
    result = await read_resume(text, FakeLLMClient(response))

    assert result.cgpa is None
    assert "not on a 10-point scale" in result.rejected[0].reason


async def test_duplicate_skills_after_aliasing_are_suggested_once():
    skills = [{"name": n, "evidence": n} for n in ("React.js", "React.js", "PostgreSQL")]
    result = await read_resume(RESUME_TEXT, FakeLLMClient(resume_response(skills=skills)))

    assert [s.value for s in result.skills] == ["React.js", "PostgreSQL"]


async def test_missing_fields_are_absent_not_rejected():
    response = resume_response(name=mention(None), cgpa=mention(None), skills=[])
    result = await read_resume(RESUME_TEXT, FakeLLMClient(response))

    assert (result.name, result.cgpa, result.skills, result.rejected) == (None, None, [], [])


async def test_invalid_twice_fails_closed():
    result = await read_resume(RESUME_TEXT, FakeLLMClient("nope", {"schema_version": "9"}))

    assert result.failure.startswith("extraction_invalid: ")
    assert (result.name, result.skills) == (None, [])
    assert len(result.calls) == 2


async def test_provider_down():
    result = await read_resume(RESUME_TEXT, FakeLLMClient(LLMUnavailable("timeout")))

    assert result.failure == "llm_unavailable"
