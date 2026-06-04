"""
LegalShield AI 2026 — Admin LLM Settings Router (Projeto A SaaS)
Gerenciamento dinâmico de modelos de IA: trocar modelo primário/fallback,
API keys e parâmetros sem mexer no código.
"""

import json
import logging
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ...models import SystemSettings, User
from ..deps import get_db, log_audit, require_role
from ...core.field_encryption import encrypt_field, decrypt_field

logger = logging.getLogger(__name__)
router = APIRouter()


# ---------------------------------------------------------------------------
# Modelos suportados (apenas com API — sem locais)
# ---------------------------------------------------------------------------

SUPPORTED_MODELS = [
    # OpenAI
    {"id": "openai/gpt-4o", "name": "GPT-4o", "provider": "openai"},
    {"id": "openai/gpt-4o-mini", "name": "GPT-4o Mini", "provider": "openai"},
    {"id": "openai/gpt-4-turbo", "name": "GPT-4 Turbo", "provider": "openai"},
    # Google Gemini
    {"id": "gemini/gemini-2.5-flash", "name": "Gemini 2.5 Flash", "provider": "google"},
    {"id": "gemini/gemini-2.5-pro", "name": "Gemini 2.5 Pro", "provider": "google"},
    {"id": "gemini/gemini-2.0-flash", "name": "Gemini 2.0 Flash", "provider": "google"},
    # Anthropic
    {"id": "anthropic/claude-sonnet-4-20250514", "name": "Claude Sonnet 4", "provider": "anthropic"},
    {"id": "anthropic/claude-3-5-sonnet-20241022", "name": "Claude 3.5 Sonnet", "provider": "anthropic"},
    {"id": "anthropic/claude-3-haiku-20240307", "name": "Claude 3 Haiku", "provider": "anthropic"},
    # Mistral
    {"id": "mistral/mistral-large-latest", "name": "Mistral Large", "provider": "mistral"},
    {"id": "mistral/mistral-medium-latest", "name": "Mistral Medium", "provider": "mistral"},
    # Cohere
    {"id": "cohere/command-r-plus", "name": "Command R+", "provider": "cohere"},
    {"id": "cohere/command-r", "name": "Command R", "provider": "cohere"},
]


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------

class LLMSettingsResponse(BaseModel):
    primary_model: str
    fallback_model: str
    temperature: float
    max_tokens: int
    openai_configured: bool
    anthropic_configured: bool
    google_configured: bool
    mistral_configured: bool
    cohere_configured: bool
    supported_models: list[dict]


class LLMSettingsUpdateRequest(BaseModel):
    primary_model: Optional[str] = None
    fallback_model: Optional[str] = None
    temperature: Optional[float] = Field(None, ge=0.0, le=2.0)
    max_tokens: Optional[int] = Field(None, ge=256, le=32768)
    openai_api_key: Optional[str] = None
    anthropic_api_key: Optional[str] = None
    google_api_key: Optional[str] = None
    mistral_api_key: Optional[str] = None
    cohere_api_key: Optional[str] = None


class LLMTestRequest(BaseModel):
    model: str
    prompt: str = "Responda em uma frase: Qual é a função principal de um contrato jurídico?"


class LLMTestResponse(BaseModel):
    success: bool
    model: str
    response: str = ""
    tokens_used: int = 0
    latency_seconds: float = 0.0
    error: str = ""


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

async def _get_setting(db: AsyncSession, key: str, default: str = "") -> str:
    """Busca configuração no banco."""
    result = await db.execute(select(SystemSettings).where(SystemSettings.key == key))
    setting = result.scalar_one_or_none()
    return setting.value if setting else default


