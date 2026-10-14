from datetime import UTC, datetime
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.db.session import get_db
from app.models.comment import Comment
from app.models.concert import Concert
from app.models.user import User
from app.schemas.comment import CommentCreate, CommentRead

router = APIRouter(tags=["comments"])

# concert_id is typed UUID so malformed ids get a 422 before any DB query runs.
# It is converted back to str for the DB, whose id columns are String(36).


def _ensure_concert_exists(db: Session, concert_id: UUID) -> None:
    if db.get(Concert, str(concert_id)) is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Concert not found")


def _to_read(comment: Comment, username: str) -> CommentRead:
    return CommentRead(
        id=comment.id,
        concert_id=comment.concert_id,
        user_id=comment.user_id,
        username=username,
        text=comment.text,
        created_at=comment.created_at,
    )


@router.post(
    "/concerts/{concert_id}/comments",
    response_model=CommentRead,
    status_code=status.HTTP_201_CREATED,
)
def create_comment(
    concert_id: UUID,
    payload: CommentCreate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> CommentRead:
    # Cancelled/past concerts are allowed on purpose: the thread stays open after the show.
    _ensure_concert_exists(db, concert_id)
    comment = Comment(
        concert_id=str(concert_id),
        user_id=user.id,  # identity comes from auth only, never from the request body
        text=payload.text,
        # Server-set timestamp. Stored naive because the column is naive; by convention it is UTC.
        created_at=datetime.now(UTC).replace(tzinfo=None),
    )
    db.add(comment)
    db.commit()
    return _to_read(comment, user.username)


@router.get("/concerts/{concert_id}/comments", response_model=list[CommentRead])
def list_comments(
    concert_id: UUID,
    db: Session = Depends(get_db),
    # Bounded so one request can't dump a whole thread (limit) or make Postgres scan and
    # discard millions of rows / overflow BIGINT (offset).
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0, le=10_000),
) -> list[CommentRead]:
    _ensure_concert_exists(db, concert_id)
    rows = db.execute(
        select(Comment, User.username)
        .join(User, Comment.user_id == User.id)
        .where(Comment.concert_id == str(concert_id))
        # Newest first. id breaks timestamp ties so the order is deterministic and
        # limit/offset pages never skip or repeat a comment.
        .order_by(Comment.created_at.desc(), Comment.id.desc())
        .limit(limit)
        .offset(offset)
    )
    return [_to_read(comment, username) for comment, username in rows]
