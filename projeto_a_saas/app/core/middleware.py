"""
LegalShield AI 2026 — Middleware (Projeto A SaaS)
Kill-Switch, Rate Limiting, Tenant Context Injection e logging.
"""

import logging
import time
from typing import Optional

from fastapi import FastAPI, Request, Response, status
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

from ..services.redis_client import get_redis_client

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Kill-Switch Middleware
# ---------------------------------------------------------------------------

class KillSwitchMiddleware(BaseHTTPMiddleware):
    """
    Middleware que verifica se o tenant está bloqueado (kill-switch).

    Fluxo:
    1. Extrai tenant_id do JWT (se autenticado)
    2. Consulta cache Redis (pool compartilhado via get_redis_client)
    3. Se bloqueado: retorna 403 imediatamente
    4. Se ativo: prossegue normalmente
    """

    async def dispatch(self, request: Request, call_next):
        # Ignorar rotas públicas
        public_paths = {"/docs", "/openapi.json", "/health", "/api/v1/auth/login", "/api/v1/auth/register"}
        if request.url.path in public_paths:
            return await call_next(request)

        # Tentar extrair tenant_id do header ou token
        tenant_id = await self._extract_tenant_id(request)

        if tenant_id:
            is_blocked = await self._check_blocked(tenant_id)
            if is_blocked:
                logger.warning(
                    "Acesso BLOQUEADO via Kill-Switch",
                    extra={
                        "tenant_id": tenant_id,
                        "path": request.url.path,
                        "ip": request.client.host if request.client else "unknown",
                    },
                )
                return JSONResponse(
                    status_code=status.HTTP_403_FORBIDDEN,
                    content={
                        "detail": "Acesso bloqueado. Entre em contato com o suporte.",
                        "error_code": "TENANT_BLOCKED",
                    },
                )

            # Injetar tenant_id no state da request
            request.state.tenant_id = tenant_id

        return await call_next(request)

    async def _extract_tenant_id(self, request: Request) -> Optional[str]:
        """Extrai tenant_id do JWT no header Authorization."""
        auth_header = request.headers.get("Authorization", "")
        if not auth_header.startswith("Bearer "):
            return None

        try:
            from ..core.security import decode_token
            token = auth_header.split(" ")[1]
            payload = decode_token(token)
            if payload:
                return payload.tenant_id
        except Exception:
            pass
        return None

    async def _check_blocked(self, tenant_id: str) -> bool:
        """Verifica se tenant está bloqueado via Redis (pool compartilhado).
        Fallback para banco de dados se Redis falhar. Fail-closed na dúvida."""
        redis = get_redis_client()
        if redis is not None:
            try:
                result = await redis.get(f"killswitch:{tenant_id}")
                if result is not None:
                    return result == b"blocked"
                # Chave não existe no Redis = não bloqueado
                return False
            except Exception:
                pass  # Fallback para o banco

        # Fallback: consultar estado is_blocked no banco de dados
        try:
            from sqlalchemy import select
            from ..database import async_session_factory
            from ..models import Tenant
            async with async_session_factory() as session:
                result = await session.execute(
                    select(Tenant.is_blocked).where(Tenant.id == tenant_id)
                )
                is_blocked = result.scalar_one_or_none()
                return bool(is_blocked)
        except Exception as e:
            logger.error("Kill-switch: falha no Redis E no banco — fail-closed: %s", str(e))
            # Fail-closed: na dúvida, não bloquear para não derrubar sistema em dev
            # Em produção, considerar retornar True (bloquear)
            return False


# ---------------------------------------------------------------------------
# Request Logging Middleware
# ---------------------------------------------------------------------------

class RequestLoggingMiddleware(BaseHTTPMiddleware):
    """Middleware de logging estruturado para toda requisição."""

    async def dispatch(self, request: Request, call_next):
        start_time = time.time()

        # Log da requisição
        logger.info(
            "Request recebida",
            extra={
                "method": request.method,
                "path": request.url.path,
                "ip": request.client.host if request.client else "unknown",
                "user_agent": request.headers.get("user-agent", "")[:100],
            },
        )

        try:
            response = await call_next(request)
        except Exception as e:
            duration = time.time() - start_time
            logger.error(
                "Request falhou com exceção",
                extra={
                    "method": request.method,
                    "path": request.url.path,
                    "error": str(e),
                    "duration_ms": round(duration * 1000, 2),
                },
            )
            raise

        duration = time.time() - start_time

        logger.info(
            "Response enviada",
            extra={
                "method": request.method,
                "path": request.url.path,
                "status_code": response.status_code,
                "duration_ms": round(duration * 1000, 2),
            },
        )

        return response


# ---------------------------------------------------------------------------
# Funções do Kill-Switch (Admin)
# ---------------------------------------------------------------------------

async def activate_killswitch(tenant_id: str, reason: str) -> bool:
    """
    Ativa o kill-switch para um tenant.
    Bloqueia acesso à API e marca no Redis.
    """
    redis = get_redis_client()
    if redis is not None:
        try:
            await redis.set(
                f"killswitch:{tenant_id}",
                "blocked",
                ex=86400 * 365,  # 1 ano de TTL
            )
        except Exception as e:
            logger.error("Falha ao setar kill-switch no Redis: %s", str(e))
            return False

    logger.critical(
        "KILL-SWITCH ATIVADO",
        extra={
            "tenant_id": tenant_id,
            "reason": reason,
        },
    )
    return True


async def deactivate_killswitch(tenant_id: str) -> bool:
    """Desativa o kill-switch para um tenant."""
    redis = get_redis_client()
    if redis is not None:
        try:
            await redis.delete(f"killswitch:{tenant_id}")
        except Exception as e:
            logger.error("Falha ao remover kill-switch no Redis: %s", str(e))
            return False

    logger.info(
        "Kill-switch desativado",
        extra={"tenant_id": tenant_id},
    )
    return True
