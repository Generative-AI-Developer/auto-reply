from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker

from .config import get_settings

settings = get_settings()

# SQLite needs check_same_thread=False because the watchdog observer runs in
# its own thread and shares the engine. Harmless / ignored for PostgreSQL.
connect_args = {"check_same_thread": False} if settings.database_url.startswith("sqlite") else {}

engine = create_engine(settings.database_url, connect_args=connect_args, future=True)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)


class Base(DeclarativeBase):
    pass


def init_db() -> None:
    """Create tables. Simple approach for this stage (Alembic can be added later)."""
    from . import models  # noqa: F401  (register models on Base.metadata)

    Base.metadata.create_all(bind=engine)
    _ensure_columns()


def _ensure_columns() -> None:
    """Additive, idempotent migration for columns added after a table first
    shipped (there's no Alembic yet, and create_all never alters an existing
    table). SQLite and PostgreSQL both support `ALTER TABLE ... ADD COLUMN`;
    existing rows take the column default, so this is safe to run every start.
    """
    from sqlalchemy import inspect, text

    additions = {
        "request_identifiers": {
            "part": "INTEGER DEFAULT 0",
            "date_from": "DATE",
            "date_to": "DATE",
        },
    }
    inspector = inspect(engine)
    with engine.begin() as conn:
        for table, columns in additions.items():
            existing = {c["name"] for c in inspector.get_columns(table)}
            for name, ddl in columns.items():
                if name not in existing:
                    conn.execute(text(f"ALTER TABLE {table} ADD COLUMN {name} {ddl}"))
