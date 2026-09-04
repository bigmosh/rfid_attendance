"""SQLAlchemy engine, session, and declarative base."""

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker

from app.config import get_settings


settings = get_settings()

# Engine construction does not open a connection. Connections are opened only
# when a request, seed command, or Alembic migration uses a session.
engine = create_engine(settings.database_url, pool_pre_ping=True)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)


class Base(DeclarativeBase):
    """Base class shared by all SQLAlchemy models."""


def get_db():
    """Yield a database session for future FastAPI route dependencies."""
    database_session = SessionLocal()
    try:
        yield database_session
    finally:
        database_session.close()
