# 📘 TUTORIAL COMPLETO — LegalShield AI SaaS

## Guia passo a passo: do desenvolvimento local até produção com clientes pagando

---

## 📋 ÍNDICE

1. [Testar Localmente (Sem Servidor)](#1-testar-localmente-sem-servidor)
2. [Obter as Chaves de API (LLMs)](#2-obter-as-chaves-de-api-llms)
3. [Preparar para Produção](#3-preparar-para-produção)
4. [Contratar Servidor (VPS)](#4-contratar-servidor-vps)
5. [Deploy no Servidor](#5-deploy-no-servidor)
6. [Domínio e SSL](#6-domínio-e-ssl)
7. [Monitoramento](#7-monitoramento)
8. [Sistema de Pagamentos](#8-sistema-de-pagamentos)
9. [Checklist Final de Produção](#9-checklist-final-de-produção)

---

## 1. TESTAR LOCALMENTE (Sem Servidor)

### 1.1 Pré-requisitos na sua máquina

```bash
# Instalar Python 3.12+
# Download: https://www.python.org/downloads/

# Instalar Docker Desktop (para PostgreSQL e Redis locais)
# Download: https://www.docker.com/products/docker-desktop/

# Instalar Tesseract OCR (para contratos escaneados)
# Windows: https://github.com/UB-Mannheim/tesseract/wiki
# Linux: sudo apt install tesseract-ocr tesseract-ocr-por
```

### 1.2 Subir banco e cache locais

Crie um arquivo `docker-compose.local.yml` para rodar SÓ o PostgreSQL e Redis:

```yaml
# docker-compose.local.yml
version: "3.9"
services:
  postgres:
    image: postgres:16-alpine
    environment:
      POSTGRES_DB: legalshield_saas
      POSTGRES_USER: legalshield
      POSTGRES_PASSWORD: dev_password_123
    ports:
      - "5432:5432"
    volumes:
      - pgdata:/var/lib/postgresql/data

  redis:
    image: redis:7-alpine
    ports:
      - "6379:6379"

volumes:
  pgdata:
```

```bash
# Subir PostgreSQL + Redis locais
docker-compose -f docker-compose.local.yml up -d

# Verificar se estão rodando
docker ps
# Deve mostrar: postgres:16-alpine e redis:7-alpine
```

### 1.3 Instalar dependências Python

```bash
cd projeto_a_saas

# Criar ambiente virtual
python -m venv venv

# Ativar (Windows)
venv\Scripts\activate

# Ativar (Linux/Mac)
source venv/bin/activate

# Instalar dependências
pip install -r requirements.txt
```

### 1.4 Configurar variáveis de ambiente

Crie um arquivo `.env` na pasta `projeto_a_saas/`:

```env
# === Banco de Dados ===
DATABASE_URL=postgresql+asyncpg://legalshield:dev_password_123@localhost:5432/legalshield_saas

# === Redis ===
REDIS_URL=redis://localhost:6379/0

# === JWT (gere uma chave aleatória) ===
# Execute: python -c "import secrets; print(secrets.token_hex(32))"
JWT_SECRET_KEY=cole_a_chave_gerada_aqui

# === Criptografia (gere uma chave AES) ===
# Execute: python -c "import base64,os; print(base64.b64encode(os.urandom(32)).decode())"
ENCRYPTION_MASTER_KEY=cole_a_chave_gerada_aqui

# === LLMs (pegue no Passo 2) ===
OPENAI_API_KEY=sk-...
ANTHROPIC_API_KEY=sk-ant-...

# === Modo Debug ===
DEBUG=true
```

### 1.5 Criar as tabelas do banco

```bash
# Opção A: Executar a migration manualmente via psql
docker exec -i $(docker ps -q -f name=postgres) psql -U legalshield -d legalshield_saas < migrations/001_initial_schema.py

# Opção B: Usar o Alembic (se estiver configurado)
alembic upgrade head

# Opção C: O app cria automaticamente em modo debug
# (já está configurado no main.py quando DEBUG=true)
```

### 1.6 Rodar o servidor local

```bash
# Rodar em modo desenvolvimento
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

# Acessar:
# API:  http://localhost:8000
# Docs: http://localhost:8000/docs (Swagger interativo)
# Health: http://localhost:8000/health
```

### 1.7 Testar os endpoints (via Swagger ou curl)

```bash
# 1. Registrar tenant + usuário
curl -X POST http://localhost:8000/api/v1/auth/register \
  -H "Content-Type: application/json" \
  -d '{
    "email": "admin@teste.com",
    "password": "SenhaForte123!",
    "full_name": "Admin Teste",
    "tenant_slug": "empresa-teste",
    "tenant_name": "Empresa Teste Ltda"
  }'
# Resposta: { "access_token": "eyJ...", "refresh_token": "..." }

# 2. Fazer upload de contrato (use o access_token)
curl -X POST http://localhost:8000/api/v1/contracts/upload \
  -H "Authorization: Bearer eyJ..." \
  -F "file=@contrato_exemplo.pdf"

# 3. Criar análise
curl -X POST http://localhost:8000/api/v1/analysis/ \
  -H "Authorization: Bearer eyJ..." \
  -H "Content-Type: application/json" \
  -d '{"contract_id": "ID_DO_CONTRATO", "mode": "defensive"}'

# 4. Exportar relatório PDF
curl -X POST http://localhost:8000/api/v1/reports/export \
  -H "Authorization: Bearer eyJ..." \
  -H "Content-Type: application/json" \
  -d '{"analysis_id": "ID_DA_ANALISE"}' \
  --output relatorio.pdf
```

### 1.8 Rodar os testes

```bash
# Da raiz do projeto (Juridico_IA/)
python -m pytest tests/test_saas.py tests/test_integration_saas.py -v
# Esperado: 19 passed ✅
```

---

## 2. OBTER AS CHAVES DE API (LLMs)

### 2.1 OpenAI (Primário) — https://platform.openai.com

1. Acesse **https://platform.openai.com/signup** e crie uma conta
2. Vá em **Settings → API Keys** (menu esquerdo)
3. Clique em **"Create new secret key"**
4. Dê um nome (ex: "LegalShield SaaS Produção")
5. Copie a chave: `sk-proj-...`
6. Vá em **Settings → Billing** e adicione crédito (mínimo $10)
7. Recomendação de modelo: `gpt-4o` (melhor custo-benefício para análise jurídica)

**Custo médio por análise:** ~$0.05-0.15 (dependendo do tamanho do contrato)

### 2.2 Anthropic (Fallback) — https://console.anthropic.com

1. Acesse **https://console.anthropic.com/** e crie uma conta
2. Vá em **Settings → API Keys**
3. Clique em **"Create Key"**
4. Copie a chave: `sk-ant-...`
5. Adicione créditos em **Plans & Billing**
6. Modelo recomendado: `claude-sonnet-4-20250514`

**Por que ter os dois?** Se a OpenAI cair (acontece ~2x por mês), o sistema muda automaticamente para Anthropic sem o cliente perceber.

---

## 3. PREPARAR PARA PRODUÇÃO

### 3.1 Gerar chaves seguras de produção

```bash
# JWT Secret (NUNCA use a mesma do desenvolvimento!)
python -c "import secrets; print('JWT_SECRET_KEY=' + secrets.token_hex(64))"

# Chave de criptografia AES-256
python -c "import base64, os; print('ENCRYPTION_MASTER_KEY=' + base64.b64encode(os.urandom(32)).decode())"
```

⚠️ **GUARDE ESSAS CHAVES EM UM LOCAL SEGURO!** Se perder a `ENCRYPTION_MASTER_KEY`, todos os contratos criptografados ficam inacessíveis.

### 3.2 Desativar modo debug

```env
DEBUG=false
# Isso desativa:
# - Swagger UI (/docs)
# - Auto-criação de tabelas
# - Logs verbosos
```

---

## 4. CONTRATAR SERVIDOR (VPS)

### Recomendações (custo/benefício):

| Provedor | Plano | Preço | RAM | vCPU | Link |
|----------|-------|-------|-----|------|------|
| **Hetzner** ⭐ | CPX21 | €5.50/mês (~R$30) | 4GB | 3 vCPU | https://www.hetzner.com/cloud |
| **DigitalOcean** | Basic | $12/mês (~R$60) | 2GB | 1 vCPU | https://www.digitalocean.com |
| **Contabo** | VPS S | €5.99/mês (~R$32) | 8GB | 4 vCPU | https://contabo.com/en/vps/ |
| **Vultr** | Cloud | $12/mês (~R$60) | 2GB | 1 vCPU | https://www.vultr.com |
| **AWS Lightsail** | Medium | $20/mês (~R$100) | 4GB | 2 vCPU | https://lightsail.aws.amazon.com |

**Recomendação para começar:** Hetzner CPX21 ou Contabo VPS S (melhor custo-benefício).

### Como contratar (exemplo Hetzner):

1. Acesse **https://www.hetzner.com/cloud**
2. Clique em **"Sign Up"** → crie conta com email
3. No painel, clique em **"Add Server"**
4. Escolha:
   - **Location:** Ashburn (USA) ou Falkenstein (Alemanha)
   - **Image:** Ubuntu 24.04
   - **Type:** Shared vCPU → CPX21 (4GB RAM, 3 vCPU)
   - **SSH Key:** Adicione sua chave SSH (ou use senha)
5. Clique em **"Create & Buy Now"**
6. Anote o **IP do servidor** (ex: `65.108.xxx.xxx`)

### Como criar chave SSH (se não tem):

```bash
# No seu computador:
ssh-keygen -t ed25519 -C "legalshield-server"
# Aperte Enter 3 vezes (aceitar padrões)

# Copiar a chave pública:
cat ~/.ssh/id_ed25519.pub
# Cole no Hetzner na hora de criar o servidor
```

---

## 5. DEPLOY NO SERVIDOR

### 5.1 Acessar o servidor

```bash
ssh root@65.108.xxx.xxx
```

### 5.2 Preparar o servidor

```bash
# Atualizar sistema
apt update && apt upgrade -y

# Instalar Docker
curl -fsSL https://get.docker.com | sh

# Instalar Docker Compose
apt install docker-compose-plugin -y

# Verificar instalação
docker --version
docker compose version

# Criar usuário para o app (não rodar como root)
adduser --disabled-password legalshield
usermod -aG docker legalshield
su - legalshield
```

### 5.3 Enviar o código para o servidor

```bash
# Do seu computador local:
# Opção A: Git (recomendado)
# No servidor:
git clone https://SEU_REPOSITORIO.git ~/legalshield-saas
cd ~/legalshield-saas/projeto_a_saas

# Opção B: SCP (upload direto)
scp -r ./projeto_a_saas root@65.108.xxx.xxx:/home/legalshield/
```

### 5.4 Configurar ambiente de produção

```bash
# No servidor, na pasta do projeto:
cd /home/legalshield/projeto_a_saas

# Criar .env de produção
nano .env
```

Cole as variáveis:

```env
# === Produção ===
DEBUG=false

# === Banco de Dados ===
DATABASE_URL=postgresql+asyncpg://legalshield:SENHA_FORTE_AQUI@postgres:5432/legalshield_saas
POSTGRES_PASSWORD=SENHA_FORTE_AQUI

# === Redis ===
REDIS_URL=redis://redis:6379/0

# === JWT ===
JWT_SECRET_KEY=sua_chave_jwt_de_producao_64_chars

# === Criptografia ===
ENCRYPTION_MASTER_KEY=sua_chave_aes_base64

# === LLMs ===
OPENAI_API_KEY=sk-proj-...
ANTHROPIC_API_KEY=sk-ant-...

# === CORS ===
CORS_ORIGINS=["https://seudominio.com.br"]
```

### 5.5 Subir o sistema

```bash
# Subir tudo em background
docker compose up -d --build

# Verificar se está rodando
docker compose ps
# Deve mostrar 3 containers: app, postgres, redis

# Ver logs
docker compose logs -f app

# Testar
curl http://localhost:8000/health
# {"status":"healthy","version":"1.0.0","service":"legalshield-saas"}
```

### 5.6 Criar as tabelas no banco de produção

```bash
# Conectar no PostgreSQL
docker compose exec postgres psql -U legalshield -d legalshield_saas

# Executar o SQL da migration (copie e cole o conteúdo de migrations/001_initial_schema.py)
# Ou faça via arquivo:
docker compose exec -T postgres psql -U legalshield -d legalshield_saas < migrations/001_initial_schema.sql
```

---

## 6. DOMÍNIO E SSL

### 6.1 Registrar domínio

| Registrador | Preço (.com.br) | Link |
|-------------|-----------------|------|
| **Registro.br** ⭐ | R$40/ano | https://registro.br |
| **Namecheap** | $8/ano (.com) | https://www.namecheap.com |
| **Cloudflare** | preço de custo | https://www.cloudflare.com/products/registrar/ |

**Como registrar no Registro.br:**
1. Acesse https://registro.br
2. Pesquise o domínio (ex: `legalshield.com.br`)
3. Registre com CPF/CNPJ
4. Pague via boleto ou cartão (R$40/ano)

### 6.2 Apontar DNS para o servidor

No painel do registrador:
1. Vá em **DNS** → **Gerenciar Registros**
2. Adicione um registro **A**:
   - **Nome:** `@` (ou `api`)
   - **Tipo:** A
   - **Valor:** `65.108.xxx.xxx` (IP do seu servidor)
   - **TTL:** 3600
3. Adicione outro para `www`:
   - **Nome:** `www`
   - **Tipo:** CNAME
   - **Valor:** `seudominio.com.br`

### 6.3 Configurar Nginx + SSL (HTTPS gratuito)

No servidor:

```bash
# Instalar Nginx e Certbot
apt install nginx certbot python3-certbot-nginx -y

# Criar config do Nginx
nano /etc/nginx/sites-available/legalshield
```

Cole:

```nginx
server {
    listen 80;
    server_name api.seudominio.com.br;

    # Limite de upload (contratos grandes)
    client_max_body_size 50M;

    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;

        # Timeouts para análises longas
        proxy_read_timeout 300s;
        proxy_connect_timeout 10s;
    }
}
```

```bash
# Ativar o site
ln -s /etc/nginx/sites-available/legalshield /etc/nginx/sites-enabled/
nginx -t   # Testar configuração
systemctl restart nginx

# Instalar certificado SSL GRATUITO (Let's Encrypt)
certbot --nginx -d api.seudominio.com.br

# Responda:
# - Email: seu@email.com
# - Agree: Y
# - Redirect HTTP→HTTPS: 2 (sim)

# Testar renovação automática
certbot renew --dry-run
```

Agora sua API está em: **https://api.seudominio.com.br** com HTTPS gratuito! 🔒

---

## 7. MONITORAMENTO

### 7.1 Uptime Robot (grátis) — https://uptimerobot.com

Monitora se a API está online e envia alerta se cair.

1. Crie conta em https://uptimerobot.com
2. Clique em **"Add New Monitor"**
3. Configure:
   - **Type:** HTTP(s)
   - **Friendly Name:** LegalShield SaaS
   - **URL:** `https://api.seudominio.com.br/health`
   - **Interval:** 5 minutes
4. Em **"Alert Contacts"** → adicione seu email/Telegram
5. Salve

### 7.2 Logs (básico)

```bash
# Ver logs em tempo real
docker compose logs -f app

# Ver últimas 100 linhas
docker compose logs --tail 100 app

# Salvar logs em arquivo
docker compose logs app > /var/log/legalshield.log
```

### 7.3 Backup do banco (IMPORTANTE!)

```bash
# Criar script de backup
nano /home/legalshield/backup.sh
```

```bash
#!/bin/bash
DATE=$(date +%Y-%m-%d_%H%M)
BACKUP_DIR=/home/legalshield/backups
mkdir -p $BACKUP_DIR

# Backup do PostgreSQL
docker compose -f /home/legalshield/projeto_a_saas/docker-compose.yml \
  exec -T postgres pg_dump -U legalshield legalshield_saas \
  | gzip > $BACKUP_DIR/db_$DATE.sql.gz

# Manter apenas últimos 30 backups
ls -t $BACKUP_DIR/db_*.sql.gz | tail -n +31 | xargs rm -f 2>/dev/null

echo "Backup feito: $BACKUP_DIR/db_$DATE.sql.gz"
```

```bash
chmod +x /home/legalshield/backup.sh

# Agendar backup diário às 3h da manhã
crontab -e
# Adicione esta linha:
0 3 * * * /home/legalshield/backup.sh >> /var/log/backup.log 2>&1
```

---

## 8. SISTEMA DE PAGAMENTOS

### 8.1 Stripe (Recomendado) — https://stripe.com

1. Crie conta em **https://dashboard.stripe.com/register**
2. Complete a verificação (documento + conta bancária)
3. Vá em **Developers → API Keys**
4. Copie:
   - `Publishable key`: `pk_live_...`
   - `Secret key`: `sk_live_...`
5. Vá em **Products** → **Create Product**:
   - **Plano Básico:** R$197/mês — 50 análises/mês
   - **Plano Pro:** R$497/mês — 200 análises/mês
   - **Plano Enterprise:** R$997/mês — ilimitado
6. Configure **Webhooks** em **Developers → Webhooks**:
   - URL: `https://api.seudominio.com.br/webhooks/stripe`
   - Eventos: `invoice.paid`, `invoice.payment_failed`, `customer.subscription.deleted`

### 8.2 Como integrar (lógica)

```
Cliente paga no Stripe → Webhook chega na sua API → Ativa/desativa tenant:

invoice.paid → subscription_status = "active"
invoice.payment_failed → subscription_status = "past_due"
customer.subscription.deleted → Kill-Switch ativado!
```

### 8.3 Alternativa: Asaas (Brasileiro) — https://www.asaas.com

Mais fácil para boleto/PIX no Brasil:
1. Crie conta em https://www.asaas.com
2. Configure cobrança recorrente
3. Use a API deles para automatizar ativação/desativação

---

## 9. CHECKLIST FINAL DE PRODUÇÃO

```
SEGURANÇA:
  [ ] DEBUG=false
  [ ] JWT_SECRET_KEY com 64+ caracteres aleatórios
  [ ] ENCRYPTION_MASTER_KEY gerada e salva em local seguro
  [ ] CORS_ORIGINS restrito ao seu domínio
  [ ] Swagger desativado (/docs não acessível)
  [ ] Rate limiting ativo (slowapi)
  [ ] Firewall configurado (UFW: permitir apenas 80, 443, 22)

INFRAESTRUTURA:
  [ ] HTTPS funcionando (Let's Encrypt)
  [ ] Nginx configurado como proxy reverso
  [ ] Docker containers rodando
  [ ] PostgreSQL com senha forte
  [ ] Redis sem acesso externo

DADOS:
  [ ] Backup diário automatizado
  [ ] Chaves salvas em local seguro (cofre/1Password)
  [ ] Tabelas criadas com RLS ativo
  [ ] Migration executada

MONITORAMENTO:
  [ ] Uptime Robot configurado
  [ ] Alertas de email/Telegram
  [ ] Logs acessíveis

NEGÓCIO:
  [ ] Planos de assinatura criados (Stripe/Asaas)
  [ ] Webhooks de pagamento configurados
  [ ] Termos de uso e política de privacidade
  [ ] Chaves de API (OpenAI + Anthropic) com crédito
```

---

## 🛑 COMANDOS ÚTEIS DO DIA-A-DIA

```bash
# Reiniciar o sistema
docker compose restart

# Atualizar para nova versão
git pull
docker compose up -d --build

# Ver uso de recursos
docker stats

# Conectar no banco
docker compose exec postgres psql -U legalshield -d legalshield_saas

# Bloquear tenant inadimplente (via API admin)
curl -X POST https://api.seudominio.com.br/api/admin/tenants/{ID}/block \
  -H "Authorization: Bearer TOKEN_SUPERADMIN" \
  -H "Content-Type: application/json" \
  -d '{"reason": "Inadimplência - fatura vencida há 15 dias"}'

# Desbloquear após pagamento
curl -X POST https://api.seudominio.com.br/api/admin/tenants/{ID}/unblock \
  -H "Authorization: Bearer TOKEN_SUPERADMIN"
```

---

## 📊 CONFIGURAR FIREWALL

```bash
# No servidor:
ufw allow 22    # SSH
ufw allow 80    # HTTP (redirecionado para HTTPS)
ufw allow 443   # HTTPS
ufw enable

# Verificar
ufw status
```

---

**Pronto!** Com este tutorial, você tem tudo para ir do desenvolvimento local até uma API SaaS em produção com clientes pagantes. 🚀
