"""
LegalShield AI 2026 — API Dependencies (Projeto A SaaS)
Dependências compartilhadas: autenticação, tenant context, audit logging.
"""

import logging
from datetime import datetime, timezone
from typing import Optional

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from ..config import get_settings
from ..core.security import decode_token, TokenPayload
from ..database import async_session_factory
from ..models import AuditLog, Tenant, User

logger = logging.getLogger(__name__)
settings = get_settings()
security_scheme = HTTPBearer()


async def get_db() -> AsyncSession:
    """Sessão de banco sem contexto de tenant."""
    async with async_session_factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security_scheme),
    db: AsyncSession = Depends(get_db),
) -> User:
    """Extrai e valida o usuário atual do JWT."""
    token = credentials.credentials
    payload = decode_token(token)

    if not payload or payload.type != "access":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token inválido ou expirado",
        )

    result = await db.execute(select(User).where(User.id == payload.sub))
    user = result.scalar_one_or_none()

    if not user or not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Usuário não encontrado ou inativo",
        )

    return user


async def get_tenant_db(
    credentials: HTTPAuthorizationCredentials = Depends(security_scheme),
) -> AsyncSession:
    """Sessão de banco COM contexto RLS do tenant."""
    payload = decode_token(credentials.credentials)
    if not payload:
        raise HTTPException(status_code=401, detail="Token inválido")

    async with async_session_factory() as session:
        try:
            await session.execute(
                text("SET app.current_tenant_id = :tid"),
                {"tid": str(payload.tenant_id)}
            )
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


def require_role(required_role: str):
    """Dependency factory para verificar role do usuário."""
    async def _check_role(user: User = Depends(get_current_user)):
        role_hierarchy = {"viewer": 0, "user": 1, "admin": 2, "superadmin": 3}
        user_level = role_hierarchy.get(user.role, 0)
        required_level = role_hierarchy.get(required_role, 0)
        if user_level < required_level:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Permissão insuficiente. Requer role: {required_role}",
            )
        return user
    return _check_role


async def log_audit(
    db: AsyncSession,
    action: str,
    user_id: Optional[str] = None,
    tenant_id: Optional[str] = None,
    resource_type: Optional[str] = None,
    resource_id: Optional[str] = None,
    details: Optional[dict] = None,
    ip_address: Optional[str] = None,
    severity: str = "info",
):
    """Registra entrada no log de auditoria."""
    log_entry = AuditLog(
        action=action,
        user_id=user_id,
        tenant_id=tenant_id,
        resource_type=resource_type,
        resource_id=resource_id,
        details=details,
        ip_address=ip_address,
        severity=severity,
    )
    db.add(log_entry)
    await db.flush()
