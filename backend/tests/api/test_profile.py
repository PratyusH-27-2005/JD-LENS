from httpx import AsyncClient

from tests.pipeline.fakes import FIXTURES, acme_response

ACME = (FIXTURES / "acme.txt").read_text(encoding="utf-8")
ME = {
    "name": "Manav",
    "skills": ["Python", "FastAPI", "Postgres", "React"],
    "cgpa": 8.1,
    "has_backlogs": False,
    "preferred_locations": ["Pune", "Bangalore"],
    "min_cash_inr": 600_000,
}


async def test_profile_starts_empty(api: AsyncClient):
    r = await api.get("/profile")

    assert r.status_code == 200
    body = r.json()
    assert (body["skills"], body["cgpa"], body["has_backlogs"]) == ([], None, None)


async def test_put_profile_saves_and_rescores_every_posting(api: AsyncClient, fake_llm):
    fake_llm.queue(acme_response())
    posting_id = (await api.post("/postings", json={"raw_text": ACME})).json()["id"]
    before = (await api.get(f"/postings/{posting_id}")).json()["score"]

    r = await api.put("/profile", json=ME)

    assert r.status_code == 200
    assert r.json()["cgpa"] == 8.1
    after = (await api.get(f"/postings/{posting_id}")).json()["score"]
    assert before["badge"] == "check_manually"
    assert after["badge"] == "eligible"  # 8.1 ≥ 7.0 and no backlogs
    # 3 of 4 skills (postgres → postgresql) = 37.5, Pune = 20, 12 LPA ≥ 6 LPA = 30
    assert after["score"] == 88
    assert after["breakdown"]["parts"]["skills"]["inputs"]["missing"] == ["docker"]


async def test_cgpa_of_ten_is_valid(api: AsyncClient):
    # numeric(3,2) from the first draft of the design would reject this.
    r = await api.put("/profile", json=ME | {"cgpa": 10})
    assert r.status_code == 200
    assert r.json()["cgpa"] == 10.0


async def test_invalid_profile_is_422(api: AsyncClient):
    r = await api.put("/profile", json=ME | {"cgpa": 11})

    assert r.status_code == 422
    assert r.json()["error"]["code"] == "validation_error"
    assert r.json()["error"]["details"][0]["loc"] == ["body", "cgpa"]
