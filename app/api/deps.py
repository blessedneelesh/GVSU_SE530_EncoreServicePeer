"""Shared FastAPI dependencies for authentication and authorizatoin. 

Usage in an endopoint: 
    @router.post("/concerts")
    def create_concert(...., current_user: User = Depends(get_current_user)):
        ......
        
Any logged-in user can post a concert, so there is no role check here. 
Ownership checks (only the owner can edit or cancel) belong in the endpoint:
    if concert.owner_id != current_user.id: raise HTTPException(403, ....)
"""

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.core.security import TokenError, decode_access_token
from app.db.session import get_db
from app.models.auth import RevokedToken
from app.models.user import User

# auto_error=False so a missing header goes through our own 401 below
# (HTTPBearer's built-in error is 403 in some FastAPI versions).
bearer_scheme = HTTPBearer(auto_error=False)

def _unauthorized(detail: str = "Could not validate credentials") -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail=detail,
        headers={"WWW-Authenticate": "Bearer"},
    )

def get_current_user(
        credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
        db: Session = Depends(get_db),
) -> User:
    """ Return the logged-in user, or raise 401 if the token is missing, invalid, expired, revoked, or belongs to a missing or deactivated user. """
    if credentials is None:
        raise _unauthorized("Not authenticated")
    try:
        payload = decode_access_token(credentials.credentials)
    except TokenError:
        raise _unauthorized()
    if db.get(RevokedToken, payload["jti"]) is not None:
        raise _unauthorized("Token has been revoked")

    user = db.get(User, payload["sub"])
    if user is None or not user.is_active:
        raise _unauthorized()

    return user
    