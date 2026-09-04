"""Environment required before importing the backend application in tests."""

import os


os.environ.setdefault(
    "DATABASE_URL",
    "postgresql+psycopg://test:test@localhost:5432/test_attendance",
)
os.environ.setdefault("APP_ENV", "test")
