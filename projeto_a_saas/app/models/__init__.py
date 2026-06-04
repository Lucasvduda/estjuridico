"""
LegalShield AI 2026 — Models (Projeto A SaaS)
Modelos SQLAlchemy para o sistema multi-tenant.
Compatível com PostgreSQL (produção) e SQLite (desenvolvimento local).
"""

import uuid
from datetime import datetime, timezone

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    Enum as SAEnum,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
    JSON,
    TypeDecorator,
    event,
)
from sqlalchemy.orm import relationship

from ..database import Base


# ---------------------------------------------------------------------------
# Tipos portáveis (PostgreSQL UUID/JSONB → SQLite String/JSON)
# ---------------------------------------------------------------------------

class PortableUUID(TypeDecorator):
    """
    UUID que funciona em PostgreSQL (UUID nativo) e SQLite (CHAR(36)).
    """
    impl = String(36)
    cache_ok = True

    def process_bind_param(self, value, dialect):
        if value is not None:
            if isinstance(value, uuid.UUID):
                return str(value)
            try:
                return str(uuid.UUID(value))
            except (ValueError, AttributeError):
                return str(value)
        return value

    def process_result_value(self, value, dialect):
        if value is not None:
            if not isinstance(value, uuid.UUID):
                return uuid.UUID(value)
        return value

    def load_dialect_impl(self, dialect):
        if dialect.name == "postgresql":
            from sqlalchemy.dialects.postgresql import UUID as PG_UUID
            return dialect.type_descriptor(PG_UUID(as_uuid=True))
        return dialect.type_descriptor(String(36))


class PortableJSON(TypeDecorator):
    """
    JSONB que funciona em PostgreSQL (JSONB nativo) e SQLite (JSON/Text).
    """
    impl = Text
    cache_ok = True

    def process_bind_param(self, value, dialect):
        if value is not None and dialect.name != "postgresql":
            import json
            return json.dumps(value)
        return value

    def process_result_value(self, value, dialect):
        if value is not None and dialect.name != "postgresql":
            import json
            try:
                return json.loads(value)
            except (json.JSONDecodeError, TypeError):
                return value
        return value

    def load_dialect_impl(self, dialect):
        if dialect.name == "postgresql":
            from sqlalchemy.dialects.postgresql import JSONB
            return dialect.type_descriptor(JSONB)
        return dialect.type_descriptor(Text)


# ---------------------------------------------------------------------------
# Tenant / Empresa
# ---------------------------------------------------------------------------

class Tenant(Base):
    """Empresa cliente do SaaS."""
    __tablename__ = "tenants"

    id = Column(PortableUUID(), primary_key=True, default=uuid.uuid4)
    name = Column(String(255), nullable=False)
    slug = Column(String(100), unique=True, nullable=False)
    email = Column(String(255), nullable=False)
    phone = Column(String(50), nullable=True)
    document = Column(String(20), nullable=True)  # CNPJ

    # Assinatura
    subscription_plan = Column(String(50), default="trial")  # trial, basic, pro, enterprise
    subscription_status = Column(String(20), default="active")  # active, suspended, cancelled
    subscription_expires_at = Column(DateTime(timezone=True), nullable=True)

    # Kill-Switch
    is_blocked = Column(Boolean, default=False, nullable=False)
    blocked_at = Column(DateTime(timezone=True), nullable=True)
    blocked_reason = Column(Text, nullable=True)

    # API
    api_key_hash = Column(String(255), nullable=True)
    api_key_prefix = Column(String(10), nullable=True)  # Para identificação visual

    # Limites
    max_analyses_per_month = Column(Integer, default=100)
    max_users = Column(Integer, default=5)

    # White-Label / Tema personalizado
    theme_primary_color = Column(String(7), default="#6C5CE7")  # Roxo jurídico
    theme_accent_color = Column(String(7), default="#00D2D3")   # Teal destaque
    theme_sidebar_color = Column(String(7), default="#1A1A2E")  # Dark sidebar
    theme_bg_color = Column(String(7), default="#0F0F23")       # Dark background
    theme_logo_url = Column(String(500), nullable=True)

    # Timestamps
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    # Relationships
    users = relationship("User", back_populates="tenant", cascade="all, delete-orphan")
    contracts = relationship("Contract", back_populates="tenant", cascade="all, delete-orphan")
    analyses = relationship("Analysis", back_populates="tenant", cascade="all, delete-orphan")
    token_usages = relationship("TokenUsage", back_populates="tenant", cascade="all, delete-orphan")


