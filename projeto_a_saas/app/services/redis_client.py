"""
LegalShield AI 2026 — Redis Client Singleton

Pool de conexões compartilhado por toda a aplicação. Inicializado uma vez
no startup (lifespan) e fechado no shutdown — nunca abrir/fechar por chamada.

Regra aplicada: conn-pooling (impacto HIGH — reduz overhead em 10x ou mais).
"""

from __future__ import annotations

import logging
from typing import Optional

from redis.asyncio import ConnectionPool, Redis

from ..config import get_settings

logger = logging.getLogger(__name__)

_pool: Optional[ConnectionPool] = None
_client: Optional[Redis] = None


def get_redis_client() -> Optional[Redis]:
    """Retorna o cliente Redis compartilhado (pool). None se não inicializado."""
    return _client


async def init_redis_pool() -> Optional[Redis]:
    """
    Inicializa o pool de conexões Redis. Deve ser chamado uma única vez
    no startup do app (lifespan). Idempotente — segunda chamada é no-op.
    """
    global _pool, _client

    if _client is not None:
        return _client

    url = get_settings().redis_url
    if not url:
        logger.warning("redis_client: REDIS_URL não configurado — operando sem Redis")
        return None

    try:
        _pool = ConnectionPool.from_url(
            url,
            decode_responses=False,
            max_connections=20,
        )
        _client = Redis(connection_pool=_pool)
        # Ping para validar a conexão no startup
        await _client.ping()
        logger.info("redis_client: pool inicializado com sucesso (max_connections=20)")
        return _client
    except Exception as exc:
        logger.error("redis_client: falha ao inicializar pool — %s", exc)
        _pool = None
        _client = None
        return None


async def close_redis_pool() -> None:
    """Fecha o pool de conexões. Deve ser chamado no shutdown do app."""
    global _pool, _client

    if _client is not None:
        try:
            await _client.aclose()
        except Exception as exc:
            logger.warning("redis_client: erro ao fechar cliente — %s", exc)
        _client = None

    if _pool is not None:
        try:
            await _pool.aclose()
        except Exception as exc:
            logger.warning("redis_client: erro ao fechar pool — %s", exc)
        _pool = None

    logger.info("redis_client: pool encerrado")
