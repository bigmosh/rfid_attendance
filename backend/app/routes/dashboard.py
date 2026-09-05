"""Read-only dashboard overview route."""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.config import get_settings
from app.database import get_db
from app.schemas.dashboard import DashboardSummaryResponse
from app.services.dashboard import get_dashboard_summary


router = APIRouter(prefix="/api/v1/dashboard", tags=["dashboard"])


@router.get("/summary", response_model=DashboardSummaryResponse)
def dashboard_summary(database_session: Session = Depends(get_db)):
    """Return real-time overview counts."""
    try:
        return get_dashboard_summary(database_session, get_settings().app_timezone)
    except SQLAlchemyError:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error",
        ) from None
