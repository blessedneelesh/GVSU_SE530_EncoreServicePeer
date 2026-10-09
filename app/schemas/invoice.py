from pydantic import BaseModel, Field

class ReservationCreate(BaseModel):
    # Notice concert_id is intentionally missing here per the teammate's request!
    seats: int = Field(
        ge=1, 
        le=4, 
        description="A user can only reserve between 1 and 4 seats per request."
    )