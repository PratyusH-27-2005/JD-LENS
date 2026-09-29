"""The five tables. Schema changes go through Alembic migrations, never create_all.

No ORM relationships on purpose: lazy loading fails under asyncio, so services query
child rows explicitly, and ON DELETE CASCADE in the database removes them.
"""

import uuid
from datetime import datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Identity,
    Integer,
    MetaData,
    Numeric,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import ARRAY, JSONB, UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

# Deterministic constraint names, so migrations can refer to them.
NAMING = {
    "ix": "ix_%(table_name)s_%(column_0_name)s",
    "uq": "uq_%(table_name)s_%(column_0_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}

STATUSES = ("pending", "verified", "partial", "needs_review")
FLAGS = ("none", "ambiguous", "conflict", "unverified", "missing")


def _in(column: str, values: tuple[str, ...]) -> str:
    return f"{column} IN ({', '.join(repr(v) for v in values)})"


class Base(DeclarativeBase):
    metadata = MetaData(naming_convention=NAMING)


class Profile(Base):
    __tablename__ = "profile"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(Text, default="")
    skills: Mapped[list[str]] = mapped_column(ARRAY(Text), default=list)
    cgpa: Mapped[Decimal | None] = mapped_column(Numeric(4, 2))
    has_backlogs: Mapped[bool | None] = mapped_column(Boolean)
    preferred_locations: Mapped[list[str]] = mapped_column(ARRAY(Text), default=list)
    min_cash_inr: Mapped[int | None] = mapped_column(Integer)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    __table_args__ = (
        CheckConstraint("cgpa >= 0 AND cgpa <= 10", name="cgpa_range"),
        CheckConstraint("min_cash_inr >= 0", name="min_cash_nonnegative"),
    )


class Posting(Base):
    __tablename__ = "postings"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    raw_text: Mapped[str] = mapped_column(Text)
    clean_text: Mapped[str] = mapped_column(Text)
    content_hash: Mapped[str] = mapped_column(Text, unique=True)
    source_label: Mapped[str | None] = mapped_column(Text)
    status: Mapped[str] = mapped_column(Text, default="pending")
    status_reason: Mapped[str | None] = mapped_column(Text)
    schema_version: Mapped[str | None] = mapped_column(Text)
    prompt_version: Mapped[str | None] = mapped_column(Text)
    model_name: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    processed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    __table_args__ = (CheckConstraint(_in("status", STATUSES), name="status_valid"),)


class ExtractedField(Base):
    __tablename__ = "extracted_fields"

    id: Mapped[int] = mapped_column(BigInteger, Identity(), primary_key=True)
    # No separate index: uq_field_mention starts with posting_id and serves those lookups.
    posting_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("postings.id", ondelete="CASCADE"))
    field_name: Mapped[str] = mapped_column(Text)
    mention_index: Mapped[int] = mapped_column(Integer, default=0)
    raw_value: Mapped[str | None] = mapped_column(Text)
    evidence: Mapped[str | None] = mapped_column(Text)
    evidence_verified: Mapped[bool] = mapped_column(Boolean)
    normalized: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    flag: Mapped[str] = mapped_column(Text, default="none")
    flag_reason: Mapped[str | None] = mapped_column(Text)

    __table_args__ = (
        UniqueConstraint("posting_id", "field_name", "mention_index", name="uq_field_mention"),
        CheckConstraint(_in("flag", FLAGS), name="flag_valid"),
    )


class MatchScore(Base):
    __tablename__ = "match_scores"

    posting_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("postings.id", ondelete="CASCADE"), primary_key=True
    )
    profile_id: Mapped[int] = mapped_column(ForeignKey("profile.id", ondelete="CASCADE"))
    score: Mapped[int | None] = mapped_column(Integer)
    eligible: Mapped[bool | None] = mapped_column(Boolean)
    breakdown: Mapped[dict[str, Any]] = mapped_column(JSONB)
    computed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    __table_args__ = (CheckConstraint("score BETWEEN 0 AND 100", name="score_range"),)


class LLMCall(Base):
    __tablename__ = "llm_calls"

    id: Mapped[int] = mapped_column(BigInteger, Identity(), primary_key=True)
    posting_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("postings.id", ondelete="CASCADE"), index=True
    )
    attempt: Mapped[int] = mapped_column(Integer)
    prompt_version: Mapped[str] = mapped_column(Text)
    model: Mapped[str] = mapped_column(Text)
    latency_ms: Mapped[int | None] = mapped_column(Integer)
    input_tokens: Mapped[int | None] = mapped_column(Integer)
    output_tokens: Mapped[int | None] = mapped_column(Integer)
    raw_response: Mapped[str | None] = mapped_column(Text)
    parse_ok: Mapped[bool] = mapped_column(Boolean)
    error: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
