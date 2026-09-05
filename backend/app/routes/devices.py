"""Read-only device route used by dashboard enrollment selection."""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.database import get_db
from app.schemas.enrollment import DeviceListItem
from app.services.enrollment import list_devices


router = APIRouter(prefix="/api/v1/devices", tags=["devices"])


@router.get("", response_model=list[DeviceListItem])
def get_devices(database_session: Session = Depends(get_db)):
    """Return registered devices for dashboard enrollment selection."""
    try:
        return list_devices(database_session)
    except SQLAlchemyError:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error",
        ) from None
