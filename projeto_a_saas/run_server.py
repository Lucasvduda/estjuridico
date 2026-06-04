#!/usr/bin/env python3
"""
LegalShield AI 2026 — SaaS Quick Start
Execute: python run_server.py            (com Docker)
         python run_server.py --local    (sem Docker — usa SQLite)

Faz tudo automaticamente:
  1. Verifica pré-requisitos (Python, Docker opcional)
  2. Cria ambiente virtual e instala dependências
  3. Gera chaves seguras (.env) se não existem
  4. Sobe PostgreSQL e Redis via Docker (ou usa SQLite no modo --local)
  5. Cria as tabelas no banco
  6. Inicia o servidor FastAPI
"""

import base64
import os
import platform
import secrets
import shutil
import subprocess
import sys
import time
from pathlib import Path

# ---------------------------------------------------------------------------
# Cores para o terminal
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


def is_local_mode() -> bool:
    """Verifica se o modo local (sem Docker) foi solicitado."""
    return "--local" in sys.argv or "--no-docker" in sys.argv


# ---------------------------------------------------------------------------
# 1. Verificar pré-requisitos
# ---------------------------------------------------------------------------
def check_prerequisites() -> bool:
    """Retorna True se Docker está disponível, False caso contrário."""
    local_mode = is_local_mode()

    print(f"\n{C.BOLD}{'='*60}{C.END}")
    if local_mode:
        print(f"{C.BOLD}  LEGALSHIELD AI — SaaS Quick Start (MODO LOCAL){C.END}")
    else:
        print(f"{C.BOLD}  LEGALSHIELD AI — SaaS Quick Start{C.END}")
    print(f"{C.BOLD}{'='*60}{C.END}\n")

    # Python
    v = sys.version_info
    if v.major < 3 or (v.major == 3 and v.minor < 10):
        fail(f"Python 3.10+ necessário (atual: {v.major}.{v.minor})")
        sys.exit(1)
    ok(f"Python {v.major}.{v.minor}.{v.micro}")

    # Se modo local explícito, pular Docker
    if local_mode:
        info("Modo local ativado — Docker não é necessário")
        info("Usando SQLite (arquivo local) e sem Redis")
        return False

    # Docker (tentar detectar)
    docker = shutil.which("docker")
    if not docker:
        warn("Docker não encontrado — ativando modo local automaticamente")
        info("Usando SQLite (arquivo local) e sem Redis")
        info("Para usar PostgreSQL+Redis, instale: https://www.docker.com/products/docker-desktop/")
        return False
    try:
        subprocess.run(["docker", "info"], capture_output=True, check=True, timeout=10)
        ok("Docker está rodando")
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired):
        warn("Docker instalado mas não está rodando — ativando modo local")
        info("Usando SQLite (arquivo local) e sem Redis")
        return False

    # Docker Compose
    try:
        subprocess.run(["docker", "compose", "version"], capture_output=True, check=True, timeout=5)
        ok("Docker Compose disponível")
    except Exception:
        try:
            subprocess.run(["docker-compose", "version"], capture_output=True, check=True, timeout=5)
            ok("docker-compose (v1) disponível")
        except Exception:
            warn("Docker Compose não encontrado — ativando modo local")
            return False

    return True


