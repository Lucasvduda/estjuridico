#!/bin/bash
# ============================================================
# LegalShield AI SaaS — Instalador Automático
# Execute no servidor:
#   bash install.sh
#   bash install.sh --domain api.empresa.com  (com HTTPS)
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

DOMAIN="$1"
APP_DIR="/opt/legalshield-saas"

echo ""
echo -e "${BOLD}============================================${NC}"
echo -e "${BOLD}  LegalShield AI SaaS — Instalador${NC}"
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
    apt install -y docker-compose-plugin 2>/dev/null || true
fi
ok "Docker Compose disponível"

# 3. Diretórios
mkdir -p $APP_DIR/{backups}
ok "Diretórios criados"

# 4. Verificar arquivos
if [ ! -f "$APP_DIR/docker-compose.yml" ]; then
    fail "docker-compose.yml não encontrado em $APP_DIR/. Extraia o pacote primeiro."
fi

# 5. .env
if [ ! -f "$APP_DIR/.env" ]; then
    info "Gerando .env com chaves seguras..."

    JWT_KEY=$(python3 -c "import secrets; print(secrets.token_hex(64))" 2>/dev/null || openssl rand -hex 64)
    ENC_KEY=$(python3 -c "import base64,os; print(base64.b64encode(os.urandom(32)).decode())" 2>/dev/null || openssl rand -base64 32)
    PG_PASS=$(python3 -c "import secrets; print(secrets.token_hex(16))" 2>/dev/null || openssl rand -hex 16)

    cat > $APP_DIR/.env << EOF
# === LegalShield AI SaaS — Produção ===
DEBUG=false

# Banco de Dados
DATABASE_URL=postgresql+asyncpg://legalshield:${PG_PASS}@db:5432/legalshield_saas
POSTGRES_PASSWORD=${PG_PASS}

# Redis
REDIS_URL=redis://redis:6379/0

# JWT (NUNCA compartilhe)
JWT_SECRET_KEY=${JWT_KEY}

# Criptografia (NUNCA compartilhe — se perder, dados ficam inacessíveis!)
ENCRYPTION_MASTER_KEY=${ENC_KEY}

# LLMs
OPENAI_API_KEY=
ANTHROPIC_API_KEY=

# CORS
CORS_ORIGINS=["*"]
EOF

    ok ".env gerado com chaves seguras"
    warn "EDITE o .env e coloque OPENAI_API_KEY e ANTHROPIC_API_KEY:"
    echo "  nano $APP_DIR/.env"
fi

# 6. Atualizar docker-compose com senha do PostgreSQL
PG_PASS=$(grep POSTGRES_PASSWORD $APP_DIR/.env | head -1 | cut -d= -f2)
if [ -n "$PG_PASS" ]; then
    sed -i "s/POSTGRES_PASSWORD: secretpass/POSTGRES_PASSWORD: ${PG_PASS}/" $APP_DIR/docker-compose.yml 2>/dev/null || true
    sed -i "s/secretpass@db/${PG_PASS}@db/" $APP_DIR/docker-compose.yml 2>/dev/null || true
fi

# 7. Firewall
if command -v ufw &> /dev/null; then
    ufw allow 22/tcp  2>/dev/null || true
    ufw allow 80/tcp  2>/dev/null || true
    ufw allow 443/tcp 2>/dev/null || true
    ok "Firewall configurado"
fi

# 8. Build e start
info "Construindo e iniciando containers..."
cd $APP_DIR
docker compose up -d --build

# 9. Aguardar PostgreSQL
info "Aguardando banco de dados..."
sleep 10

# 10. Executar migration
info "Criando tabelas..."
MIGRATION_FILE="$APP_DIR/migrations/001_initial_schema.py"
if [ -f "$MIGRATION_FILE" ]; then
    # Extrair SQL entre MIGRATION_UP = """ e """
    python3 -c "
content = open('$MIGRATION_FILE').read()
start = content.find('MIGRATION_UP = \"\"\"') + len('MIGRATION_UP = \"\"\"')
end = content.find('\"\"\"', start)
sql = content[start:end].strip()
print(sql)
" | docker compose exec -T db psql -U legalshield -d legalshield_saas 2>/dev/null
    ok "Tabelas e RLS criados"
fi

# 11. HTTPS
if [ -n "$DOMAIN" ]; then
    info "Configurando HTTPS para $DOMAIN..."
    apt install -y nginx certbot python3-certbot-nginx 2>/dev/null

    cat > /etc/nginx/sites-available/legalshield << EOF2
server {
    listen 80;
    server_name $DOMAIN;
    client_max_body_size 50M;

    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto \$scheme;
        proxy_read_timeout 300s;
    }
}
EOF2

    ln -sf /etc/nginx/sites-available/legalshield /etc/nginx/sites-enabled/
    nginx -t && systemctl restart nginx
    certbot --nginx -d $DOMAIN --non-interactive --agree-tos --email admin@$DOMAIN
    ok "HTTPS configurado para $DOMAIN"
fi

# 12. Backup cron
info "Configurando backup diário..."
cat > $APP_DIR/backup.sh << 'BKEOF'
#!/bin/bash
DATE=$(date +%Y-%m-%d_%H%M)
cd /opt/legalshield-saas
docker compose exec -T db pg_dump -U legalshield legalshield_saas | gzip > backups/db_$DATE.sql.gz
ls -t backups/db_*.sql.gz | tail -n +31 | xargs rm -f 2>/dev/null
BKEOF
chmod +x $APP_DIR/backup.sh
(crontab -l 2>/dev/null; echo "0 3 * * * $APP_DIR/backup.sh >> /var/log/legalshield-backup.log 2>&1") | sort -u | crontab -
ok "Backup diário agendado (3h da manhã)"

# 13. Verificar
sleep 3
if curl -s http://localhost:8000/health | grep -q "healthy"; then
    ok "Sistema funcionando!"
else
    warn "Aguarde mais 15s e teste: curl http://localhost:8000/health"
fi

# 14. Resumo
IP=$(hostname -I | awk '{print $1}')
echo ""
echo -e "${BOLD}============================================${NC}"
echo -e "${GREEN}  INSTALAÇÃO CONCLUÍDA!${NC}"
echo -e "${BOLD}============================================${NC}"
echo ""
echo "  API:     http://${IP}:8000"
if [ -n "$DOMAIN" ]; then
    echo "  HTTPS:   https://${DOMAIN}"
fi
echo "  Docs:    http://${IP}:8000/docs (desativado em produção)"
echo "  Health:  http://${IP}:8000/health"
echo ""
echo "  Próximos passos:"
echo "  1. nano $APP_DIR/.env  → Coloque OPENAI_API_KEY"
echo "  2. cd $APP_DIR && docker compose restart"
echo ""
echo "  Comandos úteis:"
echo "  docker compose -f $APP_DIR/docker-compose.yml logs -f"
echo "  docker compose -f $APP_DIR/docker-compose.yml restart"
echo "  $APP_DIR/backup.sh  (backup manual)"
echo ""
