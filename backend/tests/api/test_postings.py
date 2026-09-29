from datetime import datetime

from httpx import AsyncClient
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.llm.types import LLMUnavailable
from app.models import ExtractedField, LLMCall
from app.pipeline.normalize.dates import IST
from tests.pipeline.fakes import (
    FIXTURES,
    FakeLLMClient,
    acme_response,
    kasparro_response,
    m,
)

ACME = (FIXTURES / "acme.txt").read_text(encoding="utf-8")
KASPARRO = (FIXTURES / "kasparro.txt").read_text(encoding="utf-8")


def field(body: dict, name: str, index: int = 0) -> dict:
    return next(
        f for f in body["fields"] if f["field_name"] == name and f["mention_index"] == index
    )


async def count(db: async_sessionmaker[AsyncSession], model: type) -> int:
    async with db() as s:
        return await s.scalar(select(func.count()).select_from(model))


# --- the three API tests from the design ----------------------------------------------


async def test_short_raw_text_is_422_with_the_error_shape(api: AsyncClient):
    r = await api.post("/postings", json={"raw_text": "too short"})

    assert r.status_code == 422
    error = r.json()["error"]
    assert error["code"] == "validation_error"
    assert error["message"]
    assert error["details"][0]["loc"] == ["body", "raw_text"]


async def test_same_text_twice_returns_same_posting_without_a_second_llm_call(
    api: AsyncClient, fake_llm: FakeLLMClient
):
    fake_llm.queue(acme_response())
    first = await api.post("/postings", json={"raw_text": ACME})
    # Same posting, different whitespace: still a duplicate.
    again = await api.post("/postings", json={"raw_text": "  " + ACME.replace("\n", "\r\n")})

    assert first.status_code == 201
    assert again.status_code == 200
    assert again.json()["id"] == first.json()["id"]
    assert len(fake_llm.prompts) == 1


async def test_detail_returns_null_for_unverified_values(api: AsyncClient, fake_llm):
    fake_llm.queue(acme_response(location=m("Mumbai", "Location: Mumbai")))
    body = (await api.post("/postings", json={"raw_text": ACME})).json()

    detail = (await api.get(f"/postings/{body['id']}")).json()
    location = field(detail, "location")
    assert location["flag"] == "unverified"
    assert location["value"] is None
    assert location["evidence"] is None
    assert location["normalized"] is None
    assert "Mumbai" not in str(detail["fields"])


# --- create, persistence, llm_calls ----------------------------------------------------


async def test_create_saves_fields_calls_and_score(api: AsyncClient, fake_llm, db):
    fake_llm.queue("{not json", acme_response())
    r = await api.post("/postings", json={"raw_text": ACME, "source_label": "careers page"})

    assert r.status_code == 201
    body = r.json()
    assert body["status"] == "verified"
    assert body["source_label"] == "careers page"
    assert body["schema_version"] == "1.0"
    assert body["prompt_version"] == "extract_v1"
    assert field(body, "stipend")["normalized"] == {
        "period": "month",
        "min_inr": 30_000,
        "max_inr": 30_000,
    }
    assert body["score"]["badge"] == "check_manually"  # empty profile: CGPA unknown
    assert await count(db, LLMCall) == 2  # the failed attempt is logged too
    assert await count(db, ExtractedField) == len(body["fields"])


async def test_kasparro_stipend_is_shown_but_flagged(api: AsyncClient, fake_llm):
    fake_llm.queue(kasparro_response())
    body = (await api.post("/postings", json={"raw_text": KASPARRO})).json()

    stipend = field(body, "stipend")
    assert stipend["value"] == "Rs. 25,00 Per Month"  # verified quote: shown, in red
    assert stipend["flag"] == "ambiguous"
    assert stipend["normalized"] is None
    assert body["status"] == "partial"
    assert body["status_reason"] == "flagged: stipend (ambiguous)"


async def test_llm_outage_still_saves_the_posting(api: AsyncClient, fake_llm, db):
    fake_llm.queue(LLMUnavailable("timeout after 30s"))
    r = await api.post("/postings", json={"raw_text": ACME})

    assert r.status_code == 201
    assert r.json()["status"] == "needs_review"
    assert r.json()["status_reason"] == "llm_unavailable"
    assert r.json()["fields"] == []
    async with db() as s:
        call = await s.scalar(select(LLMCall))
    assert call.parse_ok is False
    assert "timeout" in call.error


