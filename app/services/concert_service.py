from sqlalchemy.orm import Session
from fastapi import HTTPException, status
from app.models.concert import Concert

def get_concert_by_id(db: Session, concert_id: str):
    """Fetches a concert by its UUID."""
    concert = db.query(Concert).filter(Concert.id == concert_id).first()
    if not concert:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Concert not found.")
    return concert

def cancel_concert(db: Session, concert_id: str, current_user_id: str):
    """
    Cancels a concert. Enforces that only the owner can cancel it.
    """
    concert = get_concert_by_id(db, concert_id)

    # Business Rule: Only the owner can cancel the concert
    if concert.owner_id != current_user_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, 
            detail="You do not have permission to cancel this concert."
        )

    # Business Rule: Prevent redundant cancellations (409 Conflict)
    if concert.cancelled:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, 
            detail="Concert is already cancelled."
        )

    # Update the database
    concert.cancelled = True
    db.commit()
    db.refresh(concert)
    
    return concert