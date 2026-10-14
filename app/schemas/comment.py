from datetime import UTC, datetime
from typing import Annotated

from pydantic import BaseModel, ConfigDict, StringConstraints, field_validator

# Stripped first, then length-checked, so "   " is rejected as empty. The pattern
# rejects NUL (\x00): Postgres TEXT cannot store it and would otherwise raise a 500.
CommentText = Annotated[
    str,
    StringConstraints(strip_whitespace=True, min_length=1, max_length=1000, pattern=r"^[^\x00]*$"),
]


class CommentCreate(BaseModel):
    # extra="forbid": a body carrying user_id/created_at/id is rejected (422) instead of
    # silently ignored, so clients can't even attempt to set server-owned fields.
    model_config = ConfigDict(extra="forbid")

    text: CommentText


class CommentRead(BaseModel):
    """Public view of a comment. An explicit allowlist: no author email or other PII."""

    id: str
    concert_id: str
    user_id: str
    username: str
    text: str
    created_at: datetime

    @field_validator("created_at")
    @classmethod
    def mark_as_utc(cls, value: datetime) -> datetime:
        # The DB column is naive but always holds UTC (team convention). Attaching the
        # zone makes the JSON end in "Z", so clients don't misread it as local time.
        return value.replace(tzinfo=UTC) if value.tzinfo is None else value
