#!/usr/bin/env python3
"""
LegalShield AI 2026 — Deploy Universal
Faz o deploy em qualquer servidor Linux com um único comando.

USO LOCAL (prepara o pacote):
  python deploy.py pack                    # Gera pacote .tar.gz pronto para enviar
  python deploy.py pack --project saas     # Empacota o SaaS
  python deploy.py pack --project enterprise  # Empacota o Enterprise

USO NO SERVIDOR (instala tudo):
  python deploy.py install                 # Detecta o projeto e instala
  python deploy.py install --port 8000     # Porta customizada
  python deploy.py install --domain api.empresa.com  # Configura HTTPS automaticamente

GERENCIAR:
  python deploy.py status                  # Mostra status dos containers
  python deploy.py logs                    # Mostra logs
  python deploy.py restart                 # Reinicia
  python deploy.py stop                    # Para tudo
  python deploy.py backup                  # Backup do banco
  python deploy.py update                  # Atualiza o código e reinicia
"""

import argparse
import os
import platform
import shutil
import subprocess
import sys
import tarfile
from datetime import datetime
from pathlib import Path

# ---------------------------------------------------------------------------
# Cores
# ---------------------------------------------------------------------------
class C:
    OK = "\033[92m"; WARN = "\033[93m"; FAIL = "\033[91m"
    BOLD = "\033[1m"; END = "\033[0m"; CYAN = "\033[96m"

def info(msg):  print(f"{C.CYAN}[INFO]{C.END} {msg}")
def ok(msg):    print(f"{C.OK}[  OK]{C.END} {msg}")
def warn(msg):  print(f"{C.WARN}[WARN]{C.END} {msg}")
def fail(msg):  print(f"{C.FAIL}[FAIL]{C.END} {msg}")

ROOT = Path(__file__).parent.resolve()


def detect_project():
    """Detecta qual projeto estamos (SaaS ou Enterprise)."""
    if (ROOT / "app" / "core" / "license_manager.py").exists():
        return "enterprise"
    if (ROOT / "app" / "core" / "middleware.py").exists():
        return "saas"
    # Se estiver na raiz com as duas pastas
    if (ROOT / "projeto_a_saas").exists():
        return "root"
    return "unknown"


def run(cmd, **kwargs):
    """Executa comando e retorna resultado."""
    return subprocess.run(cmd, shell=True, capture_output=True, text=True, **kwargs)


# ---------------------------------------------------------------------------
# PACK — Empacotar para envio
# ---------------------------------------------------------------------------
def cmd_pack(args):
    """Gera pacote .tar.gz pronto para enviar ao servidor."""
    project = args.project or detect_project()

    if project == "root":
        if not args.project:
            fail("Execute na pasta do projeto específico, ou use --project saas/enterprise")
            sys.exit(1)

    source = ROOT
    if project == "root":
        source = ROOT / f"projeto_{'a_saas' if args.project == 'saas' else 'b_enterprise'}"

    name = f"legalshield-{project}-{datetime.now().strftime('%Y%m%d_%H%M')}"
    output = ROOT / f"{name}.tar.gz"

    info(f"Empacotando projeto {project}...")

    exclude = {
        "__pycache__", ".git", "venv", ".env", "*.pyc",
        "keys", "node_modules", ".pytest_cache",
        "watermark_registry.db",
    }

    with tarfile.open(output, "w:gz") as tar:
        for item in source.rglob("*"):
            rel = item.relative_to(source)
            if any(exc in str(rel) for exc in exclude):
                continue
            if item.is_file():
                tar.add(item, arcname=f"{name}/{rel}")

    size_mb = output.stat().st_size / (1024 * 1024)
    ok(f"Pacote criado: {output.name} ({size_mb:.1f} MB)")
    print(f"\n  Para enviar ao servidor:")
    print(f"  scp {output.name} root@SEU_SERVIDOR:/opt/")
    print(f"\n  No servidor:")
    print(f"  cd /opt && tar xzf {output.name} && cd {name}")
    print(f"  python3 deploy.py install\n")


