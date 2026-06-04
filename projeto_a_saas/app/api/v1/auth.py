"""
LegalShield AI 2026 — Auth Router (Projeto A SaaS)
Endpoints: login, registro, refresh, MFA setup/verify, logout.
"""

import base64
import logging
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from slowapi import Limiter
from slowapi.util import get_remote_address
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ...core.security import (
    create_access_token,
    create_refresh_token,
    decode_token,
    generate_mfa_qr_code,
    generate_mfa_secret,
    generate_recovery_codes,
    get_mfa_provisioning_uri,
    hash_password,
    verify_mfa_code,
    verify_password,
)
from ...config import get_settings
from ...models import Tenant, User
from ...schemas import (
    LoginRequest,
    MFASetupResponse,
    MFAVerifyRequest,
    MessageResponse,
    RefreshTokenRequest,
    RegisterRequest,
    TokenResponse,
)
from ...services.redis_client import get_redis_client
from ...services.memory_fallback import (
    memory_check_brute_force,
    memory_record_failed_login,
    memory_clear_failed_logins,
    memory_blacklist_token,
    memory_is_token_blacklisted,
)
from ..deps import get_current_user, get_db, log_audit
from ...core.field_encryption import encrypt_field, decrypt_field, encrypt_json_field

logger = logging.getLogger(__name__)
settings = get_settings()
router = APIRouter()
limiter = Limiter(key_func=get_remote_address)
security_scheme = HTTPBearer()

# ---------------------------------------------------------------------------
# Helpers: Brute Force Protection & JWT Blacklist
# ---------------------------------------------------------------------------

async def _check_brute_force(email: str) -> None:
    """Verifica se a conta está temporariamente bloqueada por tentativas excessivas."""
    redis = get_redis_client()
    blocked = False
    if redis is not None:
        key = f"login_attempts:{email}"
        attempts = await redis.get(key)
        if attempts and int(attempts) >= 5:
            blocked = True
    else:
        # Fallback em memória — proteção NUNCA fica desabilitada
        blocked = await memory_check_brute_force(email)
    if blocked:
        raise HTTPException(
            status_code=429,
            detail="Conta temporariamente bloqueada por excesso de tentativas. Tente novamente em 15 minutos.",
        )


async def _record_failed_login(email: str) -> None:
    """Registra tentativa de login falha."""
    redis = get_redis_client()
    if redis is not None:
        key = f"login_attempts:{email}"
        await redis.incr(key)
        await redis.expire(key, 900)  # 15 minutos de lockout
    else:
        await memory_record_failed_login(email)


async def _clear_failed_logins(email: str) -> None:
    """Limpa contador de tentativas falhas após login bem-sucedido."""
    redis = get_redis_client()
    if redis is not None:
        await redis.delete(f"login_attempts:{email}")
    else:
        await memory_clear_failed_logins(email)


async def blacklist_token(jti: str, ttl_seconds: int) -> None:
    """Adiciona token JWT à blacklist (Redis ou memória)."""
    redis = get_redis_client()
    if redis is not None:
        await redis.set(f"jwt_blacklist:{jti}", "1", ex=ttl_seconds)
    else:
        await memory_blacklist_token(jti, ttl_seconds)


async def is_token_blacklisted(jti: str) -> bool:
    """Verifica se o token está na blacklist (Redis ou memória)."""
    redis = get_redis_client()
    if redis is not None:
        result = await redis.get(f"jwt_blacklist:{jti}")
        return result is not None
    else:
        return await memory_is_token_blacklisted(jti)



