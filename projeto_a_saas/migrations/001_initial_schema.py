"""
LegalShield AI 2026 — Alembic Migration: Initial Schema
Com RLS (Row-Level Security) policies para PostgreSQL.
"""

# Script SQL para ser executado via Alembic ou manualmente.
# Gera todas as tabelas + políticas RLS.

MIGRATION_UP = """
-- ============================================
-- EXTENSÃO
-- ============================================
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- ============================================
-- TABELAS
-- ============================================

CREATE TABLE IF NOT EXISTS tenants (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    name VARCHAR(255) NOT NULL,
    slug VARCHAR(100) UNIQUE NOT NULL,
    email VARCHAR(255) NOT NULL,
    phone VARCHAR(50),
    document VARCHAR(20),
    subscription_plan VARCHAR(50) DEFAULT 'trial',
    subscription_status VARCHAR(20) DEFAULT 'active',
    subscription_expires_at TIMESTAMPTZ,
    is_blocked BOOLEAN DEFAULT FALSE NOT NULL,
    blocked_at TIMESTAMPTZ,
    blocked_reason TEXT,
    api_key_hash VARCHAR(255),
    api_key_prefix VARCHAR(10),
    max_analyses_per_month INTEGER DEFAULT 100,
    max_users INTEGER DEFAULT 5,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS users (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    email VARCHAR(255) NOT NULL,
    password_hash VARCHAR(255) NOT NULL,
    full_name VARCHAR(255) NOT NULL,
    role VARCHAR(20) DEFAULT 'user',
    mfa_enabled BOOLEAN DEFAULT FALSE,
    mfa_secret VARCHAR(255),
    mfa_recovery_codes JSONB,
    is_active BOOLEAN DEFAULT TRUE,
    last_login_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE (tenant_id, email)
);

CREATE TABLE IF NOT EXISTS contracts (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    uploaded_by UUID NOT NULL REFERENCES users(id),
    original_filename VARCHAR(255) NOT NULL,
    stored_filename VARCHAR(255) NOT NULL,
    file_type VARCHAR(10) NOT NULL,
    file_size_bytes INTEGER NOT NULL,
    sha256_hash VARCHAR(64) NOT NULL,
    encrypted_path VARCHAR(500) NOT NULL,
    title VARCHAR(500),
    description TEXT,
    page_count INTEGER DEFAULT 1,
    ocr_used BOOLEAN DEFAULT FALSE,
    status VARCHAR(20) DEFAULT 'uploaded',
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS analyses (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    contract_id UUID NOT NULL REFERENCES contracts(id) ON DELETE CASCADE,
    requested_by UUID NOT NULL REFERENCES users(id),
    analysis_mode VARCHAR(20) NOT NULL,
    status VARCHAR(20) DEFAULT 'pending',
    results_json JSONB,
    resumo_executivo TEXT,
    score_risco INTEGER,
    total_achados INTEGER DEFAULT 0,
    injection_detected BOOLEAN DEFAULT FALSE,
    model_used VARCHAR(100),
    tokens_used INTEGER DEFAULT 0,
    cost_usd DOUBLE PRECISION DEFAULT 0.0,
    latency_seconds DOUBLE PRECISION DEFAULT 0.0,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    completed_at TIMESTAMPTZ
);

CREATE TABLE IF NOT EXISTS audit_logs (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    tenant_id UUID REFERENCES tenants(id),
    user_id UUID REFERENCES users(id),
    action VARCHAR(100) NOT NULL,
    resource_type VARCHAR(50),
    resource_id VARCHAR(50),
    details JSONB,
    ip_address VARCHAR(45),
    user_agent VARCHAR(500),
    severity VARCHAR(20) DEFAULT 'info',
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS token_usages (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    analysis_id UUID REFERENCES analyses(id),
    provider VARCHAR(20) NOT NULL,
    model VARCHAR(100) NOT NULL,
    prompt_tokens INTEGER DEFAULT 0,
    completion_tokens INTEGER DEFAULT 0,
    total_tokens INTEGER DEFAULT 0,
    cost_usd DOUBLE PRECISION DEFAULT 0.0,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- ============================================
-- INDEXES
-- ============================================

CREATE INDEX IF NOT EXISTS idx_users_tenant ON users(tenant_id);
CREATE INDEX IF NOT EXISTS idx_users_email ON users(email);
CREATE INDEX IF NOT EXISTS idx_contracts_tenant ON contracts(tenant_id);
CREATE INDEX IF NOT EXISTS idx_contracts_status ON contracts(status);
CREATE INDEX IF NOT EXISTS idx_analyses_tenant ON analyses(tenant_id);
CREATE INDEX IF NOT EXISTS idx_analyses_contract ON analyses(contract_id);
CREATE INDEX IF NOT EXISTS idx_analyses_mode ON analyses(analysis_mode);
CREATE INDEX IF NOT EXISTS idx_audit_tenant ON audit_logs(tenant_id);
CREATE INDEX IF NOT EXISTS idx_audit_action ON audit_logs(action);
CREATE INDEX IF NOT EXISTS idx_audit_created ON audit_logs(created_at);
CREATE INDEX IF NOT EXISTS idx_token_usage_tenant ON token_usages(tenant_id);
CREATE INDEX IF NOT EXISTS idx_token_usage_created ON token_usages(created_at);

-- ============================================
-- ROW-LEVEL SECURITY (RLS)
-- ============================================

-- Habilitar RLS em todas as tabelas multi-tenant
ALTER TABLE users ENABLE ROW LEVEL SECURITY;
ALTER TABLE contracts ENABLE ROW LEVEL SECURITY;
ALTER TABLE analyses ENABLE ROW LEVEL SECURITY;
ALTER TABLE token_usages ENABLE ROW LEVEL SECURITY;
ALTER TABLE audit_logs ENABLE ROW LEVEL SECURITY;

-- Políticas: cada tenant só vê seus próprios dados
-- A variável app.current_tenant_id é setada via SET no middleware

CREATE POLICY tenant_isolation_users ON users
    USING (tenant_id::text = current_setting('app.current_tenant_id', true))
    WITH CHECK (tenant_id::text = current_setting('app.current_tenant_id', true));

CREATE POLICY tenant_isolation_contracts ON contracts
    USING (tenant_id::text = current_setting('app.current_tenant_id', true))
    WITH CHECK (tenant_id::text = current_setting('app.current_tenant_id', true));

CREATE POLICY tenant_isolation_analyses ON analyses
    USING (tenant_id::text = current_setting('app.current_tenant_id', true))
    WITH CHECK (tenant_id::text = current_setting('app.current_tenant_id', true));

CREATE POLICY tenant_isolation_token_usages ON token_usages
    USING (tenant_id::text = current_setting('app.current_tenant_id', true))
    WITH CHECK (tenant_id::text = current_setting('app.current_tenant_id', true));

CREATE POLICY tenant_isolation_audit_logs ON audit_logs
    USING (tenant_id::text = current_setting('app.current_tenant_id', true))
    WITH CHECK (tenant_id::text = current_setting('app.current_tenant_id', true));

-- ============================================
-- CONFIGURAÇÃO DO POSTGRES
-- ============================================

-- Criar variável customizada (necessária para RLS)
ALTER DATABASE legalshield_saas SET app.current_tenant_id = '';
"""

MIGRATION_DOWN = """
DROP POLICY IF EXISTS tenant_isolation_audit_logs ON audit_logs;
DROP POLICY IF EXISTS tenant_isolation_token_usages ON token_usages;
DROP POLICY IF EXISTS tenant_isolation_analyses ON analyses;
DROP POLICY IF EXISTS tenant_isolation_contracts ON contracts;
DROP POLICY IF EXISTS tenant_isolation_users ON users;

DROP TABLE IF EXISTS token_usages CASCADE;
DROP TABLE IF EXISTS audit_logs CASCADE;
DROP TABLE IF EXISTS analyses CASCADE;
DROP TABLE IF EXISTS contracts CASCADE;
DROP TABLE IF EXISTS users CASCADE;
DROP TABLE IF EXISTS tenants CASCADE;
"""
