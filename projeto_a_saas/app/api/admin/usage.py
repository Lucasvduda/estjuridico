"""
LegalShield AI 2026 — Admin Usage & Audit Routers (Projeto A SaaS)
Monitoramento de consumo de tokens e logs de auditoria.
"""

import logging
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from ...models import AuditLog, Analysis, Tenant, TokenUsage, User
from ...schemas import AuditLogSchema, TokenUsageSchema
from ..deps import get_db, require_role

logger = logging.getLogger(__name__)
router = APIRouter()


# ---------------------------------------------------------------------------
# Usage — Consumo de Tokens
# ---------------------------------------------------------------------------

@router.get("/usage", response_model=list[TokenUsageSchema])
async def get_usage(
    period: str = Query("month", pattern="^(day|week|month)$"),
    _: User = Depends(require_role("superadmin")),
    db: AsyncSession = Depends(get_db),
):
    """Resumo de consumo de tokens por tenant."""
    now = datetime.now(timezone.utc)
    if period == "day":
        since = now.replace(hour=0, minute=0, second=0, microsecond=0)
    elif period == "week":
        from datetime import timedelta
        since = now - timedelta(days=7)
    else:
        since = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)

    query = (
        select(
            TokenUsage.tenant_id,
            func.sum(TokenUsage.total_tokens).label("total_tokens"),
            func.sum(TokenUsage.cost_usd).label("total_cost"),
            func.count(TokenUsage.id).label("analysis_count"),
        )
        .where(TokenUsage.created_at >= since)
        .group_by(TokenUsage.tenant_id)
        .order_by(func.sum(TokenUsage.cost_usd).desc())
    )

    result = await db.execute(query)
    rows = result.all()

    items = []
    for row in rows:
        # Buscar nome do tenant
        t = await db.execute(select(Tenant.name).where(Tenant.id == row.tenant_id))
        tenant_name = t.scalar() or "Desconhecido"

        items.append(TokenUsageSchema(
            tenant_id=str(row.tenant_id),
            tenant_name=tenant_name,
            total_tokens=row.total_tokens or 0,
            total_cost_usd=round(float(row.total_cost or 0), 4),
            analysis_count=row.analysis_count or 0,
            period=period,
        ))

    return items


# ---------------------------------------------------------------------------
# Audit — Logs de Auditoria
# ---------------------------------------------------------------------------

@router.get("/audit", response_model=list[AuditLogSchema])
async def get_audit_logs(
    tenant_id: str = None,
    action: str = None,
    severity: str = None,
    limit: int = Query(50, le=200),
    _: User = Depends(require_role("superadmin")),
    db: AsyncSession = Depends(get_db),
):
    """Lista logs de auditoria com filtros opcionais."""
    query = select(AuditLog).order_by(AuditLog.created_at.desc())

    if tenant_id:
        query = query.where(AuditLog.tenant_id == tenant_id)
    if action:
        query = query.where(AuditLog.action == action)
    if severity:
        query = query.where(AuditLog.severity == severity)

    query = query.limit(limit)
    result = await db.execute(query)
    logs = result.scalars().all()

    return [
        AuditLogSchema(
            id=str(lg.id),
            action=lg.action,
            resource_type=lg.resource_type,
            resource_id=lg.resource_id,
            ip_address=lg.ip_address,
            severity=lg.severity,
            created_at=lg.created_at,
            details=lg.details,
        ) for lg in logs
    ]
