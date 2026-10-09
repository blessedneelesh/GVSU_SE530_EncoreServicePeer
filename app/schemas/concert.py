from pydantic import BaseModel, field_validator
from datetime import datetime

class ConcertCreate(BaseModel):
    title: str
    venue: str
    date: datetime
    mood: str

    @field_validator('mood')
    @classmethod
    def validate_mood(cls, v: str) -> str:
        allowed_moods = {"Sad", "Angry", "Happy"}
        if v not in allowed_moods:
            raise ValueError(f"Mood must be exactly one of: 'Sad', 'Angry', or 'Happy'. Received: '{v}'")
        return v