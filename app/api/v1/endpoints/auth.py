"""Session routes: register, login, refresh, logout.

Token model:
- Access token: short-lived JWT (see core/security.py), sent as "Authorization: Bearer <token>".
- Refresh token: random string the client keeps; only its SHA-256 hash is stored.
  Each refresh rotates it (old one revoked, new one issued). If a revoked refresh
  token is ever presented again, it was probably stolen, so every refresh token
  for that user is revoked and they have to log in again.
"""
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from fastapi.security import HTTPAuthorizationCredentials
from sqlalchemy import select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.api.deps import bearer_scheme, get_current_user
from app.core.security import (
    create_access_token,
    create_refresh_token,
    decode_access_token,
    hash_password,
    hash_refresh_token,
    refresh_token_expiry,
    utcnow,
    verify_password,
)
from app.db.session import get_db
from app.models.auth import RefreshToken, RevokedToken, Role, UserRole
from app.models.user import User
from app.schemas.user import RefreshRequest, TokenResponse, UserCreate, UserLogin, UserResponse

router = APIRouter(prefix="/auth", tags=["auth"])

# Checked against when the email doesn't exist, so a login for an unknown email
# takes as long as one with a wrong password. Without it, response time alone
# would reveal which emails have accounts.
_DUMMY_HASH = hash_password("timing-equalizer-not-a-real-password")

_INVALID_LOGIN = HTTPException(
    status_code=status.HTTP_401_UNAUTHORIZED,
    detail="Invalid email or password",
    headers={"WWW-Authenticate": "Bearer"},
)
_INVALID_REFRESH = HTTPException(
    status_code=status.HTTP_401_UNAUTHORIZED,
    detail="Invalid or expired refresh token",
    headers={"WWW-Authenticate": "Bearer"},
)


def _role_names(db: Session, user_id: str) -> list[str]:
    stmt = select(Role.name).join(UserRole, UserRole.role_id == Role.id).where(UserRole.user_id == user_id)
    return list(db.scalars(stmt))


def _issue_tokens(db: Session, user: User, request: Request) -> TokenResponse:
    """Create an access token and a stored refresh token. Caller commits."""
    raw_refresh, refresh_hash = create_refresh_token()
    db.add(RefreshToken(
        user_id=user.id,
        token_hash=refresh_hash,
        expires_at=refresh_token_expiry(),
        created_at=utcnow(),
        user_agent=(request.headers.get("user-agent") or "")[:255] or None,
    ))
    return TokenResponse(
        access_token=create_access_token(user.id, _role_names(db, user.id)),
        refresh_token=raw_refresh,
    )


@router.post("/register", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
def register(payload: UserCreate, db: Session = Depends(get_db)) -> User:
    if db.scalar(select(User.id).where(User.email == payload.email)):
        raise HTTPException(status.HTTP_409_CONFLICT, detail="Email is already registered")
    if db.scalar(select(User.id).where(User.username == payload.username)):
        raise HTTPException(status.HTTP_409_CONFLICT, detail="Username is already taken")

    user = User(
        name=payload.name,
        username=payload.username,
        email=payload.email,
        password_hash=hash_password(payload.password),
        joined_date=utcnow().date(),
    )
    db.add(user)
    try:
        db.commit()
    except IntegrityError:
        # Two signups with the same email/username raced past the checks above;
        # the unique constraints caught the second one.
        db.rollback()
        raise HTTPException(status.HTTP_409_CONFLICT, detail="Email or username is already taken")
    db.refresh(user)  # load server defaults (is_active, bio)
    return user


@router.post("/login", response_model=TokenResponse)
def login(payload: UserLogin, request: Request, db: Session = Depends(get_db)) -> TokenResponse:
    user = db.scalar(select(User).where(User.email == payload.email))
    if user is None:
        verify_password(payload.password, _DUMMY_HASH)
        raise _INVALID_LOGIN
    if not verify_password(payload.password, user.password_hash) or not user.is_active:
        raise _INVALID_LOGIN

    user.last_login_at = utcnow()
    tokens = _issue_tokens(db, user, request)
    db.commit()
    return tokens


@router.post("/refresh", response_model=TokenResponse)
def refresh(payload: RefreshRequest, request: Request, db: Session = Depends(get_db)) -> TokenResponse:
    # FOR UPDATE locks the row, so two simultaneous refreshes with the same token
    # can't both succeed: the second waits, then sees revoked=True.
    stored = db.scalar(
        select(RefreshToken)
        .where(RefreshToken.token_hash == hash_refresh_token(payload.refresh_token))
        .with_for_update()
    )
    if stored is None:
        raise _INVALID_REFRESH

    if stored.revoked:
        # Reuse of a rotated-out token: assume it leaked and end every session.
        db.execute(
            update(RefreshToken).where(RefreshToken.user_id == stored.user_id).values(revoked=True)
        )
        db.commit()
        raise _INVALID_REFRESH

    user = db.get(User, stored.user_id)
    if stored.expires_at <= utcnow() or user is None or not user.is_active:
        raise _INVALID_REFRESH

    stored.revoked = True
    tokens = _issue_tokens(db, user, request)
    db.commit()
    return tokens


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
def logout(
    payload: RefreshRequest,
    current_user: User = Depends(get_current_user),
    credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme),
    db: Session = Depends(get_db),
) -> Response:
    # get_current_user already validated this token; decode again only to read jti/exp.
    claims = decode_access_token(credentials.credentials)
    db.add(RevokedToken(
        jti=claims["jti"],
        user_id=current_user.id,
        expires_at=datetime.fromtimestamp(claims["exp"], UTC).replace(tzinfo=None),
        revoked_at=utcnow(),
    ))
    # Only revoke the refresh token if it belongs to this user. An unknown token is
    # ignored rather than reported, so logout always succeeds once authenticated.
    db.execute(
        update(RefreshToken)
        .where(
            RefreshToken.token_hash == hash_refresh_token(payload.refresh_token),
            RefreshToken.user_id == current_user.id,
        )
        .values(revoked=True)
    )
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)