async def test_reprocess_replaces_fields_and_keeps_call_history(api: AsyncClient, fake_llm, db):
    fake_llm.queue(LLMUnavailable("timeout after 30s"), acme_response())
    posting_id = (await api.post("/postings", json={"raw_text": ACME})).json()["id"]

    r = await api.post(f"/postings/{posting_id}/reprocess")

    assert r.status_code == 200
    assert r.json()["status"] == "verified"
    assert await count(db, LLMCall) == 2
    fields_before = len(r.json()["fields"])
    fake_llm.queue(acme_response())
    again = await api.post(f"/postings/{posting_id}/reprocess")
    assert len(again.json()["fields"]) == fields_before  # replaced, not appended


# --- list, sort, filter ------------------------------------------------------------------


async def _two_postings(api: AsyncClient, fake_llm) -> tuple[str, str]:
    fake_llm.queue(acme_response(), kasparro_response())
    acme = (await api.post("/postings", json={"raw_text": ACME})).json()["id"]
    kasparro = (await api.post("/postings", json={"raw_text": KASPARRO})).json()["id"]
    return acme, kasparro


async def test_list_sorted_by_deadline_upcoming_first(api: AsyncClient, fake_llm, clock):
    acme, kasparro = await _two_postings(api, fake_llm)

    rows = (await api.get("/postings")).json()
    assert [r["id"] for r in rows] == [kasparro, acme]  # 30 Sep before 15 Oct
    k = rows[0]
    assert k["company"] == "Kasparro"
    assert k["deadline"] == "2026-09-30T03:30:00Z"
    assert (k["cash_min_inr"], k["cash_max_inr"]) == (500_000, 800_000)
    assert "skills" not in k["scored_on"]  # the notice lists no skills

    clock["now"] = datetime(2026, 10, 1, tzinfo=IST)  # Kasparro's deadline has passed
    rows = (await api.get("/postings")).json()
    assert [r["id"] for r in rows] == [acme, kasparro]
    assert rows[1]["badge"] == "closed"


async def test_list_filter_by_status(api: AsyncClient, fake_llm):
    acme, _ = await _two_postings(api, fake_llm)

    rows = (await api.get("/postings", params={"status": "verified"})).json()
    assert [r["id"] for r in rows] == [acme]
    bad = await api.get("/postings", params={"status": "bogus"})
    assert bad.status_code == 422


async def test_list_sorted_by_score(api: AsyncClient, fake_llm):
    acme, kasparro = await _two_postings(api, fake_llm)
    profile = {"skills": ["Python", "FastAPI"], "preferred_locations": ["Pune"]}
    await api.put("/profile", json=profile)

    rows = (await api.get("/postings", params={"sort": "score"})).json()
    assert [r["id"] for r in rows] == [acme, kasparro]
    assert rows[0]["score"] > (rows[1]["score"] or 0)


# --- delete, not found, rate limit -------------------------------------------------------


async def test_delete_removes_posting_and_its_rows(api: AsyncClient, fake_llm, db):
    fake_llm.queue(acme_response())
    posting_id = (await api.post("/postings", json={"raw_text": ACME})).json()["id"]

    assert (await api.delete(f"/postings/{posting_id}")).status_code == 204
    assert (await api.get(f"/postings/{posting_id}")).status_code == 404
    assert await count(db, ExtractedField) == 0
    assert await count(db, LLMCall) == 0


async def test_unknown_id_is_404_with_the_error_shape(api: AsyncClient):
    missing = "00000000-0000-0000-0000-000000000000"
    for r in (
        await api.get(f"/postings/{missing}"),
        await api.delete(f"/postings/{missing}"),
        await api.post(f"/postings/{missing}/reprocess"),
    ):
        assert r.status_code == 404
        assert r.json() == {
            "error": {"code": "not_found", "message": "posting not found", "details": None}
        }
    assert (await api.get("/postings/not-a-uuid")).status_code == 422


async def test_eleventh_post_in_a_minute_is_rate_limited(api: AsyncClient, fake_llm):
    fake_llm.queue(acme_response())
    statuses = [
        (await api.post("/postings", json={"raw_text": ACME})).status_code for _ in range(11)
    ]

    assert statuses[:10] == [201] + [200] * 9
    last = await api.post("/postings", json={"raw_text": ACME})
    assert statuses[10] == 429
    assert last.json()["error"]["code"] == "rate_limited"
