import uuid
from datetime import date
from sqlalchemy import String, Integer, Date, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy import CheckConstraint
from app.db.base import Base

class Invoice(Base):
    __tablename__ = "reservations"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    concert_id: Mapped[str] = mapped_column(String(36), ForeignKey("concerts.id", ondelete="CASCADE"), nullable=False, index=True)
    user_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index = True)
    seats: Mapped[int] = mapped_column(Integer, nullable=False)
    created_at: Mapped[date] = mapped_column(Date, nullable=False)

    __table_args__ = (
        CheckConstraint("seats > 0 AND seats <= 4", name="chk_seats_limit"),
    )