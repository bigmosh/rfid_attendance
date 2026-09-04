"""Deployment health check."""

from fastapi import APIRouter


router = APIRouter()


@router.get("/health")
def health_check():
    """Return a minimal response suitable for Coolify health checks."""
    return {"status": "ok"}
