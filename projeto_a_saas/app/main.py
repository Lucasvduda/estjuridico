"""
LegalShield AI 2026 — Main App (Projeto A SaaS)
Entrada principal do FastAPI com todos os middlewares e rotas.
"""

import logging
import os
from contextlib import asynccontextmanager
from pathlib import Path

import structlog
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded

from .config import get_settings
from .core.middleware import KillSwitchMiddleware, RequestLoggingMiddleware
from .database import init_db, close_db
from .services.redis_client import close_redis_pool, init_redis_pool

settings = get_settings()


# ---------------------------------------------------------------------------
# Structlog Configuration
# ---------------------------------------------------------------------------

def setup_logging():
    """Configura structlog para logging estruturado em JSON."""
    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.processors.add_log_level,
            structlog.processors.StackInfoRenderer(),
            structlog.dev.set_exc_info,
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.JSONRenderer() if not settings.debug else structlog.dev.ConsoleRenderer(),
        ],
        context_class=dict,
        logger_factory=structlog.PrintLoggerFactory(),
        wrapper_class=structlog.make_filtering_bound_logger(
            logging.DEBUG if settings.debug else logging.INFO
        ),
        cache_logger_on_first_use=True,
    )


# ---------------------------------------------------------------------------
# App Lifespan
# ---------------------------------------------------------------------------

async def _ensure_admin_exists(log) -> None:
    """Cria tenant + superadmin se o banco estiver vazio.

    Usa ADMIN_EMAIL e ADMIN_INITIAL_PASSWORD das variáveis de ambiente.
    Idempotente — se o admin já existe, não faz nada.
    """
    from sqlalchemy import select, func
    from .database import async_session_factory
    from .models import Tenant, User
    from .core.security import hash_password

    admin_email = settings.admin_email
    admin_password = settings.admin_initial_password

    try:
        async with async_session_factory() as db:
            # Verificar se já existe um superadmin
            existing = await db.execute(
                select(User).where(User.role == "superadmin")
            )
            superadmin = existing.scalar_one_or_none()
            if superadmin:
                superadmin.email = admin_email
                superadmin.password_hash = hash_password(admin_password)
                await db.commit()
                await log.ainfo("Superadmin atualizado", email=admin_email)
                return

            await log.ainfo("Criando superadmin", email=admin_email)

            # Verificar se o tenant admin já existe
            tenant_q = await db.execute(select(Tenant).where(Tenant.slug == "admin"))
            tenant = tenant_q.scalar_one_or_none()
            if not tenant:
                tenant = Tenant(
                    name="Administração",
                    slug="admin",
                    email=admin_email,
                )
                db.add(tenant)
                await db.flush()

            # Verificar se o email já existe como usuário
            user_q = await db.execute(select(User).where(User.email == admin_email))
            user = user_q.scalar_one_or_none()
            if user:
                user.role = "superadmin"
                user.password_hash = hash_password(admin_password)
                await log.ainfo("Usuário existente promovido a superadmin", email=admin_email)
            else:
                user = User(
                    tenant_id=tenant.id,
                    email=admin_email,
                    password_hash=hash_password(admin_password),
                    full_name="Administrador",
                    role="superadmin",
                )
                db.add(user)
                await log.ainfo("Superadmin criado", email=admin_email)

            await db.commit()
    except Exception as e:
        await log.aerror("Falha ao criar admin automático", error=str(e))


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Gerencia startup e shutdown do app."""
    setup_logging()
    log = structlog.get_logger()

    # Startup
    await log.ainfo("Iniciando LegalShield AI SaaS", version=settings.app_version)

    await init_redis_pool()
    await log.ainfo("Pool Redis inicializado")

    # Cria tabelas se não existirem (seguro em produção — CREATE IF NOT EXISTS)
    await init_db()
    await log.ainfo("Banco de dados inicializado")

    # Criar conta admin automática se não existir
    await _ensure_admin_exists(log)

    yield

    # Shutdown
    await close_db()
    await close_redis_pool()
    await log.ainfo("LegalShield AI SaaS encerrado")


# ---------------------------------------------------------------------------
# FastAPI App
# ---------------------------------------------------------------------------

app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    description="Sistema SaaS de Análise Jurídica com IA",
    docs_url="/docs" if settings.debug else None,
    redoc_url="/redoc" if settings.debug else None,
    lifespan=lifespan,
)

# === Middlewares ===

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type", "X-Requested-With"],
)

# Kill-Switch (usa get_redis_client() internamente — pool inicializado no lifespan)
app.add_middleware(KillSwitchMiddleware)

# Request Logging
app.add_middleware(RequestLoggingMiddleware)

# Rate Limiting (handler de erro)
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)


# === Security Headers Middleware ===

@app.middleware("http")
async def security_headers_middleware(request: Request, call_next):
    """Injeta headers de segurança em todas as respostas."""
    import secrets as _secrets
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["X-XSS-Protection"] = "1; mode=block"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    response.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=()"
    if not settings.debug:
        response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
    response.headers["Content-Security-Policy"] = (
        "default-src 'self'; "
        "script-src 'self' 'unsafe-inline' https://unpkg.com https://cdn.jsdelivr.net; "
        "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com; "
        "font-src 'self' https://fonts.gstatic.com; "
        "img-src 'self' data:; "
        "connect-src 'self' https://unpkg.com https://cdn.jsdelivr.net; "
        "frame-ancestors 'none'"
    )
    return response


# === Health Check ===

@app.get("/health", tags=["Sistema"])
async def health_check():
    """Verifica se o sistema está operacional."""
    return {
        "status": "healthy",
        "version": settings.app_version,
        "service": "legalshield-saas",
    }


# === Rotas da API ===
from .api.v1 import auth, contracts, analysis, reports
from .api.admin import tenants, usage
from .api.admin import llm_settings, theme

app.include_router(auth.router, prefix="/api/v1/auth", tags=["Autenticação"])
app.include_router(contracts.router, prefix="/api/v1/contracts", tags=["Contratos"])
app.include_router(analysis.router, prefix="/api/v1/analysis", tags=["Análise"])
app.include_router(reports.router, prefix="/api/v1/reports", tags=["Relatórios"])
app.include_router(tenants.router, prefix="/api/admin/tenants", tags=["Admin - Tenants"])
app.include_router(usage.router, prefix="/api/admin", tags=["Admin - Monitoramento"])
app.include_router(llm_settings.router, prefix="/api/admin/settings/llm", tags=["Admin - Modelos IA"])
app.include_router(theme.router, prefix="/api/admin/theme", tags=["Admin - Temas"])


# === Frontend (SPA) ===
_frontend_dir = Path(__file__).parent.parent / "frontend"

if (_frontend_dir / "static").exists():
    app.mount("/static", StaticFiles(directory=str(_frontend_dir / "static")), name="static")

if (_frontend_dir / "templates").exists():
    _templates = Jinja2Templates(directory=str(_frontend_dir / "templates"))

    @app.get("/{full_path:path}", response_class=HTMLResponse, include_in_schema=False)
    async def serve_spa(request: Request, full_path: str):
        """Catch-all para SPA — serve index.html para qualquer rota não-API."""
        return _templates.TemplateResponse("index.html", {"request": request})

