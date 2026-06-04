"""
LegalShield AI 2026 — Config (Projeto B Enterprise)
Configurações do sistema standalone.
"""

from typing import Optional
from pydantic_settings import BaseSettings, SettingsConfigDict


class EnterpriseSettings(BaseSettings):
    """Configurações do Enterprise (standalone)."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # === Aplicação ===
    app_name: str = "LegalShield AI — Enterprise"
    app_version: str = "1.0.0"
    debug: bool = False

    # === Autenticação Simples ===
    admin_username: str = "admin"
    admin_password: str = "Admin@123"
    jwt_secret: str = "enterprise-secret-change-me"

    # === LLM (BYOK) ===
    openai_api_key: Optional[str] = None
    anthropic_api_key: Optional[str] = None
    llm_primary_model: str = "openai/gpt-4o"
    llm_fallback_model: str = "anthropic/claude-sonnet-4-20250514"
    llm_max_tokens: int = 8192
    llm_temperature: float = 0.1

    # === Database ===
    database_path: str = "./data/legalshield.db"

    # === Arquivos ===
    upload_dir: str = "./uploads"
    reports_dir: str = "./reports"
    max_file_size_mb: int = 50


_settings = None

def get_enterprise_settings() -> EnterpriseSettings:
    global _settings
    if _settings is None:
        _settings = EnterpriseSettings()
    return _settings