# ---------------------------------------------------------------------------
# INSTALL — Instalar no servidor
# ---------------------------------------------------------------------------
def cmd_install(args):
    """Instala o sistema no servidor (Docker + Nginx + SSL)."""
    project = detect_project()
    if project == "root":
        fail("Execute dentro da pasta do projeto específico")
        sys.exit(1)

    print(f"\n{C.BOLD}{'='*60}{C.END}")
    print(f"{C.BOLD}  INSTALAÇÃO — LegalShield AI {project.upper()}{C.END}")
    print(f"{C.BOLD}{'='*60}{C.END}\n")

    # 1. Verificar Docker
    info("Verificando Docker...")
    if not shutil.which("docker"):
        info("Instalando Docker...")
        os.system("curl -fsSL https://get.docker.com | sh")
        ok("Docker instalado")
    else:
        ok("Docker disponível")

    # 2. Verificar Docker Compose
    r = run("docker compose version")
    if r.returncode != 0:
        info("Instalando Docker Compose plugin...")
        os.system("apt install -y docker-compose-plugin 2>/dev/null || true")

    # 3. Criar .env se não existe
    env_file = ROOT / ".env"
    if not env_file.exists():
        info("Gerando .env...")
        _create_production_env(project, env_file, args.port)
        ok(".env criado")
        warn("EDITE O .env E COLOQUE SUAS CHAVES DE API!")
        print(f"\n  nano {env_file}\n")
    else:
        ok(".env já existe")

    # 4. Criar diretórios
    for d in ["data", "uploads", "reports", "backups"]:
        (ROOT / d).mkdir(exist_ok=True)

    # 5. Atualizar docker-compose para usar porta correta
    if args.port != 8000:
        _update_compose_port(project, args.port)

    # 6. Build e start
    info("Construindo e iniciando containers...")
    os.system(f"cd {ROOT} && docker compose up -d --build")
    ok("Containers iniciados")

    # 7. Configurar Nginx + SSL se domínio fornecido
    if args.domain:
        _setup_nginx_ssl(args.domain, args.port)

    # 8. Verificar
    import time
    time.sleep(3)
    r = run(f"curl -s http://localhost:{args.port}/health")
    if r.returncode == 0 and "healthy" in r.stdout:
        ok("Sistema funcionando!")
    else:
        warn("Sistema pode ainda estar iniciando... Aguarde 10s e teste:")
        print(f"  curl http://localhost:{args.port}/health")

    # 9. Resumo
    print(f"\n{C.BOLD}{'='*60}{C.END}")
    print(f"{C.OK}  INSTALAÇÃO CONCLUÍDA!{C.END}")
    print(f"{C.BOLD}{'='*60}{C.END}")
    print(f"  API:  http://{'localhost' if not args.domain else args.domain}:{args.port}")
    if args.domain:
        print(f"  HTTPS: https://{args.domain}")
    print(f"\n  Comandos úteis:")
    print(f"  python3 deploy.py status   — Ver status")
    print(f"  python3 deploy.py logs     — Ver logs")
    print(f"  python3 deploy.py backup   — Backup do banco")
    print(f"  python3 deploy.py restart  — Reiniciar\n")


def _create_production_env(project, env_file, port):
    """Cria .env para produção."""
    import secrets, base64

    if project == "saas":
        pg_pass = secrets.token_hex(16)
        content = f"""# === LegalShield SaaS — Produção ===
DEBUG=false
DATABASE_URL=postgresql+asyncpg://legalshield:{pg_pass}@db:5432/legalshield_saas
POSTGRES_PASSWORD={pg_pass}
REDIS_URL=redis://redis:6379/0
JWT_SECRET_KEY={secrets.token_hex(64)}
ENCRYPTION_MASTER_KEY={base64.b64encode(os.urandom(32)).decode()}
OPENAI_API_KEY=
ANTHROPIC_API_KEY=
CORS_ORIGINS=["*"]
"""
    else:
        content = f"""# === LegalShield Enterprise — Produção ===
DEBUG=false
OPENAI_API_KEY=
ANTHROPIC_API_KEY=
DATABASE_PATH=./data/legalshield.db
UPLOAD_DIR=./uploads
REPORTS_DIR=./reports
"""

    env_file.write_text(content, encoding="utf-8")


def _update_compose_port(project, port):
    """Atualiza porta no docker-compose."""
    compose = ROOT / "docker-compose.yml"
    if compose.exists():
        content = compose.read_text(encoding="utf-8")
        content = content.replace('"8000:8000"', f'"{port}:{port}"')
        compose.write_text(content, encoding="utf-8")


