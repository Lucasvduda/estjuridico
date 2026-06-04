"""
LegalShield AI 2026 — Database (Projeto A SaaS)
Configuração assíncrona do SQLAlchemy com suporte a:
  - PostgreSQL + RLS (produção / Docker)
  - SQLite (desenvolvimento local sem Docker)
"""

from contextlib import asynccontextmanager
from typing import AsyncGenerator

from sqlalchemy import text, event
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase

from .config import get_settings

settings = get_settings()


# ---------------------------------------------------------------------------
# Detectar backend
# ---------------------------------------------------------------------------
_is_sqlite = settings.database_url.startswith("sqlite")


# ---------------------------------------------------------------------------
# Engine Configuration
# ---------------------------------------------------------------------------
if _is_sqlite:
    # SQLite: sem pool_size/max_overflow, habilitar check_same_thread=False
    engine = create_async_engine(
        settings.database_url,
        echo=settings.debug,
        connect_args={"check_same_thread": False},
    )

    # Habilitar WAL mode e foreign keys no SQLite
    @event.listens_for(engine.sync_engine, "connect")
    def _set_sqlite_pragma(dbapi_connection, connection_record):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA journal_mode=WAL")
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()
else:
    # PostgreSQL: pool de conexões completo
    engine = create_async_engine(
        settings.database_url,
        pool_size=settings.db_pool_size,
        max_overflow=settings.db_max_overflow,
        echo=settings.debug,
    )


async_session_factory = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


class Base(DeclarativeBase):
    """Base declarativa para todos os modelos."""
    pass


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """Dependency injection para sessão do banco (sem contexto de tenant)."""
    async with async_session_factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


async def get_tenant_db(tenant_id: str) -> AsyncGenerator[AsyncSession, None]:
    """
    Dependency injection com contexto de tenant para RLS.
    Define a variável de sessão do PostgreSQL antes de cada operação.
    No SQLite, apenas injeta o tenant_id sem RLS (sem suporte a RLS).
    """
    async with async_session_factory() as session:
        try:
            if not _is_sqlite:
                # Injetar contexto do tenant para RLS (PostgreSQL only)
                await session.execute(
                    text("SET app.current_tenant_id = :tid"),
                    {"tid": str(tenant_id)}
                )
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            if not _is_sqlite:
                # Limpar contexto (PostgreSQL only)
                await session.execute(
                    text("RESET app.current_tenant_id")
                )
            await session.close()


async def init_db() -> None:
    """Cria todas as tabelas (usar apenas em desenvolvimento)."""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


async def close_db() -> None:
    """Fecha pool de conexões."""
    await engine.dispose()
