"""
LegalShield AI 2026 — Pydantic Schemas (Projeto A SaaS)
Validação de todos os inputs/outputs da API.
"""

from datetime import datetime
from typing import Any, Optional
from pydantic import BaseModel, EmailStr, Field, field_validator
import re


# ---------------------------------------------------------------------------
# Auth Schemas
# ---------------------------------------------------------------------------

class LoginRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)
    mfa_code: Optional[str] = Field(None, min_length=6, max_length=6)


class RegisterRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)
    full_name: str = Field(min_length=2, max_length=255)
    tenant_slug: str = Field(min_length=3, max_length=100)
    tenant_name: str = Field(min_length=2, max_length=255)

    @field_validator("tenant_slug")
    @classmethod
    def validate_slug(cls, v: str) -> str:
        """Valida que o slug contém apenas caracteres seguros (a-z, 0-9, hífen)."""
        if not re.match(r'^[a-z0-9][a-z0-9-]*[a-z0-9]$', v):
            raise ValueError(
                "Slug deve conter apenas letras minúsculas, números e hífens. "
                "Deve começar e terminar com letra ou número."
            )
        if '--' in v:
            raise ValueError("Slug não pode conter hífens consecutivos")
        return v

    @field_validator("password")
    @classmethod
    def password_strength(cls, v: str) -> str:
        errors = []
        if len(v) < 8:
            errors.append("mínimo 8 caracteres")
        if not any(c.isupper() for c in v):
            errors.append("ao menos uma letra maiúscula")
        if not any(c.islower() for c in v):
            errors.append("ao menos uma letra minúscula")
        if not any(c.isdigit() for c in v):
            errors.append("ao menos um número")
        if not any(c in "!@#$%^&*()_+-=[]{}|;':\",./<>?~`" for c in v):
            errors.append("ao menos um caractere especial (!@#$%...)")
        if errors:
            raise ValueError("Senha fraca: " + ", ".join(errors))

        # Verificar senhas comuns
        common = {"password", "12345678", "admin123", "qwerty123", "password1",
                  "letmein1", "welcome1", "monkey12", "dragon12", "master12"}
        if v.lower().replace("@", "a").replace("!", "i").replace("0", "o") in common:
            raise ValueError("Senha muito comum, escolha outra")

        return v


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int


class MFASetupResponse(BaseModel):
    secret: str
    provisioning_uri: str
    qr_code_base64: str
    recovery_codes: list[str]


class MFAVerifyRequest(BaseModel):
    code: str = Field(min_length=6, max_length=6)


class RefreshTokenRequest(BaseModel):
    refresh_token: str


# ---------------------------------------------------------------------------
# Contract Schemas
# ---------------------------------------------------------------------------

class ContractUploadResponse(BaseModel):
    id: str
    filename: str
    file_type: str
    file_size_bytes: int
    page_count: int
    ocr_used: bool
    status: str
    created_at: datetime


class ContractListItem(BaseModel):
    id: str
    filename: str
    file_type: str
    file_size_bytes: int
    status: str
    created_at: datetime
    analysis_count: int = 0


class ContractListResponse(BaseModel):
    contracts: list[ContractListItem]
    total: int
    page: int = 1
    per_page: int = 20


# ---------------------------------------------------------------------------
# Analysis Schemas
# ---------------------------------------------------------------------------

class AnalysisRequest(BaseModel):
    contract_id: str
    mode: str = Field(pattern="^(defensive|offensive|audit|shield)$")

    @field_validator("contract_id")
    @classmethod
    def validate_contract_uuid(cls, v: str) -> str:
        """Valida que contract_id é um UUID válido."""
        import uuid
        try:
            uuid.UUID(v)
        except (ValueError, AttributeError):
            raise ValueError("contract_id deve ser um UUID válido")
        return v


class AnalysisFindingSchema(BaseModel):
    id: int
    titulo: str
    severidade: str
    clausula: str = ""
    descricao: str
    fundamentacao_legal: str = ""
    recomendacao: str = ""
    impacto_financeiro: str = ""


class AnalysisResponse(BaseModel):
    id: str
    contract_id: str
    mode: str
    status: str
    resumo_executivo: str = ""
    score_risco: int = 0
    achados: list[AnalysisFindingSchema] = []
    total_achados: int = 0
    model_used: str = ""
    tokens_used: int = 0
    cost_usd: float = 0.0
    created_at: datetime
    completed_at: Optional[datetime] = None


class AnalysisListResponse(BaseModel):
    analyses: list[AnalysisResponse]
    total: int


# ---------------------------------------------------------------------------
# Admin Schemas
# ---------------------------------------------------------------------------

class TenantSchema(BaseModel):
    id: str
    name: str
    slug: str
    email: str
    subscription_plan: str
    subscription_status: str
    is_blocked: bool
    blocked_reason: Optional[str] = None
    max_analyses_per_month: int
    max_users: int
    created_at: datetime


class TenantBlockRequest(BaseModel):
    reason: str = Field(min_length=5, max_length=500)


class TenantUpdateRequest(BaseModel):
    name: Optional[str] = None
    subscription_plan: Optional[str] = None
    max_analyses_per_month: Optional[int] = None
    max_users: Optional[int] = None


class TokenUsageSchema(BaseModel):
    tenant_id: str
    tenant_name: str
    total_tokens: int
    total_cost_usd: float
    analysis_count: int
    period: str


class AuditLogSchema(BaseModel):
    id: str
    action: str
    resource_type: Optional[str]
    resource_id: Optional[str]
    user_email: Optional[str] = None
    ip_address: Optional[str]
    severity: str
    created_at: datetime
    details: Optional[dict[str, Any]] = None


# ---------------------------------------------------------------------------
# Report Schemas
# ---------------------------------------------------------------------------

class ReportExportRequest(BaseModel):
    analysis_id: str
    format: str = Field(default="pdf", pattern="^(pdf)$")


# ---------------------------------------------------------------------------
# Common
# ---------------------------------------------------------------------------

class MessageResponse(BaseModel):
    message: str
    detail: Optional[str] = None


class ErrorResponse(BaseModel):
    detail: str
    error_code: Optional[str] = None