def _setup_nginx_ssl(domain, port):
    """Configura Nginx + Let's Encrypt automaticamente."""
    info(f"Configurando HTTPS para {domain}...")

    # Instalar Nginx e Certbot
    os.system("apt install -y nginx certbot python3-certbot-nginx 2>/dev/null")

    nginx_conf = f"""server {{
    listen 80;
    server_name {domain};
    client_max_body_size 50M;

    location / {{
        proxy_pass http://127.0.0.1:{port};
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_read_timeout 300s;
    }}
}}
"""

    conf_path = Path(f"/etc/nginx/sites-available/legalshield")
    conf_path.write_text(nginx_conf, encoding="utf-8")

    link_path = Path(f"/etc/nginx/sites-enabled/legalshield")
    if not link_path.exists():
        os.symlink(conf_path, link_path)

    os.system("nginx -t && systemctl restart nginx")
    os.system(f"certbot --nginx -d {domain} --non-interactive --agree-tos --email admin@{domain}")
    ok(f"HTTPS configurado para {domain}")


# ---------------------------------------------------------------------------
# Comandos de gerenciamento
# ---------------------------------------------------------------------------
def cmd_status(args):
    os.system(f"cd {ROOT} && docker compose ps")

def cmd_logs(args):
    os.system(f"cd {ROOT} && docker compose logs -f --tail 100")

def cmd_restart(args):
    os.system(f"cd {ROOT} && docker compose restart")
    ok("Reiniciado")

def cmd_stop(args):
    os.system(f"cd {ROOT} && docker compose down")
    ok("Parado")

def cmd_backup(args):
    project = detect_project()
    backup_dir = ROOT / "backups"
    backup_dir.mkdir(exist_ok=True)
    ts = datetime.now().strftime("%Y-%m-%d_%H%M")

    if project == "saas":
        backup_file = backup_dir / f"db_{ts}.sql.gz"
        os.system(
            f"cd {ROOT} && docker compose exec -T db "
            f"pg_dump -U legalshield legalshield_saas "
            f"| gzip > {backup_file}"
        )
        ok(f"Backup PostgreSQL: {backup_file}")
    else:
        import shutil as sh
        db_src = ROOT / "data" / "legalshield.db"
        if db_src.exists():
            backup_file = backup_dir / f"db_{ts}.sqlite3"
            sh.copy2(db_src, backup_file)
            ok(f"Backup SQLite: {backup_file}")
        else:
            warn("Banco não encontrado")

def cmd_update(args):
    info("Atualizando...")
    os.system(f"cd {ROOT} && git pull 2>/dev/null || true")
    os.system(f"cd {ROOT} && docker compose up -d --build")
    ok("Atualizado e reiniciado")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def main():
    parser = argparse.ArgumentParser(
        description="LegalShield AI — Deploy Universal",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Exemplos:
  python deploy.py pack                    Empacota para envio
  python deploy.py install                 Instala no servidor
  python deploy.py install --domain api.empresa.com  Com HTTPS
  python deploy.py status                  Ver containers
  python deploy.py backup                  Backup do banco
        """,
    )

    sub = parser.add_subparsers(dest="command", help="Comando")

    # pack
    p_pack = sub.add_parser("pack", help="Empacotar para envio")
    p_pack.add_argument("--project", choices=["saas", "enterprise"])

    # install
    p_install = sub.add_parser("install", help="Instalar no servidor")
    p_install.add_argument("--port", type=int, default=8000)
    p_install.add_argument("--domain", type=str, default=None, help="Domínio para HTTPS")

    # management
    sub.add_parser("status", help="Status dos containers")
    sub.add_parser("logs", help="Ver logs")
    sub.add_parser("restart", help="Reiniciar")
    sub.add_parser("stop", help="Parar tudo")
    sub.add_parser("backup", help="Backup do banco")
    sub.add_parser("update", help="Atualizar e reiniciar")

    args = parser.parse_args()

    commands = {
        "pack": cmd_pack,
        "install": cmd_install,
        "status": cmd_status,
        "logs": cmd_logs,
        "restart": cmd_restart,
        "stop": cmd_stop,
        "backup": cmd_backup,
        "update": cmd_update,
    }

    if args.command in commands:
        commands[args.command](args)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
