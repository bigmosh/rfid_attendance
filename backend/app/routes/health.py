"""Deployment and database health checks."""

import logging

from fastapi import APIRouter
from fastapi.responses import JSONResponse
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from app.database import engine


router = APIRouter()
LOGGER = logging.getLogger(__name__)


@router.get("/health")
def health_check():
    """Return a minimal response suitable for Coolify health checks."""
    return {"status": "ok"}


@router.get("/health/db")
def database_health_check():
    """Perform a minimal database query without exposing connection details."""
    try:
        with engine.connect() as connection:
            connection.execute(text("SELECT 1"))
    except SQLAlchemyError:
        LOGGER.warning("Database connectivity health check failed")
        return JSONResponse(
            status_code=503,
            content={"status": "error", "database": "unavailable"},
        )

    return {"status": "ok", "database": "connected"}
