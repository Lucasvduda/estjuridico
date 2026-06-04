# 🛡️ LegalShield AI — SaaS (Sistema de Assinaturas)

Sistema multi-tenant de análise jurídica de contratos com IA via API.

## Arquitetura

```
projeto_a_saas/
├── app/
│   ├── main.py                   # FastAPI + middlewares
│   ├── config.py                 # Configurações (pydantic-settings)
│   ├── database.py               # PostgreSQL async + RLS
│   ├── models/
│   │   └── __init__.py           # Tenant, User, Contract, Analysis, AuditLog, TokenUsage
│   ├── core/
│   │   ├── security.py           # JWT + MFA (TOTP) + bcrypt
│   │   ├── encryption.py         # AES-256-GCM por tenant (HKDF)
│   │   └── middleware.py         # Kill-Switch + Request Logging
│   └── services/
│       ├── analysis_engine.py    # Orquestrador dos 4 modos de análise
│       ├── document_processor.py # Extração PDF/DOCX/TXT + OCR
│       ├── llm_connector.py      # LiteLLM (OpenAI → Anthropic fallback)
│       ├── prompt_templates.py   # Prompts jurídicos especializados
│       ├── prompt_guard.py       # Anti-prompt-injection
│       └── report_generator.py   # Relatórios PDF profissionais
├── Dockerfile
├── docker-compose.yml
└── requirements.txt
```

## 🧠 Modos de Análise

| Modo | Finalidade |
|------|-----------|
| **Defensivo** | Identificar multas, prazos abusivos, responsabilidades ocultas |
| **Ofensivo** | Encontrar brechas para rescisão/invalidação sem ônus |
| **Auditoria** | Mapear passivos e janelas de renegociação em contratos assinados |
| **Blindagem** | Revisar minutas antes do envio para fechar brechas |

## 🚀 Quick Start

```bash
# 1. Configurar variáveis de ambiente
cp .env.example .env
# Editar .env com suas chaves

# 2. Subir com Docker
docker-compose up -d

# 3. Acessar
# API: http://localhost:8000
# Docs: http://localhost:8000/docs (modo debug)
```

## 🔒 Segurança

| Funcionalidade | Implementação |
|----------------|---------------|
| Criptografia em repouso | AES-256-GCM (chave única por tenant via HKDF) |
| Autenticação | JWT access (15min) + refresh (7d) |
| MFA | TOTP (Google Authenticator) + recovery codes |
| Isolamento de dados | PostgreSQL Row-Level Security |
| Kill-Switch | Bloqueio instantâneo via Redis por tenant |
| Anti-Injection | Detecção de prompt injection em documentos |
| Validação | MIME-type real (magic bytes) + Pydantic v2 |
| Rate Limiting | slowapi (100 req/min, 10 análises/hora) |

## 🛑 Kill-Switch (Admin)

```
POST /admin/tenants/{id}/block   → Bloqueia tenant instantaneamente
POST /admin/tenants/{id}/unblock → Reativa tenant
```

O bloqueio:
- Define flag no Redis (`killswitch:{tenant_id}`)
- Retorna 403 em TODAS as requisições do tenant
- Invalida sessões JWT ativas
- Registra no log de auditoria

## 📋 Requisitos

- Python 3.12+
- PostgreSQL 16+
- Redis 7+
- Docker & Docker Compose
- Tesseract OCR (para documentos escaneados)

## Variáveis de Ambiente

| Variável | Descrição |
|----------|-----------|
| `DATABASE_URL` | URL de conexão PostgreSQL |
| `REDIS_URL` | URL de conexão Redis |
| `JWT_SECRET_KEY` | Chave secreta para JWT |
| `ENCRYPTION_MASTER_KEY` | Chave mestra AES-256 (base64) |
| `OPENAI_API_KEY` | Chave da API OpenAI |
| `ANTHROPIC_API_KEY` | Chave da API Anthropic (fallback) |
