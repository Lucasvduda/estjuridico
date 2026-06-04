"""
LegalShield AI 2026 — Main App (Projeto B Enterprise)
FastAPI standalone com validação de licença binária + API completa.
"""

import logging
from contextlib import asynccontextmanager
from pathlib import Path

import structlog
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

logger = logging.getLogger(__name__)

APP_VERSION = "1.0.0"
APP_NAME = "LegalShield AI — Enterprise"
LICENSE_FILE = "./license.key"
PUBLIC_KEY_FILE = "./public_key.pem"


def validate_startup_license():
    """Validação binária de licença na inicialização."""
    from .core.license_manager import validate_license

    license_path = Path(LICENSE_FILE)
    if not license_path.exists():
        print("\n" + "=" * 50)
        print("  ✗ LICENÇA NÃO ENCONTRADA")
        print(f"  Coloque o arquivo '{LICENSE_FILE}' na raiz.")
        print("  Contate o suporte para obter sua licença.")
        print("=" * 50 + "\n")
        raise SystemExit(1)

    license_str = license_path.read_text().strip()

    pub_key = None
    pub_key_path = Path(PUBLIC_KEY_FILE)
    if pub_key_path.exists():
        pub_key = pub_key_path.read_bytes()

    status = validate_license(license_str, pub_key)

    if not status.is_valid:
        print("\n" + "=" * 50)
        print("  ✗ LICENÇA INVÁLIDA")
        print(f"  Motivo: {status.message}")
        print("  Contate o suporte.")
        print("=" * 50 + "\n")
        raise SystemExit(1)

    print(f"\n  ✓ Licença válida — {status.customer_name}")
    print(f"  ✓ {status.days_remaining} dias restantes\n")
    return status


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Gerencia startup e shutdown."""
    # Validar licença (BINÁRIO: funciona ou bloqueia)
    license_status = validate_startup_license()
    app.state.license_status = license_status

    # Inicializar banco SQLite
    from .database import init_enterprise_db
    init_enterprise_db()

    structlog.configure(
        processors=[
            structlog.processors.add_log_level,
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.dev.ConsoleRenderer(),
        ],
        logger_factory=structlog.PrintLoggerFactory(),
    )

    log = structlog.get_logger()
    await log.ainfo(
        "LegalShield Enterprise iniciado",
        version=APP_VERSION,
        customer=license_status.customer_name,
    )

    yield

    await log.ainfo("LegalShield Enterprise encerrado")


app = FastAPI(
    title=APP_NAME,
    version=APP_VERSION,
    description="Sistema Enterprise de Análise Jurídica com IA (Standalone)",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
async def health_check():
    return {
        "status": "healthy",
        "version": APP_VERSION,
        "service": "legalshield-enterprise",
    }


@app.get("/license")
async def license_info():
    """Retorna informações da licença (sem dados sensíveis)."""
    ls = app.state.license_status
    return {
        "is_valid": ls.is_valid,
        "customer_name": ls.customer_name,
        "days_remaining": ls.days_remaining,
        "expires_at": ls.expires_at,
    }


# === Registrar rotas da API ===
from .api import router as api_router
from .auth import router as auth_router
app.include_router(auth_router, prefix="/api/auth", tags=["Autenticação"])
app.include_router(api_router, prefix="/api", tags=["API"])


# === Frontend (SPA) ===
from fastapi import Request as _Request
from fastapi.responses import HTMLResponse as _HTMLResponse
from fastapi.staticfiles import StaticFiles as _StaticFiles
from fastapi.templating import Jinja2Templates as _Jinja2Templates

_frontend_dir = Path(__file__).parent.parent / "frontend"

if (_frontend_dir / "static").exists():
    app.mount("/static", _StaticFiles(directory=str(_frontend_dir / "static")), name="static")

if (_frontend_dir / "templates").exists():
    _templates = _Jinja2Templates(directory=str(_frontend_dir / "templates"))

    @app.get("/{full_path:path}", response_class=_HTMLResponse, include_in_schema=False)
    async def serve_spa(request: _Request, full_path: str):
        """Catch-all para SPA — serve index.html."""
        return _templates.TemplateResponse("index.html", {"request": request})
