"""
API v1 router configuration.
"""
from fastapi import APIRouter

from app.api.v1 import (
    auth,
    browse,
    endpoints,
    executions,
    health,
    logs,
    sessions,
    settings,
    shots,
    uploads
)

# Create main API router
api_router = APIRouter()

# Include all endpoint routers
api_router.include_router(auth.router)
api_router.include_router(browse.router)
api_router.include_router(endpoints.router)
api_router.include_router(executions.router)
api_router.include_router(health.router)
api_router.include_router(logs.router)
api_router.include_router(sessions.router)
api_router.include_router(settings.router)
api_router.include_router(shots.router)
api_router.include_router(uploads.router, prefix="/uploads")