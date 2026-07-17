from collections.abc import AsyncGenerator

from sqlalchemy import MetaData
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

from app.config import get_settings

settings = get_settings()

engine = create_async_engine(settings.database_url, echo=settings.app_env == "development")

AsyncSessionLocal = async_sessionmaker(
    bind=engine, expire_on_commit=False, class_=AsyncSession
)

# Erzwingt vorhersehbare Constraint-/Index-Namen für alles, was ab jetzt neu über
# Alembic-Autogenerate entsteht (ix_<table>_<column>, fk_<table>_<column>, ...) — siehe
# CLAUDE.md. Bestehende, bereits migrierte Constraints (z.B. Postgres-Default-Namen wie
# "receipts_bucket_id_fkey") werden dadurch NICHT umbenannt; das würde eine eigene,
# separat zu entscheidende Migration erfordern.
NAMING_CONVENTION = {
    "ix": "ix_%(table_name)s_%(column_0_name)s",
    "uq": "uq_%(table_name)s_%(column_0_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s",
    "pk": "pk_%(table_name)s",
}


class Base(DeclarativeBase):
    """Gemeinsame Basisklasse für alle ORM-Modelle."""

    metadata = MetaData(naming_convention=NAMING_CONVENTION)


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    async with AsyncSessionLocal() as session:
        yield session
