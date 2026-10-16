from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.api.v1.router import api_router

app = FastAPI(
    title="Encore Concert Reservation Service",
    version="1.0.0",
    description="API for managing concerts, reservations, comments, and user authentication."
)

# Standard CORS configuration for local development and frontend integration
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register all v1 routers under /api/v1
app.include_router(api_router, prefix="/api/v1")

@app.get("/health", tags=["health"])
def health_check():
    return {"status": "ok"}