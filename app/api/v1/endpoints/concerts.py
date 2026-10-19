from datetime import date
from uuid import UUID
from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session
from typing import Optional
from app.api.deps import get_current_user
from app.db.session import get_db
from app.models.concert import Concert
from app.models.user import User
from app.schemas.concert import ConcertCreate
from app.services.concert_service import get_concert_by_id, cancel_concert
from app.services.integrations.weather import get_weather_for_venue

router = APIRouter(prefix="/concerts", tags=["concerts"])


@router.post("/", status_code=status.HTTP_201_CREATED)
def create_concert(
    payload: ConcertCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Create a new concert with the authenticated user as the owner."""
    concert = Concert(
        **payload.model_dump(),
        owner_id=current_user.id,
        created_at=date.today(),  # Fixes the created_at NOT NULL constraint violation
    )
    db.add(concert)
    db.commit()
    db.refresh(concert)
    return concert


@router.get("/", status_code=status.HTTP_200_OK)
def list_concerts(
    owner_id: Optional[UUID] = None, 
    db: Session = Depends(get_db)
):
    """List all concerts, optionally filtered by the host's user ID."""
    query = db.query(Concert)
    
    if owner_id:
        query = query.filter(Concert.owner_id == str(owner_id))
        
    return query.all()


@router.get("/{concert_id}", status_code=status.HTTP_200_OK)
def read_concert(concert_id: UUID, db: Session = Depends(get_db)):
    """Fetch a specific concert by ID."""
    return get_concert_by_id(db=db, concert_id=str(concert_id))


@router.patch("/{concert_id}/cancel", status_code=status.HTTP_200_OK)
def cancel_existing_concert(
    concert_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Cancel a concert (only the concert owner is authorized)."""
    return cancel_concert(
        db=db,
        concert_id=str(concert_id),
        current_user_id=current_user.id,
    )


@router.get("/{concert_id}/location-weather", status_code=status.HTTP_200_OK)
async def read_concert_location_and_weather(
    concert_id: UUID,
    db: Session = Depends(get_db),
):
    """Fetch Google Maps link, coordinates, and live weather for a concert's venue."""
    concert = get_concert_by_id(db=db, concert_id=str(concert_id))
    venue_query = getattr(concert, "location", None) or getattr(concert, "venue", "")
    return await get_weather_for_venue(venue_query)