"""
LegalShield AI 2026 — Admin Theme Router (Projeto A SaaS)
Personalização de cores (white-label) por tenant.
O dev/admin pode trocar as cores de cada empresa de advogado.
"""

import logging
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field, field_validator
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ...models import Tenant, User
from ..deps import get_db, log_audit, require_role

logger = logging.getLogger(__name__)
router = APIRouter()


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------

class ThemeResponse(BaseModel):
    tenant_id: str
    tenant_name: str
    primary_color: str
    accent_color: str
    sidebar_color: str
    bg_color: str
    logo_url: Optional[str] = None


class ThemeUpdateRequest(BaseModel):
    primary_color: Optional[str] = Field(None, pattern=r"^#[0-9A-Fa-f]{6}$")
    accent_color: Optional[str] = Field(None, pattern=r"^#[0-9A-Fa-f]{6}$")
    sidebar_color: Optional[str] = Field(None, pattern=r"^#[0-9A-Fa-f]{6}$")
    bg_color: Optional[str] = Field(None, pattern=r"^#[0-9A-Fa-f]{6}$")
    logo_url: Optional[str] = None


# Presets de cores disponíveis para quick-select
THEME_PRESETS = {
    "juridico_classico": {
        "name": "Jurídico Clássico",
        "primary_color": "#6C5CE7",
        "accent_color": "#00D2D3",
        "sidebar_color": "#1A1A2E",
        "bg_color": "#0F0F23",
    },
    "corporativo_azul": {
        "name": "Corporativo Azul",
        "primary_color": "#0984E3",
        "accent_color": "#74B9FF",
        "sidebar_color": "#1B2838",
        "bg_color": "#0D1B2A",
    },
    "elegante_dourado": {
        "name": "Elegante Dourado",
        "primary_color": "#D4A76A",
        "accent_color": "#F0E68C",
        "sidebar_color": "#1A1A1A",
        "bg_color": "#121212",
    },
    "moderno_verde": {
        "name": "Moderno Verde",
        "primary_color": "#00B894",
        "accent_color": "#55EFC4",
        "sidebar_color": "#1A2F1A",
        "bg_color": "#0D1F0D",
    },
    "tech_roxo": {
        "name": "Tech Roxo",
        "primary_color": "#A855F7",
        "accent_color": "#C084FC",
        "sidebar_color": "#1E1033",
        "bg_color": "#13082A",
    },
}


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@router.get("/presets")
async def get_theme_presets(
    _: User = Depends(require_role("superadmin")),
):
    """Lista presets de cores disponíveis."""
    return THEME_PRESETS


@router.get("/{tenant_id}", response_model=ThemeResponse)
async def get_tenant_theme(
    tenant_id: str,
    _: User = Depends(require_role("superadmin")),
    db: AsyncSession = Depends(get_db),
):
    """Retorna tema atual de um tenant."""
    result = await db.execute(select(Tenant).where(Tenant.id == tenant_id))
    tenant = result.scalar_one_or_none()
    if not tenant:
        raise HTTPException(status_code=404, detail="Tenant não encontrado")

    return ThemeResponse(
        tenant_id=str(tenant.id),
        tenant_name=tenant.name,
        primary_color=tenant.theme_primary_color or "#6C5CE7",
        accent_color=tenant.theme_accent_color or "#00D2D3",
        sidebar_color=tenant.theme_sidebar_color or "#1A1A2E",
        bg_color=tenant.theme_bg_color or "#0F0F23",
        logo_url=tenant.theme_logo_url,
    )


@router.put("/{tenant_id}", response_model=ThemeResponse)
async def update_tenant_theme(
    tenant_id: str,
    body: ThemeUpdateRequest,
    admin: User = Depends(require_role("superadmin")),
    db: AsyncSession = Depends(get_db),
):
    """Atualiza cores do tema de um tenant (white-label)."""
    result = await db.execute(select(Tenant).where(Tenant.id == tenant_id))
    tenant = result.scalar_one_or_none()
    if not tenant:
        raise HTTPException(status_code=404, detail="Tenant não encontrado")

    changes = {}
    if body.primary_color is not None:
        tenant.theme_primary_color = body.primary_color
        changes["primary_color"] = body.primary_color
    if body.accent_color is not None:
        tenant.theme_accent_color = body.accent_color
        changes["accent_color"] = body.accent_color
    if body.sidebar_color is not None:
        tenant.theme_sidebar_color = body.sidebar_color
        changes["sidebar_color"] = body.sidebar_color
    if body.bg_color is not None:
        tenant.theme_bg_color = body.bg_color
        changes["bg_color"] = body.bg_color
    if body.logo_url is not None:
        tenant.theme_logo_url = body.logo_url
        changes["logo_url"] = body.logo_url

    tenant.updated_at = datetime.now(timezone.utc)
    await db.flush()

    await log_audit(
        db, action="update_theme", user_id=str(admin.id),
        tenant_id=tenant_id, resource_type="tenant",
        resource_id=tenant_id, details=changes,
    )

    return ThemeResponse(
        tenant_id=str(tenant.id),
        tenant_name=tenant.name,
        primary_color=tenant.theme_primary_color or "#6C5CE7",
        accent_color=tenant.theme_accent_color or "#00D2D3",
        sidebar_color=tenant.theme_sidebar_color or "#1A1A2E",
        bg_color=tenant.theme_bg_color or "#0F0F23",
        logo_url=tenant.theme_logo_url,
    )


@router.put("/{tenant_id}/preset/{preset_name}", response_model=ThemeResponse)
async def apply_theme_preset(
    tenant_id: str,
    preset_name: str,
    admin: User = Depends(require_role("superadmin")),
    db: AsyncSession = Depends(get_db),
):
    """Aplica um preset de cores ao tenant."""
    if preset_name not in THEME_PRESETS:
        raise HTTPException(status_code=400, detail=f"Preset não encontrado: {preset_name}")

    preset = THEME_PRESETS[preset_name]

    result = await db.execute(select(Tenant).where(Tenant.id == tenant_id))
    tenant = result.scalar_one_or_none()
    if not tenant:
        raise HTTPException(status_code=404, detail="Tenant não encontrado")

    tenant.theme_primary_color = preset["primary_color"]
    tenant.theme_accent_color = preset["accent_color"]
    tenant.theme_sidebar_color = preset["sidebar_color"]
    tenant.theme_bg_color = preset["bg_color"]
    tenant.updated_at = datetime.now(timezone.utc)
    await db.flush()

    await log_audit(
        db, action="apply_theme_preset", user_id=str(admin.id),
        tenant_id=tenant_id, resource_type="tenant",
        resource_id=tenant_id, details={"preset": preset_name},
    )

    return ThemeResponse(
        tenant_id=str(tenant.id),
        tenant_name=tenant.name,
        primary_color=tenant.theme_primary_color,
        accent_color=tenant.theme_accent_color,
        sidebar_color=tenant.theme_sidebar_color,
        bg_color=tenant.theme_bg_color,
        logo_url=tenant.theme_logo_url,
    )
