from sqlalchemy.orm import Session
from sqlalchemy import func
from fastapi import HTTPException, status
from app.models.concert import Concert
from app.models.invoice import Invoice  # Reservation

def create_reservation(db: Session, concert_id: str, user_id: str, seats: int):
    """
    Safely creates a reservation, checking capacity and seat limits.
    Uses 'with_for_update()' to lock the row and prevent race conditions.
    """
    # 1. Syntax check: Max 4 seats per transaction
    if seats < 1 or seats > 4:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, 
            detail="You can only reserve between 1 and 4 seats per request."
        )

    # 2. Scalper check: Limit 4 total seats per user per show
    existing_seats = db.query(func.sum(Invoice.seats)).filter(
        Invoice.concert_id == concert_id,
        Invoice.user_id == user_id
    ).scalar() or 0  # .scalar() returns None if no rows exist, default to 0

    if existing_seats + seats > 4:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Limit 4 tickets per user. You already have {existing_seats} tickets for this show."
        )

    # 3. Lock the specific concert row so no one else can book at the exact same time
    concert = db.query(Concert).filter(Concert.id == concert_id).with_for_update().first()
    
    if not concert:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, 
            detail="Concert not found."
        )

    # 4. Business Rule: Cannot book a cancelled show (409 Conflict)
    if concert.cancelled:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, 
            detail="This concert has been cancelled."
        )

    # 5. Business Rule: Check capacity (409 Conflict)
    if concert.reserved_count + seats > concert.capacity:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, 
            detail=f"Not enough seats available. Only {concert.capacity - concert.reserved_count} left."
        )

    # 6. Create the reservation
    new_reservation = Invoice(
        concert_id=concert_id,
        user_id=user_id,
        seats=seats
    )

    # 7. Increment the reserved count on the concert
    concert.reserved_count += seats

    # 8. Commit both the new reservation and the updated concert capacity as a single transaction
    db.add(new_reservation)
    db.commit()
    db.refresh(new_reservation)
    
    return new_reservation