@router.post("/register", response_model=TokenResponse, status_code=201)
async def register(
    body: RegisterRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    """Registra novo tenant + usuário admin."""

    # Verificar se slug ou email já existem (mensagem genérica para evitar enumeração)
    existing_slug = await db.execute(select(Tenant).where(Tenant.slug == body.tenant_slug))
    existing_email = await db.execute(select(User).where(User.email == body.email))
    if existing_slug.scalar_one_or_none() or existing_email.scalar_one_or_none():
        raise HTTPException(
            status_code=409,
            detail="Não foi possível criar a conta. Verifique se o e-mail ou slug já estão em uso."
        )

    # Criar tenant
    tenant = Tenant(
        name=body.tenant_name,
        slug=body.tenant_slug,
        email=body.email,
    )
    db.add(tenant)
    await db.flush()

    # Criar usuário admin
    user = User(
        tenant_id=tenant.id,
        email=body.email,
        password_hash=hash_password(body.password),
        full_name=body.full_name,
        role="admin",
    )
    db.add(user)
    await db.flush()

    # Audit log
    await log_audit(
        db, action="register", user_id=str(user.id),
        tenant_id=str(tenant.id), resource_type="tenant",
        resource_id=str(tenant.id),
        ip_address=request.client.host if request.client else None,
    )

    # Gerar tokens
    access = create_access_token(str(user.id), str(tenant.id), user.role)
    refresh = create_refresh_token(str(user.id), str(tenant.id), user.role)

    return TokenResponse(
        access_token=access,
        refresh_token=refresh,
        expires_in=settings.jwt_access_token_expire_minutes * 60,
    )


@router.post("/login", response_model=TokenResponse)
@limiter.limit("5/minute")
async def login(
    body: LoginRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    """Login com email + senha + MFA opcional. Rate limited: 5 tentativas/min por IP."""

    # Verificar brute force lockout
    await _check_brute_force(body.email)

    result = await db.execute(select(User).where(User.email == body.email))
    user = result.scalar_one_or_none()

    if not user or not verify_password(body.password, user.password_hash):
        await _record_failed_login(body.email)
        raise HTTPException(status_code=401, detail="Credenciais inválidas")

    if not user.is_active:
        raise HTTPException(status_code=403, detail="Conta desativada")

    # Verificar MFA se habilitado
    if user.mfa_enabled:
        if not body.mfa_code:
            raise HTTPException(
                status_code=403,
                detail="Código MFA obrigatório",
                headers={"X-MFA-Required": "true"},
            )
        if not verify_mfa_code(decrypt_field(user.mfa_secret), body.mfa_code):
            await _record_failed_login(body.email)
            raise HTTPException(status_code=401, detail="Código MFA inválido")

    # Login bem-sucedido — limpar tentativas falhas
    await _clear_failed_logins(body.email)

    # Atualizar último login
    user.last_login_at = datetime.now(timezone.utc)
    await db.flush()

    # Audit
    await log_audit(
        db, action="login", user_id=str(user.id),
        tenant_id=str(user.tenant_id),
        ip_address=request.client.host if request.client else None,
    )

    access = create_access_token(str(user.id), str(user.tenant_id), user.role)
    refresh = create_refresh_token(str(user.id), str(user.tenant_id), user.role)

    return TokenResponse(
        access_token=access,
        refresh_token=refresh,
        expires_in=settings.jwt_access_token_expire_minutes * 60,
    )


@router.post("/refresh", response_model=TokenResponse)
async def refresh_token(
    body: RefreshTokenRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    """Renova access token usando refresh token."""
    payload = decode_token(body.refresh_token)
    if not payload or payload.type != "refresh":
        raise HTTPException(status_code=401, detail="Refresh token inválido")

    # Verificar se o refresh token foi revogado (blacklist)
    if await is_token_blacklisted(payload.jti):
        raise HTTPException(status_code=401, detail="Token revogado")

    result = await db.execute(select(User).where(User.id == payload.sub))
    user = result.scalar_one_or_none()
    if not user or not user.is_active:
        raise HTTPException(status_code=401, detail="Usuário inválido")

    # Blacklist o refresh token antigo (rotation)
    await blacklist_token(payload.jti, ttl_seconds=settings.jwt_refresh_token_expire_days * 86400)

    # Audit
    await log_audit(
        db, action="token_refresh", user_id=str(user.id),
        tenant_id=str(user.tenant_id),
        ip_address=request.client.host if request.client else None,
    )

    access = create_access_token(str(user.id), str(user.tenant_id), user.role)
    refresh = create_refresh_token(str(user.id), str(user.tenant_id), user.role)

    return TokenResponse(
        access_token=access,
        refresh_token=refresh,
        expires_in=settings.jwt_access_token_expire_minutes * 60,
    )


@router.post("/mfa/setup", response_model=MFASetupResponse)
async def mfa_setup(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Gera segredo MFA + QR Code para configuração."""
    if user.mfa_enabled:
        raise HTTPException(status_code=400, detail="MFA já está habilitado")

    secret = generate_mfa_secret()
    uri = get_mfa_provisioning_uri(secret, user.email)
    qr_bytes = generate_mfa_qr_code(uri)
    recovery = generate_recovery_codes()

    # Salvar CRIPTOGRAFADO no banco (não ativar até confirmação)
    user.mfa_secret = encrypt_field(secret)
    user.mfa_recovery_codes = encrypt_json_field(recovery)
    await db.flush()

    return MFASetupResponse(
        secret=secret,
        provisioning_uri=uri,
        qr_code_base64=base64.b64encode(qr_bytes).decode(),
        recovery_codes=recovery,
    )


@router.post("/mfa/verify", response_model=MessageResponse)
async def mfa_verify(
    body: MFAVerifyRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Confirma MFA com primeiro código TOTP para ativar."""
    if user.mfa_enabled:
        raise HTTPException(status_code=400, detail="MFA já está ativo")

    if not user.mfa_secret:
        raise HTTPException(status_code=400, detail="Execute /mfa/setup primeiro")

    # Descriptografar o secret para verificar o código TOTP
    decrypted_secret = decrypt_field(user.mfa_secret)
    if not verify_mfa_code(decrypted_secret, body.code):
        raise HTTPException(status_code=400, detail="Código inválido")

    user.mfa_enabled = True
    await db.flush()

    return MessageResponse(message="MFA ativado com sucesso")


@router.post("/logout", response_model=MessageResponse)
async def logout(
    credentials: HTTPAuthorizationCredentials = Depends(security_scheme),
    user: User = Depends(get_current_user),
):
    """Invalida o token atual via blacklist no Redis."""
    payload = decode_token(credentials.credentials)
    if payload:
        # Blacklist o access token pelo tempo restante
        await blacklist_token(
            payload.jti,
            ttl_seconds=settings.jwt_access_token_expire_minutes * 60,
        )
    return MessageResponse(message="Logout realizado com sucesso")
