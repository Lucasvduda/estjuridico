#!/usr/bin/env python3
"""
LegalShield AI 2026 — Enterprise Quick Start
Execute: python run_server.py

Faz tudo automaticamente:
  1. Verifica pré-requisitos
  2. Cria ambiente virtual e instala dependências
  3. Gera chaves RSA + licença de teste (se não existem)
  4. Cria banco SQLite e .env
  5. Inicia o servidor FastAPI

Argumentos opcionais:
  python run_server.py --port 8001
  python run_server.py --skip-license  (pula geração de licença)
"""

import argparse
import base64
import hashlib
import os
import platform
import secrets
import shutil
import subprocess
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

# ---------------------------------------------------------------------------
# Cores
# ---------------------------------------------------------------------------
class C:
    OK = "\033[92m"
    WARN = "\033[93m"
    FAIL = "\033[91m"
    BOLD = "\033[1m"
    END = "\033[0m"
    CYAN = "\033[96m"

def info(msg):  print(f"{C.CYAN}[INFO]{C.END} {msg}")
def ok(msg):    print(f"{C.OK}[  OK]{C.END} {msg}")
def warn(msg):  print(f"{C.WARN}[WARN]{C.END} {msg}")
def fail(msg):  print(f"{C.FAIL}[FAIL]{C.END} {msg}")

ROOT = Path(__file__).parent.resolve()
ENV_FILE = ROOT / ".env"
VENV_DIR = ROOT / "venv"


# ---------------------------------------------------------------------------
# 1. Verificar pré-requisitos
# ---------------------------------------------------------------------------
def check_prerequisites():
    print(f"\n{C.BOLD}{'='*60}{C.END}")
    print(f"{C.BOLD}  LEGALSHIELD AI — Enterprise Quick Start{C.END}")
    print(f"{C.BOLD}{'='*60}{C.END}\n")

    v = sys.version_info
    if v.major < 3 or (v.major == 3 and v.minor < 10):
        fail(f"Python 3.10+ necessário (atual: {v.major}.{v.minor})")
        sys.exit(1)
    ok(f"Python {v.major}.{v.minor}.{v.micro}")


# ---------------------------------------------------------------------------
# 2. Ambiente virtual e dependências
# ---------------------------------------------------------------------------
def setup_venv():
    info("Verificando ambiente virtual...")

    py_name = "python" if platform.system() == "Windows" else "python3"
    bin_dir = "Scripts" if platform.system() == "Windows" else "bin"
    venv_python = VENV_DIR / bin_dir / py_name
    venv_pip = VENV_DIR / bin_dir / "pip"

    if not VENV_DIR.exists():
        info("Criando ambiente virtual...")
        subprocess.run([sys.executable, "-m", "venv", str(VENV_DIR)], check=True)
        ok("Ambiente virtual criado")

    info("Instalando dependências (pode demorar na primeira vez)...")
    subprocess.run(
        [str(venv_pip), "install", "-r", str(ROOT / "requirements.txt"), "-q"],
        check=True,
    )
    ok("Dependências instaladas")

    return str(venv_python)


