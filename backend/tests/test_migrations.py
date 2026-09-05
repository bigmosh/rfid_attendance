"""Local checks for Alembic revision metadata and environment settings."""

from pathlib import Path

from alembic.config import Config
from alembic.script import ScriptDirectory

from app.config import get_settings


BACKEND_DIRECTORY = Path(__file__).resolve().parents[1]


def test_alembic_has_expected_current_head():
    configuration = Config(str(BACKEND_DIRECTORY / "alembic.ini"))
    script_directory = ScriptDirectory.from_config(configuration)

    assert script_directory.get_current_head() == "0003_add_student_status_and_active_card_constraint"


def test_settings_reads_database_url_from_environment(monkeypatch):
    test_url = "postgresql+psycopg://test:test@localhost:5432/test_attendance"
    monkeypatch.setenv("DATABASE_URL", test_url)
    get_settings.cache_clear()

    assert get_settings().database_url == test_url

    get_settings.cache_clear()
