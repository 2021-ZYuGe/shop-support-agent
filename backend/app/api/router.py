from fastapi import APIRouter

from app.api.routes import admin, auth, chat, health, knowledge, operations

api_router = APIRouter()
api_router.include_router(health.router, tags=["system"])
api_router.include_router(auth.router, prefix="/auth", tags=["auth"])
api_router.include_router(admin.router, prefix="/admin", tags=["admin"])
api_router.include_router(
    operations.router, prefix="/admin", tags=["operations"]
)
api_router.include_router(knowledge.router, prefix="/admin/knowledge", tags=["knowledge"])
api_router.include_router(chat.router, prefix="/chat", tags=["chat"])
