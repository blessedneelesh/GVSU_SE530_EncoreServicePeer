"""Profile routes: view and edit your own profile, view someone else's public profile."""
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.db.session import get_db
from app.models.user import User
from app.schemas.user import UserPublic, UserResponse, UserUpdate

router = APIRouter(prefix="/users", tags=["users"])

# The /me routes must be declared before /{user_id}. FastAPI matches routes in
# order, and "me" would otherwise be tried as a user_id (and fail as a UUID).


@router.get("/me", response_model=UserResponse)
def read_me(current_user: User = Depends(get_current_user)) -> User:
    return current_user


@router.patch("/me", response_model=UserResponse)
def update_me(
    payload: UserUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> User:
    # exclude_unset: fields the client didn't send stay as they are.
    # exclude_none: an explicit null also means "no change", because name and bio
    # are NOT NULL columns. Send "" to clear a bio.
    for field, value in payload.model_dump(exclude_unset=True, exclude_none=True).items():
        setattr(current_user, field, value)
    db.commit()
    db.refresh(current_user)
    return current_user


@router.get("/{user_id}", response_model=UserPublic)
def read_user(user_id: UUID, db: Session = Depends(get_db)) -> User:
    # UUID so malformed ids get a 422 before any DB query; str() for the String(36) column.
    user = db.get(User, str(user_id))
    # Deactivated accounts look the same as missing ones.
    if user is None or not user.is_active:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    return user