from httpx import AsyncClient

from app.llm.types import LLMUnavailable
from tests.resume_fixtures import RESUME_LINES, make_pdf, resume_response

PDF = {"content-type": "application/pdf"}


async def test_import_returns_verified_suggestions_and_changes_nothing(api: AsyncClient, fake_llm):
    await api.put("/profile", json={"skills": ["Python", "postgres"], "cgpa": 7.0})
    fake_llm.queue(resume_response())

    r = await api.post("/profile/resume", content=make_pdf(RESUME_LINES), headers=PDF)

    assert r.status_code == 200
    body = r.json()
    assert body["name"] == {"value": "Asha Verma", "evidence": "Asha Verma"}
    assert body["cgpa"] == {"value": 8.4, "evidence": "CGPA: 8.4/10"}
    new = {s["value"]: s["new"] for s in body["skills"]}
    assert new["Python"] is False
    assert new["PostgreSQL"] is False  # "postgres" in the profile, via the alias map
    assert new["FastAPI"] is True
    assert body["prompt_version"] == "resume_v1"
    # Suggestions only: the profile is untouched until PUT /profile.
    profile = (await api.get("/profile")).json()
    assert (profile["skills"], profile["cgpa"], profile["name"]) == (
        ["Python", "postgres"],
        7.0,
        "",
    )


async def test_resume_text_reaches_the_model(api: AsyncClient, fake_llm):
    fake_llm.queue(resume_response())
    await api.post("/profile/resume", content=make_pdf(RESUME_LINES), headers=PDF)

    assert "Frameworks: FastAPI, React.js, Next.js" in fake_llm.prompts[0]


async def test_wrong_content_type_is_415(api: AsyncClient):
    r = await api.post("/profile/resume", content=b"hello", headers={"content-type": "text/plain"})

    assert r.status_code == 415
    assert r.json()["error"]["code"] == "unsupported_media_type"


async def test_oversized_file_is_413(api: AsyncClient):
    r = await api.post("/profile/resume", content=b"%PDF-" + b"0" * (5 * 1024 * 1024), headers=PDF)

    assert r.status_code == 413
    assert r.json()["error"]["code"] == "file_too_large"


async def test_unreadable_pdf_is_422_and_the_model_is_not_called(api: AsyncClient, fake_llm):
    r = await api.post("/profile/resume", content=make_pdf([]), headers=PDF)

    assert r.status_code == 422
    assert r.json()["error"]["code"] == "resume_unreadable"
    assert "no text found" in r.json()["error"]["message"]
    assert fake_llm.prompts == []


async def test_model_down_is_503(api: AsyncClient, fake_llm):
    fake_llm.queue(LLMUnavailable("timeout after 30s"))
    r = await api.post("/profile/resume", content=make_pdf(RESUME_LINES), headers=PDF)

    assert r.status_code == 503
    assert r.json()["error"]["code"] == "llm_unavailable"


async def test_invalid_model_output_twice_is_502(api: AsyncClient, fake_llm):
    fake_llm.queue("nope", "still nope")
    r = await api.post("/profile/resume", content=make_pdf(RESUME_LINES), headers=PDF)

    assert r.status_code == 502
    assert r.json()["error"]["code"] == "extraction_invalid"
