"""
LegalShield AI 2026 — Auth (Projeto B Enterprise)
Login simples com credenciais do .env — sem multi-tenancy.
"""

import logging
from datetime import datetime, timezone, timedelta

import jwt
from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel

from .config import get_enterprise_settings

logger = logging.getLogger(__name__)
settings = get_enterprise_settings()
router = APIRouter()
security_scheme = HTTPBearer(auto_error=False)


class LoginRequest(BaseModel):
    username: str
    password: str


class LoginResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int = 86400  # 24h


def create_token(username: str) -> str:
    """Gera JWT simples para o admin."""
    payload = {
        "sub": username,
        "iat": datetime.now(timezone.utc),
        "exp": datetime.now(timezone.utc) + timedelta(days=1),
    }
    return jwt.encode(payload, settings.jwt_secret, algorithm="HS256")


def verify_token(token: str) -> dict:
    """Verifica JWT."""
    try:
        return jwt.decode(token, settings.jwt_secret, algorithms=["HS256"])
    except jwt.ExpiredSignatureError:
        raise HTTPException(401, "Token expirado")
    except jwt.InvalidTokenError:
        raise HTTPException(401, "Token inválido")


async def require_auth(
    credentials: HTTPAuthorizationCredentials = Depends(security_scheme),
):
    """Dependency: requer autenticação."""
    if not credentials:
        raise HTTPException(401, "Autenticação necessária")
    verify_token(credentials.credentials)
    return True


@router.post("/login", response_model=LoginResponse)
async def login(body: LoginRequest):
    """Login simples com credenciais do .env."""
    if body.username != settings.admin_username or body.password != settings.admin_password:
        raise HTTPException(401, "Credenciais inválidas")

    token = create_token(body.username)
    return LoginResponse(access_token=token)


@router.get("/me")
async def get_me(_: bool = Depends(require_auth)):
    """Retorna dados do usuário logado."""
    return {
        "username": settings.admin_username,
        "role": "admin",
    }
