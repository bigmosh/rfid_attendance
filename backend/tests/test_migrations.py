"""Local checks for Alembic revision metadata and environment settings."""

from pathlib import Path

from alembic.config import Config
from alembic.script import ScriptDirectory

from app.config import get_settings


BACKEND_DIRECTORY = Path(__file__).resolve().parents[1]
ALEMBIC_VERSION_MAX_LENGTH = 32


def test_alembic_has_expected_current_head():
    configuration = Config(str(BACKEND_DIRECTORY / "alembic.ini"))
    script_directory = ScriptDirectory.from_config(configuration)

    assert script_directory.get_current_head() == "0003_student_status"
    assert [revision.revision for revision in script_directory.walk_revisions()] == [
        "0003_student_status",
        "0002_add_foreign_key_indexes",
        "0001_initial_schema",
    ]


def test_alembic_revision_identifiers_fit_the_version_table_column():
    """Keep revision IDs within Alembic's default VARCHAR(32) version column."""
    configuration = Config(str(BACKEND_DIRECTORY / "alembic.ini"))
    script_directory = ScriptDirectory.from_config(configuration)

    for revision in script_directory.walk_revisions():
        assert len(revision.revision) <= ALEMBIC_VERSION_MAX_LENGTH


def test_settings_reads_database_url_from_environment(monkeypatch):
    test_url = "postgresql+psycopg://test:test@localhost:5432/test_attendance"
    monkeypatch.setenv("DATABASE_URL", test_url)
    get_settings.cache_clear()

    assert get_settings().database_url == test_url

    get_settings.cache_clear()
