"""Request and response schemas for users and authentication. 

Input schemas use extra="forbid", so a request that sneaks in fields like 
"id" or "is_active" is rejected with 422 instead of being silently ignored. 
No response schema has a password_hash field, so it can never be serialized.
"""

from datetime import date
from typing import Annotated

from pydantic import BaseModel, ConfigDict, EmailStr, Field, StringConstraints, field_validator

# Lengths match the String(...) columns in app/models/user.py
Name = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=100)]
Username = Annotated[
    str,
    StringConstraints(strip_whitespace=True, min_length=3, max_length=50, pattern=r"^[A-Za-z0-9_]+$"),
]
Bio = Annotated[str, StringConstraints(strip_whitespace=True, max_length=500)]

# 128 max keeps someone from making the server hash a megabyte-long "password"
Password = Annotated[str, Field(min_length=8, max_length=128)]

class _Input(BaseModel):
    model_config = ConfigDict(extra="forbid")


# Inputs

class UserCreate(_Input):
    name: Name
    username: Username
    email: EmailStr
    password: Password

    @field_validator("email")
    @classmethod
    def lowercase_email(cls, v: str) -> str:
        return v.lower()

    @field_validator("password")
    @classmethod
    def password_complexity(cls, v: str) -> str:
        missing = []
        if not any(c.islower() for c in v):
            missing.append("a lowercase letter")
        if not any(c.isupper() for c in v):
            missing.append("a uppercase letter")
        if not any(c.isdigit() for c in v):
            missing.append("a number")
        if missing:
            raise ValueError(f"Password must contain " + ", ".join(missing))
        return v

class UserLogin(_Input):
    # No complexity check here: a login only has to match the stored hash, 
    # and validating it would reveal the password rules to anyone guessing.
    email: EmailStr
    password: str = Field(min_length=1, max_length=128)

    @field_validator("email")
    @classmethod
    def lowercase_email(cls, v: str) -> str:
        return v.lower()

class UserUpdate(_Input):
    """Profile edits. Only the field sent are changed (use exclude_unset=True)."""
    name: Name | None = None
    bio: Bio | None = None


# outputs

class UserPublic(BaseModel):
    """ What other users can see, e.g. comment authors and attendee lists."""

    model_config = ConfigDict(from_attributes=True)

    id: str
    name: str
    username: str
    bio: str
    joined_date: date

class UserResponse(UserPublic):
    """The logged=in user's own profile. Adds email, which strangers shouldn't see."""
    email: EmailStr

# tokens
class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"

class RefreshRequest(_Input):
    refresh_token: str = Field(min_length=1, max_length=255)
    