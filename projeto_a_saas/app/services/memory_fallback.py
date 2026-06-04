"""
LegalShield AI 2026 — In-Memory Security Fallback

Fornece fallback em memória para proteções que dependem de Redis:
  - Brute force protection (tentativas de login)
  - JWT blacklist (tokens revogados)

Ativado automaticamente quando Redis não está disponível.
Thread-safe via asyncio locks. Limpeza automática de entradas expiradas.

NOTA: Em produção, use Redis. Este fallback é para desenvolvimento local
e para garantir que as proteções NUNCA fiquem desabilitadas.
"""

import asyncio
import logging
import time
from typing import Optional

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Brute Force Protection (in-memory fallback)
# ---------------------------------------------------------------------------

_login_attempts: dict[str, list[float]] = {}
_login_lock = asyncio.Lock()

BRUTE_FORCE_MAX_ATTEMPTS = 5
BRUTE_FORCE_WINDOW_SECONDS = 900  # 15 minutos


async def memory_check_brute_force(email: str) -> bool:
    """
    Verifica se o email está temporariamente bloqueado.
    Returns True se bloqueado, False se liberado.
    """
    async with _login_lock:
        now = time.time()
        attempts = _login_attempts.get(email, [])
        # Filtrar apenas tentativas dentro da janela
        recent = [t for t in attempts if now - t < BRUTE_FORCE_WINDOW_SECONDS]
        _login_attempts[email] = recent
        return len(recent) >= BRUTE_FORCE_MAX_ATTEMPTS


async def memory_record_failed_login(email: str) -> None:
    """Registra uma tentativa de login falha."""
    async with _login_lock:
        now = time.time()
        if email not in _login_attempts:
            _login_attempts[email] = []
        _login_attempts[email].append(now)
        # Limpar entradas antigas de vez em quando
        if len(_login_attempts) > 1000:
            _cleanup_login_attempts(now)


async def memory_clear_failed_logins(email: str) -> None:
    """Limpa tentativas falhas após login bem-sucedido."""
    async with _login_lock:
        _login_attempts.pop(email, None)


def _cleanup_login_attempts(now: float) -> None:
    """Remove entradas expiradas para evitar memory leak."""
    expired = [
        email for email, attempts in _login_attempts.items()
        if not attempts or now - max(attempts) > BRUTE_FORCE_WINDOW_SECONDS
    ]
    for email in expired:
        del _login_attempts[email]


# ---------------------------------------------------------------------------
# JWT Blacklist (in-memory fallback)
# ---------------------------------------------------------------------------

_blacklisted_tokens: dict[str, float] = {}  # jti -> expiry_timestamp
_blacklist_lock = asyncio.Lock()


async def memory_blacklist_token(jti: str, ttl_seconds: int) -> None:
    """Adiciona um token à blacklist em memória."""
    async with _blacklist_lock:
        _blacklisted_tokens[jti] = time.time() + ttl_seconds
        # Limpar tokens expirados periodicamente
        if len(_blacklisted_tokens) > 500:
            _cleanup_blacklist()


async def memory_is_token_blacklisted(jti: str) -> bool:
    """Verifica se um token está na blacklist em memória."""
    async with _blacklist_lock:
        expiry = _blacklisted_tokens.get(jti)
        if expiry is None:
            return False
        if time.time() > expiry:
            # Token expirou da blacklist
            del _blacklisted_tokens[jti]
            return False
        return True


def _cleanup_blacklist() -> None:
    """Remove tokens expirados."""
    now = time.time()
    expired = [jti for jti, exp in _blacklisted_tokens.items() if now > exp]
    for jti in expired:
        del _blacklisted_tokens[jti]