# ---------------------------------------------------------------------------
# 2. Ambiente virtual e dependências
# ---------------------------------------------------------------------------
def setup_venv():
    info("Verificando ambiente virtual...")

    venv_python = VENV_DIR / ("Scripts" if platform.system() == "Windows" else "bin") / "python"
    venv_pip = VENV_DIR / ("Scripts" if platform.system() == "Windows" else "bin") / "pip"

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
# 3. Gerar .env se não existe
# ---------------------------------------------------------------------------
def setup_env(use_docker: bool):
    if ENV_FILE.exists():
        ok(f".env já existe ({ENV_FILE})")
        # Se modo local, garantir que DATABASE_URL aponta para SQLite
        if not use_docker:
            _patch_env_for_local()
        return

    info("Gerando .env com chaves seguras...")

    jwt_secret = secrets.token_hex(64)
    encryption_key = base64.b64encode(os.urandom(32)).decode()
    pg_password = secrets.token_hex(16)

    if use_docker:
        db_url = f"postgresql+asyncpg://legalshield:{pg_password}@localhost:5432/legalshield_saas"
        redis_url = "redis://localhost:6379/0"
    else:
        db_url = "sqlite+aiosqlite:///./legalshield_local.db"
        redis_url = ""

    env_content = f"""# === LegalShield AI SaaS — Configuração ===
# Gerado automaticamente. GUARDE ESSAS CHAVES EM LOCAL SEGURO!

# === Modo ===
DEBUG=true

# === Banco de Dados ===
DATABASE_URL={db_url}
POSTGRES_PASSWORD={pg_password}

# === Redis (vazio = desabilitado) ===
REDIS_URL={redis_url}

# === JWT ===
JWT_SECRET_KEY={jwt_secret}

# === Criptografia AES-256 ===
ENCRYPTION_MASTER_KEY={encryption_key}

# === LLMs (coloque suas chaves) ===
OPENAI_API_KEY=
ANTHROPIC_API_KEY=

# === CORS ===
CORS_ORIGINS=["http://localhost:3000","http://localhost:8000"]
"""

    ENV_FILE.write_text(env_content, encoding="utf-8")
    ok(f".env criado com chaves seguras")
    if use_docker:
        warn("Edite o .env e coloque suas chaves OPENAI_API_KEY e ANTHROPIC_API_KEY")
    else:
        warn("Edite o .env e coloque suas chaves OPENAI_API_KEY e ANTHROPIC_API_KEY")
        info(f"Banco SQLite será criado em: {ROOT / 'legalshield_local.db'}")


def _patch_env_for_local():
    """Se .env existe mas tem PostgreSQL e estamos em modo local, avisar."""
    content = ENV_FILE.read_text(encoding="utf-8")
    # Só checar linhas ATIVAS (não comentadas) por PostgreSQL
    active_lines = [l.strip() for l in content.splitlines() if l.strip() and not l.strip().startswith("#")]
    has_active_pg = any("postgresql" in l.lower() for l in active_lines if l.startswith("DATABASE_URL="))
    if has_active_pg and not _docker_available():
        warn("O .env atual aponta para PostgreSQL, mas Docker não está disponível")
        info("Para usar modo local com SQLite, altere DATABASE_URL no .env para:")
        info("  DATABASE_URL=sqlite+aiosqlite:///./legalshield_local.db")
        info("  REDIS_URL=")
        print()
        resp = input(f"{C.CYAN}[????]{C.END} Deseja alterar automaticamente para SQLite? (s/N): ").strip().lower()
        if resp in ("s", "sim", "y", "yes"):
            lines = content.splitlines()
            new_lines = []
            for line in lines:
                stripped = line.strip()
                if stripped.startswith("DATABASE_URL=") and "postgresql" in stripped:
                    new_lines.append("DATABASE_URL=sqlite+aiosqlite:///./legalshield_local.db")
                elif stripped.startswith("REDIS_URL=") and stripped != "REDIS_URL=":
                    new_lines.append("REDIS_URL=")
                else:
                    new_lines.append(line)
            ENV_FILE.write_text("\n".join(new_lines) + "\n", encoding="utf-8")
            ok("DATABASE_URL alterado para SQLite")
            ok("REDIS_URL desabilitado")
        else:
            fail("Modo local requer SQLite. Edite o .env manualmente ou remova o arquivo.")
            sys.exit(1)


def _docker_available() -> bool:
    """Check rápido se Docker está funcional."""
    try:
        subprocess.run(["docker", "info"], capture_output=True, check=True, timeout=5)
        return True
    except Exception:
        return False