# ---------------------------------------------------------------------------
# User
# ---------------------------------------------------------------------------

class User(Base):
    """Usuário do sistema."""
    __tablename__ = "users"
    __table_args__ = (
        UniqueConstraint("tenant_id", "email", name="uq_user_tenant_email"),
    )

    id = Column(PortableUUID(), primary_key=True, default=uuid.uuid4)
    tenant_id = Column(PortableUUID(), ForeignKey("tenants.id"), nullable=False)
    email = Column(String(255), nullable=False)
    password_hash = Column(String(255), nullable=False)
    full_name = Column(String(255), nullable=False)
    role = Column(String(20), default="user")  # admin, user, viewer

    # MFA
    mfa_enabled = Column(Boolean, default=False)
    mfa_secret = Column(String(255), nullable=True)  # Encrypted TOTP secret
    mfa_recovery_codes = Column(PortableJSON(), nullable=True)  # Encrypted recovery codes

    # Status
    is_active = Column(Boolean, default=True)
    last_login_at = Column(DateTime(timezone=True), nullable=True)

    # Timestamps
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    # Relationships
    tenant = relationship("Tenant", back_populates="users")


# ---------------------------------------------------------------------------
# Contract
# ---------------------------------------------------------------------------

class Contract(Base):
    """Metadados de um contrato analisado.

    NOTA IMPORTANTE (privacidade / LGPD):
    Esta tabela guarda apenas METADADOS do contrato (nome, tamanho, hash, número
    de páginas). Os BYTES do contrato (PDF/DOCX/TXT) NÃO são armazenados de
    forma persistente — eles vivem temporariamente no Redis durante a janela
    de análise (ver `app/services/contract_cache.py` e `CONTRACT_CACHE_TTL_SECONDS`)
    e somem automaticamente após o TTL. Apenas o RELATÓRIO completo (achados,
    score, resumo, recomendações) é persistido — no modelo `Analysis`.

    Os campos `stored_filename` e `encrypted_path` são opcionais e foram
    mantidos por compatibilidade com bancos legados. Em deploys novos eles
    permanecem `NULL`.
    """
    __tablename__ = "contracts"

    id = Column(PortableUUID(), primary_key=True, default=uuid.uuid4)
    tenant_id = Column(PortableUUID(), ForeignKey("tenants.id"), nullable=False)
    uploaded_by = Column(PortableUUID(), ForeignKey("users.id"), nullable=False)

    # Metadados do arquivo (não-sensíveis)
    original_filename = Column(String(255), nullable=False)
    file_type = Column(String(10), nullable=False)  # pdf, docx, txt
    file_size_bytes = Column(Integer, nullable=False)
    sha256_hash = Column(String(64), nullable=False)

    # Legado — não usados no fluxo novo (mantidos para compatibilidade de schema).
    stored_filename = Column(String(255), nullable=True)
    encrypted_path = Column(String(500), nullable=True)

    # Conteúdo descritivo
    title = Column(String(500), nullable=True)
    description = Column(Text, nullable=True)
    page_count = Column(Integer, default=1)
    ocr_used = Column(Boolean, default=False)

    # Status
    # uploaded   = metadados criados, bytes no Redis aguardando análise
    # processing = worker pegou e está analisando
    # analyzed   = análise terminou (bytes podem ainda estar no Redis até TTL)
    # discarded  = bytes apagados do Redis (TTL ou exclusão manual); só metadados ficam
    # error      = falha de processamento
    status = Column(String(20), default="uploaded")

    # Marca quando os bytes foram apagados do cache (TTL ou ação do usuário).
    bytes_discarded_at = Column(DateTime(timezone=True), nullable=True)

    # Timestamps
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    # Relationships
    tenant = relationship("Tenant", back_populates="contracts")
    analyses = relationship("Analysis", back_populates="contract", cascade="all, delete-orphan")


