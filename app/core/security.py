import hashlib
import os
import secrets
import uuid
from datetime import datetime, timedelta, timezone

import jwt
from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError
from dotenv import load_dotenv

load_dotenv()

# TODO: move these into core/config.py once it exists
SECRET_KEY = os.getenv("JWT_SECRET_KEY")

if not SECRET_KEY:
    raise ValueError("JWT_SECRET_KEY environment variable is not set")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", 15))
REFRESH_TOKEN_EXPIRE_DAYS = int(os.getenv("REFRESH_TOKEN_EXPIRE_DAYS", 7))

_hasher = PasswordHasher() # argon2id with the librarys recommended defaults


class TokenError(Exception):
    """ Raised when a token is missing claims, has a bad signature, or is expired. """

def utcnow() -> datetime:
    """ Current UTC time without tzinfo, to match the naive DateTime columns in the models. """
    return datetime.now(timezone.utc).replace(tzinfo=None)

### Passwords
def hash_password(password: str) -> str:
    """ Hash a plaintext password for users.password_hash. """
    return _hasher.hash(password)

def verify_password(password: str, password_hash: str) -> bool:
    """ Check a login attempt against a stored hash. Never raises on a bad password. """
    try:
        return _hasher.verify(password_hash, password)
    except (InvalidHashError, VerificationError):
        return False

### Access Tokens

def create_access_token(user_id: str, roles: list[str]) -> str:
    """ Short-lived JWT sent as 'Authorization: Bearer <token>'. 
    jti is a uuid4 string (36 chars) so it fits revoked_tokens.jti on logout."""
    now = datetime.now(timezone.utc)
    payload = {
        "sub": user_id,
        "roles": roles,
        "jti": str(uuid.uuid4()),
        "type": "access",
        "iat": now,
        "exp": now + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES),
    }
    return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)

def decode_access_token(token: str) -> dict:
    """ Verify a signature and expiry and return the payload, or raise TokenError."""
    try:
        payload = jwt.decode(
            token,
            SECRET_KEY,
            algorithms=[ALGORITHM],
            options={"require": ["exp", "jti", "sub"]},
        )
    except jwt.PyJWTError as exc:
        raise TokenError("Invalid or expired token") from exc
    if payload.get("type") != "access":
        raise TokenError("Not an access token")
    return payload


### Refresh Tokens
# Refresh tokens are random strings, not JWTs. The client keeps the raw value
# The database stores only its SHA-256 hash. SHA-256 (not argon2) is deliberate:
    # the token is 256 bits of randomness, so it cant be brute-forced, and the hash 
    # has to be deterministic so we can look it up by refresh_tokens.token_hash.

def create_refresh_token() -> tuple[str, str]:
    """ Return (raw_token, token_hash). Send raw_token to the client, store token_hash."""
    raw_token = secrets.token_urlsafe(32)
    return raw_token, hash_refresh_token(raw_token)

def hash_refresh_token(raw_token: str) -> str:
    """ Return the SHA-256 hash of a refresh token. """
    return hashlib.sha256(raw_token.encode()).hexdigest()

def refresh_token_expiry() -> datetime:
    """ Naive UTC expiry for refresh_tokens.expires_at."""
    return utcnow() + timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS)