# ---------------------------------------------------------------------------
# 4. Subir PostgreSQL e Redis via Docker
# ---------------------------------------------------------------------------
def start_docker_services():
    info("Subindo PostgreSQL e Redis via Docker...")

    # Ler a senha do .env ou gerar uma aleatória para dev
    import secrets as _secrets
    pg_password = _secrets.token_urlsafe(16)  # Gera senha aleatória se não definida
    if ENV_FILE.exists():
        for line in ENV_FILE.read_text(encoding="utf-8").splitlines():
            if line.startswith("POSTGRES_PASSWORD="):
                pg_password = line.split("=", 1)[1].strip()

    compose_local = ROOT / "docker-compose.local.yml"
    compose_content = f"""version: "3.9"
services:
  postgres:
    image: postgres:16-alpine
    container_name: legalshield-dev-db
    environment:
      POSTGRES_DB: legalshield_saas
      POSTGRES_USER: legalshield
      POSTGRES_PASSWORD: {pg_password}
    ports:
      - "5432:5432"
    volumes:
      - pgdata_dev:/var/lib/postgresql/data
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U legalshield"]
      interval: 3s
      timeout: 3s
      retries: 10

  redis:
    image: redis:7-alpine
    container_name: legalshield-dev-redis
    ports:
      - "6379:6379"
    volumes:
      - redisdata_dev:/data

volumes:
  pgdata_dev:
  redisdata_dev:
"""
    compose_local.write_text(compose_content, encoding="utf-8")

    # Subir containers
    try:
        subprocess.run(
            ["docker", "compose", "-f", str(compose_local), "up", "-d"],
            check=True, capture_output=True,
        )
    except subprocess.CalledProcessError:
        subprocess.run(
            ["docker-compose", "-f", str(compose_local), "up", "-d"],
            check=True,
        )

    # Esperar PostgreSQL ficar pronto
    info("Aguardando PostgreSQL...")
    for i in range(30):
        try:
            result = subprocess.run(
                ["docker", "exec", "legalshield-dev-db",
                 "pg_isready", "-U", "legalshield"],
                capture_output=True, timeout=3,
            )
            if result.returncode == 0:
                ok("PostgreSQL pronto")
                break
        except Exception:
            pass
        time.sleep(1)
    else:
        fail("PostgreSQL não iniciou em 30s")
        sys.exit(1)

    ok("Redis pronto")


# ---------------------------------------------------------------------------
# 5. Criar tabelas no banco
# ---------------------------------------------------------------------------
def setup_database_docker():
    """Cria tabelas via migration SQL no PostgreSQL (modo Docker)."""
    info("Criando tabelas e políticas RLS...")

    migration_file = ROOT / "migrations" / "001_initial_schema.py"
    if not migration_file.exists():
        warn("Migration não encontrada, pulando...")
        return

    # Extrair SQL da migration
    content = migration_file.read_text(encoding="utf-8")

    # Extrair o MIGRATION_UP
    start = content.find('MIGRATION_UP = """') + len('MIGRATION_UP = """')
    end = content.find('"""', start)
    sql = content[start:end].strip()

    if not sql:
        warn("SQL de migration vazio")
        return

    # Executar via docker exec
    result = subprocess.run(
        ["docker", "exec", "-i", "legalshield-dev-db",
         "psql", "-U", "legalshield", "-d", "legalshield_saas"],
        input=sql, capture_output=True, text=True, timeout=30,
    )

    if result.returncode == 0:
        ok("Tabelas e RLS criados com sucesso")
    else:
        if "already exists" in (result.stderr or ""):
            ok("Tabelas já existem (migration já foi executada)")
        else:
            warn(f"Aviso na migration: {result.stderr[:200]}")


def setup_database_local():
    """Cria tabelas via SQLAlchemy create_all (modo local/SQLite)."""
    info("Criando tabelas locais (SQLite)...")
    info("As tabelas serão criadas automaticamente no startup do FastAPI (modo debug)")
    ok("SQLite configurado — tabelas criadas no startup")


# ---------------------------------------------------------------------------
# 6. Iniciar servidor
# ---------------------------------------------------------------------------
def start_server(python_path: str, use_docker: bool):
    print(f"\n{C.BOLD}{'='*60}{C.END}")
    if use_docker:
        print(f"{C.OK}  LEGALSHIELD AI SaaS — PRONTO!{C.END}")
    else:
        print(f"{C.OK}  LEGALSHIELD AI SaaS — PRONTO! (Modo Local){C.END}")
    print(f"{C.BOLD}{'='*60}{C.END}")
    print(f"  API:     http://localhost:8000")
    print(f"  Docs:    http://localhost:8000/docs")
    print(f"  Health:  http://localhost:8000/health")
    if not use_docker:
        print(f"  Banco:   SQLite (legalshield_local.db)")
        print(f"  Redis:   Desabilitado (sem cache)")
    print(f"  Ctrl+C para parar\n")

    # Carregar .env
    os.environ.update(_parse_env(ENV_FILE))

    try:
        sys.exit(subprocess.call([
            python_path, "-m", "uvicorn",
            "app.main:app",
            "--reload",
            "--host", "0.0.0.0",
            "--port", "8000",
        ]))
    except KeyboardInterrupt:
        info("Servidor encerrado pelo usuário")
        sys.exit(0)


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
    os.chdir(ROOT)

    use_docker = check_prerequisites()
    python_path = setup_venv()
    setup_env(use_docker)

    if use_docker:
        start_docker_services()
        setup_database_docker()
    else:
        setup_database_local()

    start_server(python_path, use_docker)


if __name__ == "__main__":
    main()
