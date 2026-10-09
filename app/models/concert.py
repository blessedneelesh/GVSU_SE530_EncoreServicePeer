import uuid
from datetime import date, time
from sqlalchemy import String, Integer, Boolean, Date, Time, Text, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy import CheckConstraint
from sqlalchemy import text
from app.db.base import Base

class Concert(Base):
    __tablename__ = "concerts"

    # Auto-generates a UUID string like "123e4567-e89b-12d3-a456-426614174000"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    venue: Mapped[str] = mapped_column(String(200), nullable=False)
    city: Mapped[str] = mapped_column(String(100), nullable=False)
    state: Mapped[str] = mapped_column(String(50), nullable=False)
    date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    time: Mapped[time] = mapped_column(Time, nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    genre: Mapped[str] = mapped_column(String(50), nullable=False)
    
    owner_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id", ondelete="RESTRICT"), nullable=False, index=True)
    
    capacity: Mapped[int] = mapped_column(Integer, nullable=False)
    reserved_count: Mapped[int] = mapped_column(Integer, server_default=text("0"), nullable=False)
    image_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    cancelled: Mapped[bool] = mapped_column(Boolean, server_default=text("false"), nullable=False)
    created_at: Mapped[date] = mapped_column(Date, nullable=False)
    mood: Mapped[str] = mapped_column(String(20), nullable=False)

    __table_args__ = (
        CheckConstraint("capacity > 0", name="chk_capacity_positive"),
        CheckConstraint("reserved_count >= 0 AND reserved_count <= capacity", name="chk_reserved_count"),
        CheckConstraint("mood IN ('Sad', 'Angry', 'Happy')", name="chk_mood_valid")
    )