async def _set_setting(db: AsyncSession, key: str, value: str) -> None:
    """Salva configuração no banco."""
    result = await db.execute(select(SystemSettings).where(SystemSettings.key == key))
    setting = result.scalar_one_or_none()
    if setting:
        setting.value = value
        setting.updated_at = datetime.now(timezone.utc)
    else:
        db.add(SystemSettings(key=key, value=value))
    await db.flush()


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@router.get("/", response_model=LLMSettingsResponse)
async def get_llm_settings(
    _: User = Depends(require_role("superadmin")),
    db: AsyncSession = Depends(get_db),
):
    """Retorna configurações atuais de LLM."""
    from ...config import get_settings
    settings = get_settings()

    primary = await _get_setting(db, "llm_primary_model", settings.llm_primary_model)
    fallback = await _get_setting(db, "llm_fallback_model", settings.llm_fallback_model)
    temp = await _get_setting(db, "llm_temperature", str(settings.llm_temperature))
    max_tok = await _get_setting(db, "llm_max_tokens", str(settings.llm_max_tokens))

    # API keys são criptografadas no banco — verificar se existem (não descriptografar no response)
    async def _has_api_key(db_session, key_name, fallback):
        stored = await _get_setting(db_session, key_name, "")
        return bool(stored or fallback)

    return LLMSettingsResponse(
        primary_model=primary,
        fallback_model=fallback,
        temperature=float(temp),
        max_tokens=int(max_tok),
        openai_configured=await _has_api_key(db, "openai_api_key", settings.openai_api_key or ""),
        anthropic_configured=await _has_api_key(db, "anthropic_api_key", settings.anthropic_api_key or ""),
        google_configured=await _has_api_key(db, "google_api_key", ""),
        mistral_configured=await _has_api_key(db, "mistral_api_key", ""),
        cohere_configured=await _has_api_key(db, "cohere_api_key", ""),
        supported_models=SUPPORTED_MODELS,
    )


@router.put("/", response_model=LLMSettingsResponse)
async def update_llm_settings(
    body: LLMSettingsUpdateRequest,
    admin: User = Depends(require_role("superadmin")),
    db: AsyncSession = Depends(get_db),
):
    """Atualiza configurações de LLM (troca modelo sem mexer no código)."""
    changes = {}

    if body.primary_model is not None:
        valid_ids = [m["id"] for m in SUPPORTED_MODELS]
        if body.primary_model not in valid_ids:
            raise HTTPException(400, f"Modelo não suportado: {body.primary_model}")
        await _set_setting(db, "llm_primary_model", body.primary_model)
        changes["primary_model"] = body.primary_model

    if body.fallback_model is not None:
        valid_ids = [m["id"] for m in SUPPORTED_MODELS]
        if body.fallback_model not in valid_ids:
            raise HTTPException(400, f"Modelo não suportado: {body.fallback_model}")
        await _set_setting(db, "llm_fallback_model", body.fallback_model)
        changes["fallback_model"] = body.fallback_model

    if body.temperature is not None:
        await _set_setting(db, "llm_temperature", str(body.temperature))
        changes["temperature"] = body.temperature

    if body.max_tokens is not None:
        await _set_setting(db, "llm_max_tokens", str(body.max_tokens))
        changes["max_tokens"] = body.max_tokens

    # API Keys (criptografadas no banco, mascaradas no log)
    for key_name in ["openai_api_key", "anthropic_api_key", "google_api_key", "mistral_api_key", "cohere_api_key"]:
        value = getattr(body, key_name, None)
        if value is not None:
            # Criptografar antes de salvar no banco
            encrypted_value = encrypt_field(value)
            await _set_setting(db, key_name, encrypted_value)
            changes[key_name] = f"***{value[-4:]}" if len(value) > 4 else "***"
            # Injetar valor REAL (não criptografado) no ambiente para LiteLLM
            import os
            env_map = {
                "openai_api_key": "OPENAI_API_KEY",
                "anthropic_api_key": "ANTHROPIC_API_KEY",
                "google_api_key": "GEMINI_API_KEY",
                "mistral_api_key": "MISTRAL_API_KEY",
                "cohere_api_key": "COHERE_API_KEY",
            }
            os.environ[env_map[key_name]] = value

    await log_audit(
        db, action="update_llm_settings", user_id=str(admin.id),
        details=changes, severity="warning",
    )

    return await get_llm_settings(admin, db)


@router.post("/test", response_model=LLMTestResponse)
async def test_llm_connection(
    body: LLMTestRequest,
    _: User = Depends(require_role("superadmin")),
    db: AsyncSession = Depends(get_db),
):
    """Testa conexão com um modelo específico."""
    import time
    try:
        import litellm
        litellm.set_verbose = False

        start = time.time()
        response = await litellm.acompletion(
            model=body.model,
            messages=[
                {"role": "system", "content": "Você é um assistente jurídico."},
                {"role": "user", "content": body.prompt},
            ],
            max_tokens=200,
            temperature=0.3,
            timeout=30,
        )
        latency = time.time() - start

        return LLMTestResponse(
            success=True,
            model=body.model,
            response=response.choices[0].message.content,
            tokens_used=response.usage.total_tokens,
            latency_seconds=round(latency, 2),
        )
    except Exception as e:
        return LLMTestResponse(
            success=False,
            model=body.model,
            error=str(e),
        )
