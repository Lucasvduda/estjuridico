"""
LegalShield AI 2026 — Security Core (Projeto A SaaS)
JWT, hashing de senha, MFA TOTP e utilitários de segurança.
"""

import secrets
import io
from datetime import datetime, timedelta, timezone
from typing import Optional

import bcrypt
import pyotp
import qrcode
from jose import JWTError, jwt
from pydantic import BaseModel

from ..config import get_settings

settings = get_settings()

# ---------------------------------------------------------------------------
# Password Hashing
# ---------------------------------------------------------------------------


def _prep(password: str) -> bytes:
    """Encode and truncate to 72 bytes (bcrypt hard limit)."""
    return password.encode("utf-8")[:72]


def hash_password(password: str) -> str:
    """Gera hash bcrypt da senha."""
    return bcrypt.hashpw(_prep(password), bcrypt.gensalt()).decode("utf-8")


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verifica senha contra o hash."""
    try:
        prepped = _prep(plain_password)
        hashed_bytes = hashed_password.encode("utf-8")
        result = bcrypt.checkpw(prepped, hashed_bytes)
        # DEBUG TEMPORÁRIO — remover após resolver o problema de login
        print(f"[DEBUG verify_password] plain_password repr: {repr(plain_password)}")
        print(f"[DEBUG verify_password] prepped: {prepped}")
        print(f"[DEBUG verify_password] hashed_password: {hashed_password[:20]}...")
        print(f"[DEBUG verify_password] result: {result}")
        return result
    except Exception as e:
        print(f"[DEBUG verify_password] EXCEPTION: {type(e).__name__}: {e}")
        return False


# ---------------------------------------------------------------------------
# JWT Tokens
# ---------------------------------------------------------------------------

class TokenPayload(BaseModel):
    """Payload do JWT."""
    sub: str  # user_id
    tenant_id: str
    role: str
    exp: datetime
    type: str  # "access" ou "refresh"
    jti: str  # JWT ID (para blacklist)


def create_access_token(
    user_id: str,
    tenant_id: str,
    role: str,
) -> str:
    """Cria access token JWT (curta duração)."""
    expire = datetime.now(timezone.utc) + timedelta(
        minutes=settings.jwt_access_token_expire_minutes
    )
    payload = {
        "sub": str(user_id),
        "tenant_id": str(tenant_id),
        "role": role,
        "exp": expire,
        "type": "access",
        "jti": secrets.token_hex(16),
    }
    return jwt.encode(payload, settings.jwt_secret_key, algorithm=settings.jwt_algorithm)


def create_refresh_token(
    user_id: str,
    tenant_id: str,
    role: str,
) -> str:
    """Cria refresh token JWT (longa duração)."""
    expire = datetime.now(timezone.utc) + timedelta(
        days=settings.jwt_refresh_token_expire_days
    )
    payload = {
        "sub": str(user_id),
        "tenant_id": str(tenant_id),
        "role": role,
        "exp": expire,
        "type": "refresh",
        "jti": secrets.token_hex(16),
    }
    return jwt.encode(payload, settings.jwt_secret_key, algorithm=settings.jwt_algorithm)


def decode_token(token: str) -> Optional[TokenPayload]:
    """Decodifica e valida JWT token."""
    try:
        payload = jwt.decode(
            token,
            settings.jwt_secret_key,
            algorithms=[settings.jwt_algorithm],
        )
        return TokenPayload(**payload)
    except JWTError:
        return None


# ---------------------------------------------------------------------------
# MFA (TOTP)
# ---------------------------------------------------------------------------

def generate_mfa_secret() -> str:
    """Gera novo segredo TOTP para MFA."""
    return pyotp.random_base32()


def get_mfa_provisioning_uri(
    secret: str,
    email: str,
    issuer: str = "LegalShield AI",
) -> str:
    """Gera URI de provisionamento para Google Authenticator."""
    totp = pyotp.TOTP(secret)
    return totp.provisioning_uri(name=email, issuer_name=issuer)


def generate_mfa_qr_code(provisioning_uri: str) -> bytes:
    """Gera QR Code PNG para configuração do MFA."""
    qr = qrcode.QRCode(version=1, box_size=10, border=5)
    qr.add_data(provisioning_uri)
    qr.make(fit=True)

    img = qr.make_image(fill_color="black", back_color="white")
    buffer = io.BytesIO()
    img.save(buffer, format="PNG")
    return buffer.getvalue()


def verify_mfa_code(secret: str, code: str) -> bool:
    """Verifica código TOTP do MFA."""
    totp = pyotp.TOTP(secret)
    return totp.verify(code, valid_window=1)  # ±30 segundos de tolerância


def generate_recovery_codes(count: int = 8) -> list[str]:
    """Gera códigos de recuperação de uso único."""
    return [secrets.token_hex(4).upper() for _ in range(count)]


# ---------------------------------------------------------------------------
# API Key
# ---------------------------------------------------------------------------

def generate_api_key() -> tuple[str, str, str]:
    """
    Gera API key para tenant.
    Retorna: (key_completa, prefix, hash)
    """
    prefix = "ls_" + secrets.token_hex(3)
    body = secrets.token_hex(24)
    full_key = f"{prefix}_{body}"
    key_hash = hash_password(full_key)
    return full_key, prefix, key_hash


def verify_api_key(key: str, key_hash: str) -> bool:
    """Verifica API key contra o hash."""
    return verify_password(key, key_hash)
