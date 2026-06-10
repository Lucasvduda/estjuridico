"""
LegalShield AI 2026 — Projeto A SaaS
Configurações centrais via Pydantic Settings.
"""

import os
from functools import lru_cache
from pathlib import Path
from typing import Optional

from pydantic_settings import BaseSettings, SettingsConfigDict


def _read_secret(name: str) -> Optional[str]:
    """Lê um segredo de Secret Files do Render (/etc/secrets/<name>)
    ou de variável de ambiente. Render Secret Files têm prioridade sobre env vars."""
    secret_path = Path(f"/etc/secrets/{name}")
    if secret_path.exists():
        value = secret_path.read_text().strip()
        if value:
            return value
    return os.environ.get(name) or None


class Settings(BaseSettings):
    """Configurações do sistema SaaS."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # === Aplicação ===
    app_name: str = "LegalShield AI — SaaS"
    app_version: str = "1.0.0"
    debug: bool = False
    environment: str = "production"

    # === Banco de Dados ===
    database_url: str = "postgresql+asyncpg://legalshield:secret@localhost:5432/legalshield_saas"
    db_pool_size: int = 10
    db_max_overflow: int = 5

    @property
    def async_database_url(self) -> str:
        """Converte DATABASE_URL para o driver asyncpg.

        O Render fornece URLs no formato postgres:// ou postgresql://
        mas o SQLAlchemy async precisa de postgresql+asyncpg://.
        Em dev com SQLite, retorna como está.
        """
        url = self.database_url
        if url.startswith("sqlite"):
            return url
        if url.startswith("postgres://"):
            return url.replace("postgres://", "postgresql+asyncpg://", 1)
        if url.startswith("postgresql://"):
            return url.replace("postgresql://", "postgresql+asyncpg://", 1)
        return url

    # === Redis ===
    # Usado para: fila de jobs (Arq), cache temporário dos bytes do contrato
    # (vivem aqui durante a análise e somem por TTL), kill-switch e rate limit.
    redis_url: str = "redis://localhost:6379/0"

    # TTL (em segundos) dos bytes do contrato no Redis. Após esse tempo, os bytes
    # somem automaticamente. O usuário pode rodar múltiplas análises do mesmo
    # contrato durante essa janela. Padrão: 30 minutos.
    contract_cache_ttl_seconds: int = 1800

    # === Worker (fila de tarefas Arq) ===
    # Quantos jobs em paralelo cada instância de worker processa.
    worker_concurrency: int = 4
    # Limite de jobs por minuto por worker (proteção contra rate-limit de OpenAI/Anthropic).
    worker_max_jobs_per_minute: int = 60
    # Timeout de cada job (segundos). 10 min cobre PDFs grandes + IA lenta.
    worker_job_timeout: int = 600

    # === Autenticação ===
    jwt_secret_key: str = "CHANGE-ME-IN-PRODUCTION-USE-STRONG-RANDOM-KEY"
    jwt_algorithm: str = "HS256"
    jwt_access_token_expire_minutes: int = 15
    jwt_refresh_token_expire_days: int = 7

    # === Criptografia ===
    encryption_master_key: str = "CHANGE-ME-32-BYTES-BASE64-ENCODED-KEY"

    # === LLM ===
    openai_api_key: Optional[str] = None
    anthropic_api_key: Optional[str] = None
    llm_primary_model: str = "openai/gpt-4o"
    llm_fallback_model: str = "anthropic/claude-sonnet-4-20250514"
    llm_max_tokens: int = 8192
    llm_temperature: float = 0.1

    # === Rate Limiting ===
    rate_limit_requests_per_minute: int = 100
    rate_limit_analyses_per_hour: int = 10

    # === Armazenamento de bytes do contrato ===
    # Controla onde os bytes temporários do contrato ficam durante a análise.
    #
    # "auto"   → detecta automaticamente na ordem: r2 → redis → memory
    #            (padrão — funciona local e produção sem mudar código nem .env)
    # "memory" → dict em processo (sem serviços externos, análise inline)
    # "redis"  → Redis com TTL (docker-compose local, até ~100 simultâneos)
    # "r2"     → Cloudflare R2 (produção, 10k+ usuários simultâneos)
    #
    # Regra de auto-detecção:
    #   1. R2_ACCOUNT_ID e R2_ACCESS_KEY_ID preenchidos → r2
    #   2. Redis conectado com sucesso no startup → redis
    #   3. Qualquer outro caso → memory (análise roda inline, sem fila)
    storage_backend: str = "auto"

    # Arquivos
    max_file_size_mb: int = 25
    upload_dir: str = "./uploads"  # fallback legado

    # === Cloudflare R2 (ativo quando storage_backend="r2") ===
    r2_account_id: str = ""
    r2_access_key_id: str = ""
    r2_secret_access_key: str = ""
    r2_bucket_name: str = "legalshield-contracts"
    # Se vazio, montado automaticamente a partir do r2_account_id
    r2_endpoint_url: str = ""

    # === CORS ===
    # Em produção, defina via env: CORS_ORIGINS=["https://app.seudominio.com.br"]
    cors_origins: list[str] = ["http://localhost:3000", "http://localhost:8000"]

    # === Admin ===
    admin_email: str = "lucasvduda90@gmail.com"
    admin_initial_password: str = "@Lucasvd10"


@lru_cache
def get_settings() -> Settings:
    """Retorna instância cacheada das configurações."""
    return Settings()
