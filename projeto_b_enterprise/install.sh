#!/bin/bash
# ============================================================
# LegalShield AI Enterprise — Instalador Automático
# Execute no servidor do cliente:
#   curl -sSL URL_DO_SEU_ARQUIVO/install.sh | bash
#   OU
#   bash install.sh
# ============================================================

set -e

GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'
BOLD='\033[1m'

ok()   { echo -e "${GREEN}[  OK]${NC} $1"; }
info() { echo -e "${BOLD}[INFO]${NC} $1"; }
warn() { echo -e "${YELLOW}[WARN]${NC} $1"; }
fail() { echo -e "${RED}[FAIL]${NC} $1"; exit 1; }

APP_DIR="/opt/legalshield"

echo ""
echo -e "${BOLD}============================================${NC}"
echo -e "${BOLD}  LegalShield AI — Instalador Automático${NC}"
echo -e "${BOLD}============================================${NC}"
echo ""

# 1. Docker
if ! command -v docker &> /dev/null; then
    info "Instalando Docker..."
    curl -fsSL https://get.docker.com | sh
    systemctl enable docker
    systemctl start docker
    ok "Docker instalado"
else
    ok "Docker já instalado"
fi

# 2. Docker Compose
if ! docker compose version &> /dev/null; then
    info "Instalando Docker Compose..."
    apt install -y docker-compose-plugin 2>/dev/null || true
fi
ok "Docker Compose disponível"

# 3. Diretórios
mkdir -p $APP_DIR/{data,uploads,reports,backups}
ok "Diretórios criados em $APP_DIR"

# 4. Verificar se os arquivos estão no lugar
if [ ! -f "$APP_DIR/docker-compose.yml" ]; then
    fail "Arquivos do sistema não encontrados em $APP_DIR/. Extraia o pacote primeiro."
fi

if [ ! -f "$APP_DIR/license.key" ]; then
    fail "license.key não encontrada em $APP_DIR/. Coloque a licença antes de instalar."
fi

# 5. .env
if [ ! -f "$APP_DIR/.env" ]; then
    info "Criando .env..."
    cat > $APP_DIR/.env << 'EOF'
# === LegalShield AI Enterprise ===
# Coloque suas chaves de API abaixo:
OPENAI_API_KEY=
ANTHROPIC_API_KEY=

DEBUG=false
DATABASE_PATH=./data/legalshield.db
UPLOAD_DIR=./uploads
REPORTS_DIR=./reports
EOF
    ok ".env criado"
    warn "EDITE o .env e coloque sua OPENAI_API_KEY:"
    echo "  nano $APP_DIR/.env"
fi

# 6. Firewall
if command -v ufw &> /dev/null; then
    ufw allow 22/tcp   2>/dev/null || true
    ufw allow 80/tcp   2>/dev/null || true
    ufw allow 443/tcp  2>/dev/null || true
    ok "Firewall configurado (22, 80, 443)"
fi

# 7. Build e start
info "Construindo e iniciando o sistema..."
cd $APP_DIR
docker compose up -d --build

# 8. Aguardar
sleep 5

# 9. Verificar
if curl -s http://localhost:8000/health | grep -q "healthy"; then
    ok "Sistema funcionando!"
else
    warn "Sistema iniciando... Aguarde 15s e teste:"
    echo "  curl http://localhost:8000/health"
fi

# 10. Resumo
echo ""
echo -e "${BOLD}============================================${NC}"
echo -e "${GREEN}  INSTALAÇÃO CONCLUÍDA!${NC}"
echo -e "${BOLD}============================================${NC}"
echo ""
echo "  API:     http://$(hostname -I | awk '{print $1}'):8000"
echo "  Health:  http://$(hostname -I | awk '{print $1}'):8000/health"
echo "  License: http://$(hostname -I | awk '{print $1}'):8000/license"
echo ""
echo "  Próximos passos:"
echo "  1. Edite o .env com sua OPENAI_API_KEY: nano $APP_DIR/.env"
echo "  2. Reinicie: cd $APP_DIR && docker compose restart"
echo "  3. Para HTTPS: python3 deploy.py install --domain seu.dominio.com"
echo ""
