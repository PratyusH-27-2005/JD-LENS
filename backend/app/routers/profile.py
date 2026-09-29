from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_session
from app.deps import get_now
from app.schemas.api import ErrorResponse, ProfileIn, ProfileOut
from app.services import scores

router = APIRouter(prefix="/profile", tags=["profile"])

Session = Annotated[AsyncSession, Depends(get_session)]


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
