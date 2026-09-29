"""Postings: create, reprocess, read, list, delete.

The LLM call (5–20 s) never runs inside a database transaction. The pipeline result is
then written in ONE transaction: posting, fields, llm_calls and score together, or none.
"""

import uuid
from datetime import datetime
from typing import Any, Literal

from sqlalchemy import BigInteger, ColumnElement, DateTime, and_, case, cast, delete, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import aliased

from app import models
from app.errors import NotFound
from app.llm.types import LLMClient
from app.pipeline.ingest import clean, content_hash
from app.pipeline.run import PipelineResult, run_extraction
from app.schemas.api import FieldOut, PostingDetail, PostingSummary, ScoreOut
from app.services import scores

FIELD_ORDER = (
    "company",
    "role_title",
    "location",
    "work_mode",
    "stipend",
    "ctc",
    "eligibility",
    "application_deadline",
    "apply_instructions",
    "required_skills",
)
Sort = Literal["deadline", "score"]


async def create_posting(
    session: AsyncSession,
    raw_text: str,
    source_label: str | None,
    client: LLMClient,
    now: datetime,
) -> tuple[uuid.UUID, bool]:
    """Returns (posting id, created). A known hash returns the existing posting and the
    LLM is not called."""
    clean_text = clean(raw_text)
    digest = content_hash(clean_text)
    if existing := await _id_by_hash(session, digest):
        return existing, False
    await session.rollback()  # end the read transaction before the slow LLM call

    result = await run_extraction(clean_text, client)

    posting = models.Posting(
        id=uuid.uuid4(),
        raw_text=raw_text,
        clean_text=clean_text,
        content_hash=digest,
        source_label=source_label,
    )
    _apply_result(posting, result, now)
    session.add(posting)
    try:
        await session.flush()
        await _save_children(session, posting.id, result, now)
        await session.commit()
    except IntegrityError:
        # Someone saved the same text while our LLM call was running.
        await session.rollback()
        if existing := await _id_by_hash(session, digest):
            return existing, False
        raise
    return posting.id, True


async def reprocess_posting(
    session: AsyncSession, posting_id: uuid.UUID, client: LLMClient, now: datetime
) -> None:
    """Rerun the pipeline (e.g. after a prompt change). Old llm_calls are kept as history."""
    posting = await _get(session, posting_id)
    clean_text = posting.clean_text
    await session.rollback()

    result = await run_extraction(clean_text, client)

    posting = await _get(session, posting_id)  # it may have been deleted meanwhile
    await session.execute(
        delete(models.ExtractedField).where(models.ExtractedField.posting_id == posting_id)
    )
    _apply_result(posting, result, now)
    await _save_children(session, posting_id, result, now)
    await session.commit()


async def delete_posting(session: AsyncSession, posting_id: uuid.UUID) -> None:
    deleted = await session.scalar(
        delete(models.Posting).where(models.Posting.id == posting_id).returning(models.Posting.id)
    )
    if deleted is None:
        raise NotFound("posting")
    await session.commit()  # fields, score and llm_calls go with it (ON DELETE CASCADE)


async def get_detail(session: AsyncSession, posting_id: uuid.UUID, now: datetime) -> PostingDetail:
    posting = await _get(session, posting_id)
    rows = (
        await session.scalars(
            select(models.ExtractedField).where(models.ExtractedField.posting_id == posting_id)
        )
    ).all()
    rows = sorted(rows, key=lambda r: (FIELD_ORDER.index(r.field_name), r.mention_index))
    score = await session.get(models.MatchScore, posting_id)
    return PostingDetail(
        id=posting.id,
        status=posting.status,  # type: ignore[arg-type]
        status_reason=posting.status_reason,
        source_label=posting.source_label,
        raw_text=posting.raw_text,
        clean_text=posting.clean_text,
        schema_version=posting.schema_version,
        prompt_version=posting.prompt_version,
        model_name=posting.model_name,
        created_at=posting.created_at,
        processed_at=posting.processed_at,
        fields=[_field_out(r) for r in rows],
        score=_score_out(score, _deadline(rows), now) if score else None,
    )


