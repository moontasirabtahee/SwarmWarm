"""
Database engine + schema bootstrap.

Provides a single SQLAlchemy engine driven by `settings.DATABASE_URL` (SQLite by
default, PostgreSQL in production). Exposes helpers used by `app.core.db`:

* `engine`               – the shared SQLAlchemy engine
* `create_schema()`      – create any missing tables from the Core metadata
* `sync_missing_columns()` – lightweight "add missing columns" migrator so an older
                             database file gains new columns without a destructive rebuild
                             (Postgres deployments should use Alembic instead)
"""
import logging

from sqlalchemy import create_engine, event, inspect, text

from app.core.models import metadata
from app.core.settings import settings

logger = logging.getLogger("swarmwarm.database")

# SQLite needs check_same_thread disabled (FastAPI/Celery use multiple threads) and
# benefits from an explicit connection pool. Postgres uses sensible pool defaults.
if settings.is_sqlite:
    engine = create_engine(
        settings.DATABASE_URL,
        connect_args={"check_same_thread": False, "timeout": 10},
        future=True,
    )

    @event.listens_for(engine, "connect")
    def _enable_sqlite_fk(dbapi_conn, _record):
        cur = dbapi_conn.cursor()
        cur.execute("PRAGMA foreign_keys=ON;")
        cur.close()
else:
    engine = create_engine(
        settings.DATABASE_URL,
        pool_pre_ping=True,
        pool_size=10,
        max_overflow=20,
        future=True,
    )


def create_schema() -> None:
    """Create any tables that do not yet exist (idempotent)."""
    metadata.create_all(engine)


def sync_missing_columns() -> None:
    """
    Add any columns present in the model metadata but missing from an existing table.

    Covers pre-existing SQLite database files that predate a new column. Both SQLite
    and Postgres support `ALTER TABLE ... ADD COLUMN`. Production Postgres should be
    managed with Alembic; this is a dev-safety net.
    """
    inspector = inspect(engine)
    existing_tables = set(inspector.get_table_names())

    with engine.begin() as conn:
        for table in metadata.sorted_tables:
            if table.name not in existing_tables:
                continue
            live_cols = {c["name"] for c in inspector.get_columns(table.name)}
            for column in table.columns:
                if column.name in live_cols:
                    continue
                col_type = column.type.compile(dialect=engine.dialect)
                ddl = f'ALTER TABLE {table.name} ADD COLUMN {column.name} {col_type}'
                logger.info("Applying column migration: %s", ddl)
                conn.execute(text(ddl))
