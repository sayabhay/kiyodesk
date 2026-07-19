"""Async SQLite engine and unit-of-work session dependency."""

from collections.abc import AsyncIterator

from loguru import logger
from sqlalchemy import ColumnDefault, Connection, inspect, text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.config import get_settings
from app.database.base import Base

settings = get_settings()
engine = create_async_engine(settings.database_url, echo=settings.app_env == "development")
AsyncSessionLocal = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


async def get_session() -> AsyncIterator[AsyncSession]:
    """Yield one request-scoped database session."""

    async with AsyncSessionLocal() as session:
        yield session


def _sync_schema(connection: object) -> None:
    """Add any model columns that are missing from the live SQLite tables.

    SQLAlchemy's create_all only creates missing tables; it never alters existing
    ones. This function inspects the current schema and issues ALTER TABLE ...
    ADD COLUMN for every column that exists in the ORM model but is absent from
    the database, so the DB stays in sync after new columns are added without
    requiring a manual file delete.
    """
    conn: Connection = connection  # type: ignore[assignment]
    inspector = inspect(conn)

    for table in Base.metadata.sorted_tables:
        if not inspector.has_table(table.name):
            continue  # brand-new tables are handled by create_all below

        existing_columns = {col["name"] for col in inspector.get_columns(table.name)}
        for column in table.columns:
            if column.name not in existing_columns:
                col_type = column.type.compile(dialect=conn.dialect)
                nullable_kw = "NULL" if column.nullable else "NOT NULL"
                default_clause = ""
                if column.default is not None and isinstance(column.default, ColumnDefault):
                    default_clause = f" DEFAULT {column.default.arg!r}"
                elif column.nullable:
                    # SQLite requires a default when adding a NOT NULL column to
                    # an existing table; nullable columns default to NULL.
                    default_clause = " DEFAULT NULL"
                ddl = (
                    f"ALTER TABLE {table.name} "
                    f"ADD COLUMN {column.name} {col_type}{default_clause} {nullable_kw}"
                )
                logger.info("Schema sync: {}", ddl)
                conn.execute(text(ddl))


async def initialize_database() -> None:
    """Sync schema columns then create any missing tables."""

    async with engine.begin() as connection:
        await connection.run_sync(_sync_schema)
        await connection.run_sync(Base.metadata.create_all)


async def dispose_database() -> None:
    """Close pooled database connections during application shutdown."""

    await engine.dispose()