async def list_summaries(
    session: AsyncSession, status: str | None, sort: Sort, now: datetime
) -> list[PostingSummary]:
    """One query. Each displayed value comes from a verified, unflagged field (LEFT JOIN
    on flag = 'none'), so a flagged or unverified value shows up as null."""
    P = models.Posting
    company, company_on = _mention("company")
    role, role_on = _mention("role_title")
    dl, dl_on = _mention("application_deadline")
    ctc, ctc_on = _mention("ctc")
    deadline = cast(dl.normalized["iso"].astext, DateTime(timezone=True))
    upcoming_first = case((deadline.is_(None), 2), (deadline <= now, 1), else_=0)

    stmt = (
        select(
            P.id,
            P.status,
            P.source_label,
            P.created_at,
            company.raw_value.label("company"),
            role.raw_value.label("role_title"),
            deadline.label("deadline"),
            cast(ctc.normalized["cash_min_inr"].astext, BigInteger).label("cash_min_inr"),
            cast(ctc.normalized["cash_max_inr"].astext, BigInteger).label("cash_max_inr"),
            models.MatchScore.score,
            models.MatchScore.eligible,
        )
        .outerjoin(company, company_on)
        .outerjoin(role, role_on)
        .outerjoin(dl, dl_on)
        .outerjoin(ctc, ctc_on)
        .outerjoin(models.MatchScore, models.MatchScore.posting_id == P.id)
    )
    if status:
        stmt = stmt.where(P.status == status)
    if sort == "score":
        stmt = stmt.order_by(models.MatchScore.score.desc().nulls_last(), upcoming_first, deadline)
    else:
        stmt = stmt.order_by(upcoming_first, deadline, P.created_at.desc())

    rows = (await session.execute(stmt)).mappings().all()
    return [
        PostingSummary(**row, badge=scores.badge(row["eligible"], row["deadline"], now))
        for row in rows
    ]


# --- helpers ---------------------------------------------------------------------------


async def _id_by_hash(session: AsyncSession, digest: str) -> uuid.UUID | None:
    return await session.scalar(
        select(models.Posting.id).where(models.Posting.content_hash == digest)
    )


async def _get(session: AsyncSession, posting_id: uuid.UUID) -> models.Posting:
    posting = await session.get(models.Posting, posting_id)
    if posting is None:
        raise NotFound("posting")
    return posting


def _apply_result(posting: models.Posting, result: PipelineResult, now: datetime) -> None:
    posting.status = result.status
    posting.status_reason = result.status_reason
    posting.schema_version = result.schema_version
    posting.prompt_version = result.prompt_version
    posting.model_name = result.model_name
    posting.processed_at = now


async def _save_children(
    session: AsyncSession, posting_id: uuid.UUID, result: PipelineResult, now: datetime
) -> None:
    session.add_all(
        models.ExtractedField(
            posting_id=posting_id,
            field_name=f.field_name,
            mention_index=f.mention_index,
            raw_value=f.raw_value,
            evidence=f.evidence,
            evidence_verified=f.evidence_verified,
            normalized=f.normalized,
            flag=f.flag,
            flag_reason=f.flag_reason,
        )
        for f in result.fields
    )
    session.add_all(
        models.LLMCall(
            posting_id=posting_id,
            attempt=c.attempt,
            prompt_version=c.prompt_version,
            model=c.model,
            latency_ms=c.latency_ms,
            input_tokens=c.input_tokens,
            output_tokens=c.output_tokens,
            raw_response=c.raw_response,
            parse_ok=c.parse_ok,
            error=c.error,
        )
        for c in result.calls
    )
    await session.flush()
    profile = await scores.get_profile(session)
    await scores.save_score(session, posting_id, profile, result.fields, now)


def _mention(name: str) -> tuple[Any, ColumnElement[bool]]:
    """An aliased extracted_fields row for mention 0 of `name`, and its join condition."""
    ef = aliased(models.ExtractedField, name=f"f_{name}")
    on = and_(
        ef.posting_id == models.Posting.id,
        ef.field_name == name,
        ef.mention_index == 0,
        ef.flag == "none",
    )
    return ef, on


def _field_out(row: models.ExtractedField) -> FieldOut:
    verified = row.evidence_verified
    return FieldOut(
        field_name=row.field_name,
        mention_index=row.mention_index,
        value=row.raw_value if verified else None,  # never show an unverified value
        evidence=row.evidence if verified else None,
        evidence_verified=verified,
        normalized=row.normalized,
        flag=row.flag,  # type: ignore[arg-type]
        flag_reason=row.flag_reason,
    )


def _deadline(rows: list[models.ExtractedField]) -> datetime | None:
    for r in rows:
        if r.field_name == "application_deadline" and r.flag == "none" and r.normalized:
            return datetime.fromisoformat(r.normalized["iso"])
    return None


def _score_out(score: models.MatchScore, deadline: datetime | None, now: datetime) -> ScoreOut:
    return ScoreOut(
        score=score.score,
        eligible=score.eligible,
        badge=scores.badge(score.eligible, deadline, now),
        breakdown=score.breakdown,
        computed_at=score.computed_at,
    )
