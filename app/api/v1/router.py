from fastapi import APIRouter
from app.api.v1.endpoints import auth, users, comments, invoices, concerts

api_router = APIRouter()


api_router.include_router(auth.router)
api_router.include_router(users.router)
api_router.include_router(comments.router)
api_router.include_router(invoices.router)
api_router.include_router(concerts.router)