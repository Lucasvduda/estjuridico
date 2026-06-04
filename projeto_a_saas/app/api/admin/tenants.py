"""
LegalShield AI 2026 — Admin Tenants Router (Projeto A SaaS)
Gerenciamento de tenants: listar, bloquear (kill-switch), desbloquear, editar.
"""

import logging
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ...core.middleware import activate_killswitch, deactivate_killswitch
from ...models import Tenant, User
from ...schemas import (
    MessageResponse,
    TenantBlockRequest,
    TenantSchema,
    TenantUpdateRequest,
)
from ..deps import get_db, log_audit, require_role

logger = logging.getLogger(__name__)
router = APIRouter()


@router.get("/", response_model=list[TenantSchema])
async def list_tenants(
    _: User = Depends(require_role("superadmin")),
    db: AsyncSession = Depends(get_db),
):
    """Lista todos os tenants (apenas superadmin)."""
    result = await db.execute(select(Tenant).order_by(Tenant.created_at.desc()))
    tenants = result.scalars().all()
    return [
        TenantSchema(
            id=str(t.id), name=t.name, slug=t.slug, email=t.email,
            subscription_plan=t.subscription_plan,
            subscription_status=t.subscription_status,
            is_blocked=t.is_blocked,
            blocked_reason=t.blocked_reason,
            max_analyses_per_month=t.max_analyses_per_month,
            max_users=t.max_users,
            created_at=t.created_at,
        ) for t in tenants
    ]


@router.post("/{tenant_id}/block", response_model=MessageResponse)
async def block_tenant(
    tenant_id: str,
    body: TenantBlockRequest,
    admin: User = Depends(require_role("superadmin")),
    db: AsyncSession = Depends(get_db),
):
    """Ativa Kill-Switch para um tenant."""
    result = await db.execute(select(Tenant).where(Tenant.id == tenant_id))
    tenant = result.scalar_one_or_none()
    if not tenant:
        raise HTTPException(status_code=404, detail="Tenant não encontrado")

    tenant.is_blocked = True
    tenant.blocked_at = datetime.now(timezone.utc)
    tenant.blocked_reason = body.reason
    tenant.subscription_status = "suspended"

    # Ativar no Redis (cache)
    await activate_killswitch(tenant_id, body.reason)

    await log_audit(
        db, action="block_tenant", user_id=str(admin.id),
        tenant_id=tenant_id, resource_type="tenant",
        resource_id=tenant_id,
        details={"reason": body.reason},
        severity="critical",
    )

    return MessageResponse(
        message=f"Tenant '{tenant.name}' bloqueado com sucesso",
        detail=body.reason,
    )


@router.post("/{tenant_id}/unblock", response_model=MessageResponse)
async def unblock_tenant(
    tenant_id: str,
    admin: User = Depends(require_role("superadmin")),
    db: AsyncSession = Depends(get_db),
):
    """Desativa Kill-Switch para um tenant."""
    result = await db.execute(select(Tenant).where(Tenant.id == tenant_id))
    tenant = result.scalar_one_or_none()
    if not tenant:
        raise HTTPException(status_code=404, detail="Tenant não encontrado")

    tenant.is_blocked = False
    tenant.blocked_at = None
    tenant.blocked_reason = None
    tenant.subscription_status = "active"

    await deactivate_killswitch(tenant_id)

    await log_audit(
        db, action="unblock_tenant", user_id=str(admin.id),
        tenant_id=tenant_id, resource_type="tenant",
        resource_id=tenant_id,
        severity="warning",
    )

    return MessageResponse(message=f"Tenant '{tenant.name}' desbloqueado com sucesso")


@router.patch("/{tenant_id}", response_model=TenantSchema)
async def update_tenant(
    tenant_id: str,
    body: TenantUpdateRequest,
    admin: User = Depends(require_role("superadmin")),
    db: AsyncSession = Depends(get_db),
):
    """Atualiza configurações de um tenant."""
    result = await db.execute(select(Tenant).where(Tenant.id == tenant_id))
    tenant = result.scalar_one_or_none()
    if not tenant:
        raise HTTPException(status_code=404, detail="Tenant não encontrado")

    if body.name is not None:
        tenant.name = body.name
    if body.subscription_plan is not None:
        tenant.subscription_plan = body.subscription_plan
    if body.max_analyses_per_month is not None:
        tenant.max_analyses_per_month = body.max_analyses_per_month
    if body.max_users is not None:
        tenant.max_users = body.max_users

    tenant.updated_at = datetime.now(timezone.utc)
    await db.flush()

    return TenantSchema(
        id=str(tenant.id), name=tenant.name, slug=tenant.slug, email=tenant.email,
        subscription_plan=tenant.subscription_plan,
        subscription_status=tenant.subscription_status,
        is_blocked=tenant.is_blocked,
        blocked_reason=tenant.blocked_reason,
        max_analyses_per_month=tenant.max_analyses_per_month,
        max_users=tenant.max_users,
        created_at=tenant.created_at,
    )
