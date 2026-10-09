import uuid
from datetime import date, datetime
from sqlalchemy import String, Boolean, Date, DateTime, Text
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy import text
from app.db.base import Base

class User(Base):
    __tablename__ = "users"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    username: Mapped[str] = mapped_column(String(50), unique=True, nullable=False)
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, server_default=text("True"), nullable=False)
    bio: Mapped[str] = mapped_column(Text, server_default=text("''"), nullable=False)
    joined_date: Mapped[date] = mapped_column(Date, nullable=False)
    last_login_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)