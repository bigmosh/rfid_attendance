"""FastAPI application entry point."""

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import get_settings
from app.routes.attendance import router as attendance_router
from app.routes.dashboard import router as dashboard_router
from app.routes.health import router as health_router
from app.routes.students import router as students_router


LOGGER = logging.getLogger(__name__)


def configure_logging(log_level):
    """Configure concise process logging for local runs and Coolify logs."""
    logging.basicConfig(
        level=log_level.upper(),
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )


def create_app():
    """Create the API without opening a database connection at import time."""
    settings = get_settings()
    configure_logging(settings.log_level)

    @asynccontextmanager
    async def lifespan(_app):
        LOGGER.info("Backend application started (environment: %s)", settings.app_env)
        yield
        LOGGER.info("Backend application shutting down")

    application = FastAPI(
        title="RFID Attendance API",
        version="0.1.0",
        lifespan=lifespan,
    )
    application.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origin_list,
        allow_credentials=False,
        allow_methods=["GET", "POST", "PATCH"],
        allow_headers=["Content-Type"],
    )
    application.include_router(health_router)
    application.include_router(attendance_router)
    application.include_router(dashboard_router)
    application.include_router(students_router)
    return application


app = create_app()
