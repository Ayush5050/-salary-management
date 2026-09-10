"""Database engine and session management.

SQLite needs two things switched on explicitly to behave the way the schema
assumes: foreign key enforcement (off by default, so a bad ``manager_id`` would
otherwise be accepted silently) and WAL journalling, which lets the dashboard's
read queries run while a write is in flight.
"""

from collections.abc import Iterator
from typing import Any

from sqlalchemy import Engine, create_engine, event
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import Pool

from app.config import get_settings


def _is_sqlite(url: str) -> bool:
    return url.startswith("sqlite")


def _register_sqlite_pragmas(engine: Engine) -> None:
    """Attach the per-connection pragmas to one engine.

    Bound to the specific engine rather than to the ``Engine`` class, because a
    class-level listener only takes effect once this module has been imported —
    which made foreign key enforcement depend on import order, and silently
    absent in tests that never touched it.
    """

    @event.listens_for(engine, "connect")
    def _apply(dbapi_connection: Any, _record: Any) -> None:
        cursor = dbapi_connection.cursor()
        try:
            cursor.execute("PRAGMA foreign_keys=ON")
            cursor.execute("PRAGMA journal_mode=WAL")
        finally:
            cursor.close()


def create_database_engine(database_url: str, echo: bool, poolclass: type[Pool] | None) -> Engine:
    """The single way an engine is built, so every engine is configured alike.

    Tests pass ``StaticPool`` to keep one in-memory database across connections;
    everything else passes ``None`` for the dialect's own default.
    """
    connect_args = {"check_same_thread": False} if _is_sqlite(database_url) else {}
    engine = create_engine(
        database_url,
        echo=echo,
        connect_args=connect_args,
        poolclass=poolclass,
        future=True,
    )
    if _is_sqlite(database_url):
        _register_sqlite_pragmas(engine)
    return engine


_settings = get_settings()
engine = create_database_engine(_settings.database_url, _settings.sql_echo, poolclass=None)
SessionFactory = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


def get_session() -> Iterator[Session]:
    """FastAPI dependency yielding a request-scoped session.

    The session is rolled back on any exception so a failed request cannot leave
    a partial write visible to the next one.
    """
    session = SessionFactory()
    try:
        yield session
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()
