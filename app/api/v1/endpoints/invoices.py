from uuid import UUID

from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.db.session import get_db
from app.models.user import User
from app.schemas.invoice import ReservationCreate, ReservationRead
from app.services.reservation_service import create_reservation

router = APIRouter(tags=["reservations"])


@router.post(
    "/concerts/{concert_id}/reservations",
    response_model=ReservationRead,
    status_code=status.HTTP_201_CREATED,
)
def reserve_seats(
    # UUID so malformed ids get a 422 before any DB query; str() for the String(36) columns.
    concert_id: UUID,
    payload: ReservationCreate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    # All business rules (row lock, sold out, cancelled, 4-per-user cap) live in the
    # service, which raises the matching HTTPException itself. The endpoint only supplies
    # the caller's identity, taken from auth and never from the request body.
    return create_reservation(db, str(concert_id), user.id, payload.seats)
