"""
Health check endpoint.
"""
from fastapi import APIRouter
from app.schemas.call import HealthResponse
from app.core.config import settings

router = APIRouter()


@router.get("/health", response_model=HealthResponse)
async def health_check():
    """Check if the API service is running."""
    return HealthResponse(
        status="ok",
        service=settings.app_name,
        version=settings.app_version
    )
