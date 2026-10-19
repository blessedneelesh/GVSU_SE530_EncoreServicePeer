from uuid import UUID
from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session
from app.api.deps import get_current_user
from app.db.session import get_db
from app.models.user import User
from app.models.concert import Concert
from app.models.invoice import Invoice
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

@router.get("/concerts/{concert_id}/attendees", status_code=status.HTTP_200_OK)
def get_concert_attendees(concert_id: UUID, db: Session = Depends(get_db)):
    """
    1) Get users who reserved a specific concert.
    Joins the User and Invoice tables to return the attendee's info and how many seats they booked.
    """
    results = (
        db.query(User.id, User.username, User.email, Invoice.seats)
        .join(Invoice, User.id == Invoice.user_id)
        .filter(Invoice.concert_id == str(concert_id))
        .all()
    )
    
    # Format the response cleanly for the frontend
    return [
        {
            "user_id": row.id, 
            "username": row.username, 
            "email": row.email, 
            "seats": row.seats
        } 
        for row in results
    ]


@router.get("/users/me/reservations", status_code=status.HTTP_200_OK)
def get_my_reservations(
    db: Session = Depends(get_db), 
    current_user: User = Depends(get_current_user)
):
    """
    2) Get concert details joined with reservation details for the logged-in user.
    Powers the 'My Reservations' tab in the frontend.
    """
    results = (
        db.query(Invoice.seats, Invoice.created_at, Concert)
        .join(Concert, Invoice.concert_id == Concert.id)
        .filter(Invoice.user_id == current_user.id)
        .all()
    )
    
    # Packages the reservation metadata alongside the full concert object
    return [
        {
            "seats": row.seats,
            "reservation_date": row.created_at,
            "concert": row.Concert
        }
        for row in results
    ]