# ---------------------------------------------------------------------------
# Analysis
# ---------------------------------------------------------------------------

class Analysis(Base):
    """Resultado de uma análise jurídica."""
    __tablename__ = "analyses"

    id = Column(PortableUUID(), primary_key=True, default=uuid.uuid4)
    tenant_id = Column(PortableUUID(), ForeignKey("tenants.id"), nullable=False)
    contract_id = Column(PortableUUID(), ForeignKey("contracts.id"), nullable=False)
    requested_by = Column(PortableUUID(), ForeignKey("users.id"), nullable=False)

    # Análise
    analysis_mode = Column(String(20), nullable=False)  # defensive, offensive, audit, shield
    status = Column(String(20), default="pending")  # pending, processing, completed, failed

    # Resultados
    results_json = Column(PortableJSON(), nullable=True)
    resumo_executivo = Column(Text, nullable=True)
    score_risco = Column(Integer, nullable=True)
    total_achados = Column(Integer, default=0)

    # Segurança
    injection_detected = Column(Boolean, default=False)

    # LLM
    model_used = Column(String(100), nullable=True)
    tokens_used = Column(Integer, default=0)
    cost_usd = Column(Float, default=0.0)
    latency_seconds = Column(Float, default=0.0)

    # Timestamps
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    completed_at = Column(DateTime(timezone=True), nullable=True)

    # Relationships
    tenant = relationship("Tenant", back_populates="analyses")
    contract = relationship("Contract", back_populates="analyses")


# ---------------------------------------------------------------------------
# Audit Log
# ---------------------------------------------------------------------------

class AuditLog(Base):
    """Log de auditoria para rastreamento de atividades."""
    __tablename__ = "audit_logs"

    id = Column(PortableUUID(), primary_key=True, default=uuid.uuid4)
    tenant_id = Column(PortableUUID(), ForeignKey("tenants.id"), nullable=True)
    user_id = Column(PortableUUID(), ForeignKey("users.id"), nullable=True)

    # Ação
    action = Column(String(100), nullable=False)  # login, upload, analyze, block, etc.
    resource_type = Column(String(50), nullable=True)  # contract, analysis, tenant, user
    resource_id = Column(String(50), nullable=True)
    details = Column(PortableJSON(), nullable=True)

    # Contexto
    ip_address = Column(String(45), nullable=True)
    user_agent = Column(String(500), nullable=True)
    severity = Column(String(20), default="info")  # info, warning, critical

    # Timestamp
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))


# ---------------------------------------------------------------------------
# Token Usage (Monitoramento de Consumo)
# ---------------------------------------------------------------------------

class TokenUsage(Base):
    """Registro de consumo de tokens por tenant."""
    __tablename__ = "token_usages"

    id = Column(PortableUUID(), primary_key=True, default=uuid.uuid4)
    tenant_id = Column(PortableUUID(), ForeignKey("tenants.id"), nullable=False)
    analysis_id = Column(PortableUUID(), ForeignKey("analyses.id"), nullable=True)

    # Consumo
    provider = Column(String(20), nullable=False)  # openai, anthropic
    model = Column(String(100), nullable=False)
    prompt_tokens = Column(Integer, default=0)
    completion_tokens = Column(Integer, default=0)
    total_tokens = Column(Integer, default=0)
    cost_usd = Column(Float, default=0.0)

    # Timestamp
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    # Relationships
    tenant = relationship("Tenant", back_populates="token_usages")


# ---------------------------------------------------------------------------
# System Settings (Configurações Dinâmicas de LLM)
# ---------------------------------------------------------------------------

class SystemSettings(Base):
    """Configurações dinâmicas do sistema (key/value).
    Usado para trocar modelos de IA sem mexer no código."""
    __tablename__ = "system_settings"

    key = Column(String(100), primary_key=True)
    value = Column(Text, nullable=False)
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))