# ---------------------------------------------------------------------------
# 3. Gerar chaves RSA + licença de teste
# ---------------------------------------------------------------------------
def setup_license(skip: bool = False):
    license_file = ROOT / "license.key"
    pubkey_file = ROOT / "public_key.pem"
    keys_dir = ROOT / "keys"

    if license_file.exists() and pubkey_file.exists():
        ok("Licença e chave pública já existem")
        return

    if skip:
        warn("--skip-license: pulando geração de licença")
        warn("Coloque license.key e public_key.pem na raiz antes de rodar o servidor")
        return

    info("Gerando chaves RSA e licença de teste...")

    # Adicionar o projeto ao path para importar o license_manager
    sys.path.insert(0, str(ROOT))

    from app.core.license_manager import (
        LicenseInfo,
        generate_rsa_keypair,
        create_license,
        get_hardware_id,
    )

    # Gerar chaves RSA
    keys_dir.mkdir(exist_ok=True)
    private_pem, public_pem = generate_rsa_keypair()

    priv_path = keys_dir / "private_key.pem"
    pub_path = keys_dir / "public_key.pem"
    priv_path.write_bytes(private_pem)
    pub_path.write_bytes(public_pem)
    ok(f"Chaves RSA geradas em {keys_dir}/")

    # Copiar chave pública para raiz
    pubkey_file.write_bytes(public_pem)

    # Gerar licença de teste para esta máquina
    hw_id = get_hardware_id()
    now = datetime.now(timezone.utc)

    license_info = LicenseInfo(
        customer_id="DEV_LOCAL",
        customer_name="Desenvolvimento Local",
        hardware_id=hw_id,
        issued_at=now.isoformat(),
        expires_at=(now + timedelta(days=365)).isoformat(),
    )

    license_str = create_license(license_info, private_pem)
    license_file.write_text(license_str, encoding="utf-8")

    ok(f"Licença de teste gerada (365 dias)")
    ok(f"Hardware ID: {hw_id[:32]}...")


# ---------------------------------------------------------------------------
# 4. Configurar .env e banco SQLite
# ---------------------------------------------------------------------------
def setup_env():
    if ENV_FILE.exists():
        ok(f".env já existe")
        return

    info("Gerando .env...")

    env_content = """# === LegalShield AI Enterprise — Configuração ===

# === LLMs (coloque suas chaves) ===
OPENAI_API_KEY=
ANTHROPIC_API_KEY=

# === Banco de Dados (SQLite, zero-config) ===
DATABASE_PATH=./data/legalshield.db

# === Diretórios ===
UPLOAD_DIR=./uploads
REPORTS_DIR=./reports

# === Configurações ===
DEBUG=true
"""
    ENV_FILE.write_text(env_content, encoding="utf-8")
    ok(".env criado")
    warn("Edite o .env e coloque sua OPENAI_API_KEY")


def setup_database():
    info("Preparando banco SQLite...")

    data_dir = ROOT / "data"
    data_dir.mkdir(exist_ok=True)
    (ROOT / "uploads").mkdir(exist_ok=True)
    (ROOT / "reports").mkdir(exist_ok=True)

    # Inicializar banco
    sys.path.insert(0, str(ROOT))
    from app.database import init_enterprise_db
    init_enterprise_db()

    ok("Banco SQLite inicializado")


# ---------------------------------------------------------------------------
# 5. Iniciar servidor
# ---------------------------------------------------------------------------
def start_server(python_path: str, port: int = 8001):
    print(f"\n{C.BOLD}{'='*60}{C.END}")
    print(f"{C.OK}  LEGALSHIELD AI Enterprise — PRONTO!{C.END}")
    print(f"{C.BOLD}{'='*60}{C.END}")
    print(f"  API:     http://localhost:{port}")
    print(f"  Docs:    http://localhost:{port}/docs")
    print(f"  Health:  http://localhost:{port}/health")
    print(f"  License: http://localhost:{port}/license")
    print(f"  Ctrl+C para parar\n")

    # Carregar .env
    os.environ.update(_parse_env(ENV_FILE))

    os.execvp(python_path, [
        python_path, "-m", "uvicorn",
        "app.main:app",
        "--reload",
        "--host", "0.0.0.0",
        "--port", str(port),
    ])


def _parse_env(path: Path) -> dict:
    env = {}
    if not path.exists():
        return env
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if "=" in line:
            k, v = line.split("=", 1)
            env[k.strip()] = v.strip().strip('"').strip("'")
    return env


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def main():
    parser = argparse.ArgumentParser(description="LegalShield Enterprise Quick Start")
    parser.add_argument("--port", type=int, default=8001, help="Porta do servidor")
    parser.add_argument("--skip-license", action="store_true", help="Pular geração de licença")
    args = parser.parse_args()

    os.chdir(ROOT)

    check_prerequisites()
    python_path = setup_venv()
    setup_license(skip=args.skip_license)
    setup_env()
    setup_database()
    start_server(python_path, args.port)


if __name__ == "__main__":
    main()
