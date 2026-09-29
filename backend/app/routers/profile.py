import asyncio
from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Depends, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.db import get_session
from app.deps import get_now
from app.errors import ApiError
from app.llm.client import get_llm_client
from app.llm.types import LLMClient
from app.pipeline.pdf import PdfUnreadable, pdf_to_text
from app.pipeline.resume import read_resume
from app.pipeline.scoring import canonical_skill
from app.ratelimit import limiter
from app.schemas.api import (
    ErrorResponse,
    ProfileIn,
    ProfileOut,
    ResumeCgpa,
    ResumeImport,
    ResumeRejected,
    ResumeSkillOut,
    ResumeValue,
)
from app.services import scores

router = APIRouter(prefix="/profile", tags=["profile"])

Session = Annotated[AsyncSession, Depends(get_session)]

MAX_RESUME_BYTES = 5 * 1024 * 1024
MAX_RESUME_CHARS = 30_000


@router.get("", response_model=ProfileOut)
async def get_profile(session: Session) -> ProfileOut:
    profile = await scores.get_profile(session)
    await session.commit()  # keep the row if it was just created
    return ProfileOut.model_validate(profile)


@router.put("", response_model=ProfileOut, responses={422: {"model": ErrorResponse}})
async def put_profile(
    body: ProfileIn, session: Session, now: Annotated[datetime, Depends(get_now)]
) -> ProfileOut:
    """Replace the profile and rescore every posting in the same transaction."""
    profile = await scores.update_profile(session, body, now)
    return ProfileOut.model_validate(profile)


@router.post(
    "/resume",
    response_model=ResumeImport,
    responses={code: {"model": ErrorResponse} for code in (413, 415, 422, 429, 502, 503)},
)
@limiter.limit(lambda: get_settings().rate_limit_resume)
async def import_resume(
    request: Request, session: Session, llm: Annotated[LLMClient, Depends(get_llm_client)]
) -> ResumeImport:
    """Body: the PDF itself, `Content-Type: application/pdf`.

    Returns suggestions (name, CGPA, skills), each with a quote verified against the
    resume text. Nothing is stored: not the file, not its text, and the profile is not
    changed. The user reviews the suggestions and saves with PUT /profile.
    """
    content_type = request.headers.get("content-type", "").split(";")[0].strip().lower()
    if content_type != "application/pdf":
        raise ApiError(
            status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            "unsupported_media_type",
            "send the resume as a PDF (Content-Type: application/pdf)",
        )
    data = await _read_capped(request, MAX_RESUME_BYTES)
    try:
        text = await asyncio.to_thread(pdf_to_text, data)  # CPU work off the event loop
    except PdfUnreadable as e:
        raise ApiError(422, "resume_unreadable", str(e)) from e
    if len(text) > MAX_RESUME_CHARS:
        raise ApiError(422, "resume_too_long", "that's more text than a resume usually has")

    result = await read_resume(text, llm)
    if result.failure == "llm_unavailable":
        raise ApiError(503, "llm_unavailable", "the model couldn't be reached; try again shortly")
    if result.failure:
        raise ApiError(
            502, "extraction_invalid", "the model's answer failed validation twice", result.failure
        )

    profile = await scores.get_profile(session)
    have = {canonical_skill(s) for s in profile.skills or []}  # read before rollback expires it
    await session.rollback()  # read only: don't even create the profile row here
    return ResumeImport(
        name=ResumeValue(value=result.name.value, evidence=result.name.evidence)
        if result.name
        else None,
        cgpa=ResumeCgpa(value=result.cgpa.value, evidence=result.cgpa.evidence)
        if result.cgpa
        else None,
        skills=[
            ResumeSkillOut(
                value=s.value, evidence=s.evidence, new=canonical_skill(s.value) not in have
            )
            for s in result.skills
        ],
        rejected=[
            ResumeRejected(field=r.field, value=r.value, reason=r.reason) for r in result.rejected
        ],
        model_name=result.model_name,
        prompt_version=result.prompt_version,
        text_chars=len(text),
    )


async def _read_capped(request: Request, limit: int) -> bytes:
    """Read the body, refusing anything over `limit` without buffering all of it."""
    declared = request.headers.get("content-length")
    if declared and declared.isdigit() and int(declared) > limit:
        raise _too_large(limit)
    chunks, size = [], 0
    async for chunk in request.stream():
        size += len(chunk)
        if size > limit:
            raise _too_large(limit)
        chunks.append(chunk)
    return b"".join(chunks)


def _too_large(limit: int) -> ApiError:
    return ApiError(413, "file_too_large", f"the resume must be under {limit // (1024 * 1024)} MB")
