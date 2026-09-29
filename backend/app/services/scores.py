"""Profile access and (re)scoring. Scores are derived data: always recomputable from the
stored fields and the profile, which is what PUT /profile relies on."""

import uuid
from collections import defaultdict
from collections.abc import Iterable
from datetime import datetime
from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app import models
from app.pipeline import scoring
from app.pipeline.run import FieldResult, facts_for_scoring
from app.schemas.api import Badge, ProfileIn

PROFILE_ID = 1  # one user for now


async def get_profile(session: AsyncSession) -> models.Profile:
    """The single profile row, created empty on first use (race-safe)."""
    await session.execute(
        insert(models.Profile)
        .values(id=PROFILE_ID, name="", skills=[], preferred_locations=[])
        .on_conflict_do_nothing(index_elements=["id"])
    )
    return await session.get_one(models.Profile, PROFILE_ID)


async def update_profile(session: AsyncSession, data: ProfileIn, now: datetime) -> models.Profile:
    profile = await get_profile(session)
    for key, value in data.model_dump().items():
        setattr(profile, key, value)
    if data.cgpa is not None:
        profile.cgpa = Decimal(str(round(data.cgpa, 2)))
    await session.flush()
    await rescore_all(session, profile, now)
    await session.commit()
    await session.refresh(profile)
    return profile


def to_scoring_profile(p: models.Profile) -> scoring.Profile:
    return scoring.Profile(
        skills=list(p.skills or []),
        cgpa=float(p.cgpa) if p.cgpa is not None else None,
        has_backlogs=p.has_backlogs,
        preferred_locations=list(p.preferred_locations or []),
        min_cash_inr=p.min_cash_inr,
    )


def to_field_result(row: models.ExtractedField) -> FieldResult:
    return FieldResult(
        field_name=row.field_name,
        mention_index=row.mention_index,
        raw_value=row.raw_value,
        evidence=row.evidence,
        evidence_verified=row.evidence_verified,
        normalized=row.normalized,
        flag=row.flag,  # type: ignore[arg-type]  # CHECK constraint keeps it a Flag
        flag_reason=row.flag_reason,
    )


async def save_score(
    session: AsyncSession,
    posting_id: uuid.UUID,
    profile: models.Profile,
    fields: Iterable[FieldResult],
    now: datetime,
) -> None:
    """Score one posting from its verified fields and upsert match_scores."""
    result = scoring.score_posting(
        to_scoring_profile(profile), facts_for_scoring(list(fields)), now
    )
    values = {
        "profile_id": profile.id,
        "score": result.score,
        "eligible": result.eligibility.eligible,
        "breakdown": result.breakdown(),
        "computed_at": func.now(),
    }
    await session.execute(
        insert(models.MatchScore)
        .values(posting_id=posting_id, **values)
        .on_conflict_do_update(index_elements=["posting_id"], set_=values)
    )


async def rescore_all(session: AsyncSession, profile: models.Profile, now: datetime) -> None:
    rows = await session.scalars(select(models.ExtractedField))
    by_posting: dict[uuid.UUID, list[FieldResult]] = defaultdict(list)
    for row in rows:
        by_posting[row.posting_id].append(to_field_result(row))
    for posting_id in await session.scalars(select(models.Posting.id)):
        await save_score(session, posting_id, profile, by_posting.get(posting_id, []), now)


def badge(eligible: bool | None, deadline: datetime | None, now: datetime) -> Badge:
    """Computed at read time: "closed" depends on the clock, so it is never stored."""
    if deadline is not None and deadline <= now:
        return "closed"
    if eligible is None:
        return "check_manually"
    return "eligible" if eligible else "not_eligible"
