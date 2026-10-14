from datetime import date

from pydantic import BaseModel, ConfigDict, Field

class ReservationCreate(BaseModel):
    # Notice concert_id is intentionally missing here per the teammate's request!
    seats: int = Field(
        ge=1, 
        le=4, 
        description="A user can only reserve between 1 and 4 seats per request."
    )

class ReservationRead(BaseModel):
    """Public view of a reservation: an explicit allowlist of fields."""

    # Lets FastAPI build this straight from the Invoice ORM object the service returns.
    model_config = ConfigDict(from_attributes=True)

    id: str
    concert_id: str
    seats: int
    created_at: date
