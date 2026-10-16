from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field, field_validator

class ConcertCreate(BaseModel):
    title: str
    venue: str
    city: str
    state: str
    date: datetime
    time: str
    capacity: int = Field(gt=0, description="Total seating capacity must be greater than 0.")
    mood: str
    
    # Optional fields that are nullable in the database model
    description: Optional[str] = None
    genre: Optional[str] = None
    image_url: Optional[str] = None

    @field_validator('mood')
    @classmethod
    def validate_mood(cls, v: str) -> str:
        allowed_moods = {"Sad", "Angry", "Happy"}
        if v not in allowed_moods:
            raise ValueError(f"Mood must be exactly one of: 'Sad', 'Angry', or 'Happy'. Received: '{v}'")
        return v