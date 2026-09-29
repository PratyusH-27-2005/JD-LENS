import uuid
from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Depends, Request, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.db import get_session
from app.deps import get_now
from app.llm.client import get_llm_client
from app.llm.types import LLMClient
from app.ratelimit import limiter
from app.schemas.api import ErrorResponse, PostingCreate, PostingDetail, PostingSummary, Status
from app.services import postings as svc

router = APIRouter(prefix="/postings", tags=["postings"])

Session = Annotated[AsyncSession, Depends(get_session)]
LLM = Annotated[LLMClient, Depends(get_llm_client)]
Now = Annotated[datetime, Depends(get_now)]
ERRORS = {
    404: {"model": ErrorResponse},
    422: {"model": ErrorResponse},
    429: {"model": ErrorResponse},
}


@router.post(
    "",
    status_code=status.HTTP_201_CREATED,
    response_model=PostingDetail,
    responses={200: {"description": "Same text already stored: the existing posting"}} | ERRORS,
)
@limiter.limit(lambda: get_settings().rate_limit_postings)
async def create_posting(
    request: Request,  # slowapi keys the limit on the client IP
    response: Response,
    body: PostingCreate,
    session: Session,
    llm: LLM,
    now: Now,
) -> PostingDetail:
    """Save the posting, run the pipeline and score it. An LLM outage still saves the
    posting (status needs_review, reason llm_unavailable) so it can be reprocessed."""
    posting_id, created = await svc.create_posting(
        session, body.raw_text, body.source_label, llm, now
    )
    if not created:
        response.status_code = status.HTTP_200_OK
    return await svc.get_detail(session, posting_id, now)


@router.get("", response_model=list[PostingSummary], responses=ERRORS)
async def list_postings(
    session: Session,
    now: Now,
    status: Status | None = None,
    sort: svc.Sort = "deadline",
) -> list[PostingSummary]:
    return await svc.list_summaries(session, status, sort, now)


@router.get("/{posting_id}", response_model=PostingDetail, responses=ERRORS)
async def get_posting(posting_id: uuid.UUID, session: Session, now: Now) -> PostingDetail:
    return await svc.get_detail(session, posting_id, now)


@router.post("/{posting_id}/reprocess", response_model=PostingDetail, responses=ERRORS)
async def reprocess_posting(
    posting_id: uuid.UUID, session: Session, llm: LLM, now: Now
) -> PostingDetail:
    await svc.reprocess_posting(session, posting_id, llm, now)
    return await svc.get_detail(session, posting_id, now)


@router.delete("/{posting_id}", status_code=status.HTTP_204_NO_CONTENT, responses=ERRORS)
async def delete_posting(posting_id: uuid.UUID, session: Session) -> Response:
    await svc.delete_posting(session, posting_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
