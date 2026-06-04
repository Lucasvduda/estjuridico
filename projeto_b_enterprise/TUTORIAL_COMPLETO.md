# 📘 TUTORIAL COMPLETO — LegalShield AI Enterprise

## Guia passo a passo: como vender, instalar, proteger e testar localmente

---

## 📋 ÍNDICE

1. [Testar Localmente (Sem Servidor)](#1-testar-localmente-sem-servidor)
2. [Obter as Chaves de API (LLMs)](#2-obter-as-chaves-de-api-llms)
3. [Preparar Ambiente de Venda](#3-preparar-ambiente-de-venda)
4. [Processo de Venda (Passo a Passo)](#4-processo-de-venda-passo-a-passo)
5. [Instalar no Servidor do Cliente](#5-instalar-no-servidor-do-cliente)
6. [Como Testar se a Proteção Funciona](#6-como-testar-se-a-proteção-funciona)
7. [Em Caso de Pirataria](#7-em-caso-de-pirataria)
8. [Manutenção e Atualizações](#8-manutenção-e-atualizações)
9. [Checklist de Venda](#9-checklist-de-venda)

---

## 1. TESTAR LOCALMENTE (Sem Servidor)

### 1.1 Pré-requisitos na sua máquina

```bash
# Instalar Python 3.12+
# Download: https://www.python.org/downloads/

# Instalar Docker Desktop
# Download: https://www.docker.com/products/docker-desktop/

# Instalar Tesseract OCR (para contratos escaneados)
# Windows: https://github.com/UB-Mannheim/tesseract/wiki
# Linux: sudo apt install tesseract-ocr tesseract-ocr-por
```

### 1.2 Instalar dependências Python

```bash
cd projeto_b_enterprise

# Criar ambiente virtual
python -m venv venv

# Ativar (Windows)
venv\Scripts\activate

# Ativar (Linux/Mac)
source venv/bin/activate

# Instalar dependências
pip install -r requirements.txt
```

### 1.3 Gerar chaves RSA para teste local

```bash
# Gerar par de chaves RSA-4096 (execute uma vez)
python tools/generate_license.py init-keys

# Resultado:
# ✓ Chave privada: ./keys/private_key.pem
# ✓ Chave pública: ./keys/public_key.pem
```

### 1.4 Gerar licença de teste (para sua máquina)

```bash
# Ver o Hardware ID da sua máquina
python tools/generate_license.py hwid
# Resultado: Hardware ID desta máquina: a1b2c3d4e5f6...

# Gerar licença de teste para você
python tools/generate_license.py generate \
  --customer "Teste Local" \
  --days 365

# Resultado:
# ✓ Licença salva: license_TESTE_LOCAL.key
```

### 1.5 Colocar arquivos no lugar certo

```bash
# Copiar licença e chave pública para a raiz do projeto
cp license_TESTE_LOCAL.key ./license.key
cp keys/public_key.pem ./public_key.pem
```

### 1.6 Configurar variáveis de ambiente

Crie um arquivo `.env` na pasta `projeto_b_enterprise/`:

```env
# === LLMs (suas chaves de teste) ===
OPENAI_API_KEY=sk-...
ANTHROPIC_API_KEY=sk-ant-...

# === Configurações ===
DEBUG=true
DATABASE_PATH=./data/legalshield.db
UPLOAD_DIR=./uploads
```

### 1.7 Rodar o sistema

```bash
# Rodar em modo desenvolvimento
uvicorn app.main:app --reload --host 0.0.0.0 --port 8001

# Se a licença estiver válida, você verá:
# ✓ Licença válida — Teste Local
# ✓ 365 dias restantes

# Acessar:
# API:  http://localhost:8001
# Docs: http://localhost:8001/docs
# Health: http://localhost:8001/health
```

### 1.8 Testar os endpoints

```bash
# 1. Upload de contrato
curl -X POST http://localhost:8001/api/contracts/upload \
  -F "file=@contrato_exemplo.pdf"
# Resposta: {"id": "abc-123", "filename": "contrato_exemplo.pdf", ...}

# 2. Criar análise
curl -X POST http://localhost:8001/api/analysis \
  -H "Content-Type: application/json" \
  -d '{"contract_id": "abc-123", "mode": "defensive"}'

# 3. Exportar relatório PDF
curl -X POST http://localhost:8001/api/reports/export/ID_DA_ANALISE \
  --output relatorio.pdf

# 4. Ver/Configurar chaves de API
curl http://localhost:8001/api/settings/byok

# 5. Atualizar chave de API
curl -X PUT http://localhost:8001/api/settings/byok \
  -H "Content-Type: application/json" \
  -d '{"openai_api_key": "sk-nova-chave..."}'
```

### 1.9 Rodar os testes automatizados

```bash
# Da raiz do projeto (Juridico_IA/)
python -m pytest tests/test_enterprise.py tests/test_integration.py -v
# Esperado: 13 passed ✅
```

---

## 2. OBTER AS CHAVES DE API (LLMs)

> **NOTA:** No Enterprise, o CLIENTE compra as próprias chaves (modelo BYOK). Você não gasta nada com API de IA!

### Instrua o cliente a fazer:

### 2.1 OpenAI — https://platform.openai.com

1. Acesse **https://platform.openai.com/signup**
2. Crie conta com email da empresa
3. Vá em **Settings → API Keys** → **"Create new secret key"**
4. Copie a chave: `sk-proj-...`
5. Vá em **Settings → Billing** → adicione crédito (mínimo $10)
6. Configure no sistema em **Configurações → API Keys**

### 2.2 Anthropic — https://console.anthropic.com

1. Acesse **https://console.anthropic.com/**
2. Crie conta → vá em **Settings → API Keys** → **"Create Key"**
3. Copie: `sk-ant-...`
4. Adicione créditos em **Plans & Billing**

**Dica para o cliente:** "A OpenAI é obrigatória. Anthropic é opcional, mas recomendamos para ter redundância automática."

---

## 3. PREPARAR AMBIENTE DE VENDA

### 3.1 Gerar chaves RSA (apenas UMA VEZ, na primeira venda)

```bash
cd projeto_b_enterprise

# Gerar par de chaves RSA-4096
python tools/generate_license.py init-keys --output-dir ./keys_master

# Resultado:
# ✓ Chave privada: ./keys_master/private_key.pem ← NUNCA COMPARTILHE!
# ✓ Chave pública: ./keys_master/public_key.pem  ← Vai para o cliente

# ⚠️ FAÇA BACKUP DA CHAVE PRIVADA EM:
# 1. HD externo
# 2. Cofre digital (1Password, Bitwarden)
# 3. Impresso em papel em cofre físico (paranoia nível alto)
```

### 3.2 Serviços de backup recomendados para suas chaves

| Serviço | Preço | Link |
|---------|-------|------|
| **Bitwarden** ⭐ | Grátis | https://bitwarden.com |
| **1Password** | $3/mês | https://1password.com |
| **Google Drive** (criptografado) | Grátis | Coloque num ZIP com senha AES-256 |

### 3.3 Organizar pasta de vendas

Crie esta estrutura no seu computador (NÃO no repositório):

```
📁 LegalShield_Vendas/         ← Pasta segura, com backup
├── 📁 keys_master/
│   ├── private_key.pem        ← SUA chave, NUNCA sai daqui
│   └── public_key.pem         ← Cópia vai para cada cliente
├── 📁 registro/
│   └── watermark_registry.db  ← Banco de registro de vendas
├── 📁 builds/
│   ├── 📁 empresa_abc/        ← Build customizado por cliente
│   ├── 📁 empresa_xyz/
│   └── ...
└── 📁 contratos_venda/        ← PDFs dos contratos de venda
```

---

## 4. PROCESSO DE VENDA (Passo a Passo)

### 4.1 Fluxograma da venda

```
1. Cliente fecha contrato
   ↓
2. Você pede o Hardware ID do servidor do cliente
   ↓
3. Você gera a licença vinculada ao hardware
   ↓
4. Você gera o build com marca d'água única
   ↓
5. Você entrega: Docker image + license.key + public_key.pem
   ↓
6. Cliente sobe o Docker no servidor dele
```

### 4.2 Passo 1: Pegar o Hardware ID do cliente

Envie este script para o cliente executar no servidor DELE:

```bash
# O cliente deve rodar isso no servidor onde vai instalar:
python3 -c "
import hashlib, subprocess, platform, uuid
data = ''
data += platform.processor()
data += str(uuid.getnode())
try:
    r = subprocess.run(['wmic', 'diskdrive', 'get', 'serialnumber'], capture_output=True, text=True)
    data += r.stdout.strip()
except: pass
try:
    r = subprocess.run(['wmic', 'baseboard', 'get', 'serialnumber'], capture_output=True, text=True)
    data += r.stdout.strip()
except: pass
print('Hardware ID:', hashlib.sha256(data.encode()).hexdigest())
"
```

O cliente te envia o resultado: `Hardware ID: a1b2c3d4...` (64 caracteres hex)

### 4.3 Passo 2: Gerar licença vinculada ao hardware

```bash
cd projeto_b_enterprise

python tools/generate_license.py generate \
  --customer "Escritório Jurídico ABC" \
  --hardware-id "a1b2c3d4e5f6..." \
  --days 365 \
  --private-key ../LegalShield_Vendas/keys_master/private_key.pem \
  --output ../LegalShield_Vendas/builds/escritorio_abc/license.key

# Resultado:
# Cliente:      Escritório Jurídico ABC
# Hardware ID:  a1b2c3d4e5f6...
# Expira em:    04/05/2027
# ✓ Licença salva: .../builds/escritorio_abc/license.key
```

### 4.4 Passo 3: Gerar marca d'água (fingerprint digital)

```bash
python tools/generate_watermark.py \
  --customer "Escritório Jurídico ABC" \
  --contract "CONTRATO_2026_042" \
  --build-path ../LegalShield_Vendas/builds/escritorio_abc \
  --registry ../LegalShield_Vendas/registro/watermark_registry.db

# Resultado:
# Cliente:        Escritório Jurídico ABC
# Fingerprint ID: ESCRITORIO_JURIDICO_ABC_2026_42
#
# [✓] Injetado em: BD SQLite (_sys_calibration)
# [✓] Injetado em: Config YAML (zero-width chars)
# [✓] Injetado em: Comentários SQL (migrations)
# [✓] Injetado em: Metadados EXIF de assets
# [✓] Injetado em: Constantes Python (.pyc)
#
# Resultado: 5/5 locais injetados com sucesso
# ✓ Registro salvo em: watermark_registry.db
```

### 4.5 Passo 4: Montar o pacote de entrega

```bash
# Copiar o código-fonte para o build do cliente
DEST=../LegalShield_Vendas/builds/escritorio_abc

# Copiar app
cp -r app/ $DEST/app/
cp Dockerfile $DEST/
cp docker-compose.yml $DEST/
cp requirements.txt $DEST/

# Copiar chave pública (NÃO a privada!)
cp ../LegalShield_Vendas/keys_master/public_key.pem $DEST/

# O build do cliente agora contém:
# builds/escritorio_abc/
# ├── app/                    (código com marca d'água já injetada)
# ├── Dockerfile
# ├── docker-compose.yml
# ├── requirements.txt
# ├── license.key             (vinculada ao hardware do cliente)
# ├── public_key.pem          (para validação da licença)
# ├── data/legalshield.db     (com fingerprint no SQLite)
# ├── config/settings.yml     (com fingerprint ZWC)
# ├── migrations/init.sql     (com fingerprint nos comentários)
# ├── static/icon.png         (com fingerprint nos metadados)
# └── app/core/_calibration_constants.py (com fingerprint)
```

### 4.6 Passo 5: Entregar ao cliente

**Opção A: Via repositório privado (recomendado)**
```bash
# Criar repositório privado no GitHub/GitLab para cada cliente
# Upload do build customizado
cd $DEST
git init
git add .
git commit -m "LegalShield Enterprise v1.0 - Escritório ABC"
git remote add origin https://github.com/suaempresa/legalshield-escritorio-abc.git
git push -u origin main
# Dar acesso ao cliente
```

**Opção B: Via arquivo compactado**
```bash
cd ../LegalShield_Vendas/builds/
tar czf escritorio_abc_v1.0.tar.gz escritorio_abc/
# Envie via link seguro (Google Drive com acesso restrito, WeTransfer, etc.)
```

**Opção C: Via Docker Hub privado**
```bash
cd $DEST
docker build -t seuregistro/legalshield-abc:v1.0 .
docker push seuregistro/legalshield-abc:v1.0
# Cliente faz: docker pull seuregistro/legalshield-abc:v1.0
```

---

## 5. INSTALAR NO SERVIDOR DO CLIENTE

### 5.1 Requisitos do servidor do cliente

| Item | Mínimo | Recomendado |
|------|--------|-------------|
| **CPU** | 2 vCPU | 4 vCPU |
| **RAM** | 2GB | 4GB |
| **Disco** | 20GB SSD | 50GB SSD |
| **SO** | Ubuntu 22.04+ | Ubuntu 24.04 |
| **Docker** | 24+ | Última versão |
| **Internet** | Necessária (para API do LLM) | Banda larga |

### 5.2 Servidores recomendados para o CLIENTE

| Provedor | Plano | Preço | Link |
|----------|-------|-------|------|
| **Hetzner** ⭐ | CPX21 | €5.50/mês | https://www.hetzner.com/cloud |
| **DigitalOcean** | Basic | $12/mês | https://www.digitalocean.com |
| **Contabo** | VPS S | €5.99/mês | https://contabo.com |
| **AWS Lightsail** | Medium | $20/mês | https://lightsail.aws.amazon.com |
| **Servidor on-premises** | — | — | O próprio servidor da empresa |

### 5.3 Instalação (envie isso como manual para o cliente)

```markdown
# GUIA DE INSTALAÇÃO — LegalShield AI Enterprise

## 1. Instalar Docker
ssh root@SEU_SERVIDOR
curl -fsSL https://get.docker.com | sh
docker --version

## 2. Enviar os arquivos para o servidor
# (faça do seu computador)
scp -r ./legalshield_enterprise root@SEU_SERVIDOR:/opt/legalshield/

## 3. Configurar
cd /opt/legalshield
nano .env
```

```env
# === API Keys (compre as suas) ===
# OpenAI: https://platform.openai.com → API Keys
OPENAI_API_KEY=sk-...

# Anthropic (opcional): https://console.anthropic.com
ANTHROPIC_API_KEY=sk-ant-...
```

```markdown
## 4. Subir o sistema
docker compose up -d --build

## 5. Verificar
curl http://localhost:8001/health
# Deve retornar: {"status":"healthy","service":"legalshield-enterprise"}

curl http://localhost:8001/license
# Deve retornar: {"is_valid":true,"customer_name":"Escritório ABC",...}

## 6. Acessar
# API: http://SEU_IP:8001
# Para HTTPS, configure Nginx + Let's Encrypt (mesma instrução do SaaS)
```

### 5.4 Configurar HTTPS para o cliente (se precisar)

```bash
# No servidor do cliente:
apt install nginx certbot python3-certbot-nginx -y

# Criar config Nginx (mesma lógica do SaaS, porta 8001)
nano /etc/nginx/sites-available/legalshield
```

```nginx
server {
    listen 80;
    server_name legal.empresa-do-cliente.com.br;
    client_max_body_size 50M;

    location / {
        proxy_pass http://127.0.0.1:8001;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_read_timeout 300s;
    }
}
```

```bash
ln -s /etc/nginx/sites-available/legalshield /etc/nginx/sites-enabled/
certbot --nginx -d legal.empresa-do-cliente.com.br
```

---

## 6. COMO TESTAR SE A PROTEÇÃO FUNCIONA

### 6.1 Testar a licença

```bash
# Cenário 1: Licença válida — sistema funciona
# Resultado esperado: sistema inicia normalmente

# Cenário 2: Licença removida
mv license.key license.key.bkp
uvicorn app.main:app --port 8001
# Resultado esperado:
# ✗ LICENÇA NÃO ENCONTRADA
# (sistema NÃO inicia)

# Cenário 3: Licença adulterada
echo "chave_falsa" > license.key
uvicorn app.main:app --port 8001
# Resultado esperado:
# ✗ LICENÇA INVÁLIDA
# (sistema NÃO inicia)

# Cenário 4: Hardware diferente
# Se copiar a licença para OUTRA máquina:
# Resultado esperado:
# ✗ LICENÇA INVÁLIDA
# Motivo: Hardware ID não corresponde
```

### 6.2 Testar a marca d'água

```bash
# 1. Gerar uma marca d'água de teste
python tools/generate_watermark.py \
  --customer "Teste Interno" \
  --contract "CT-TESTE" \
  --build-path ./test_watermark

# 2. Tentar extrair (simular detecção de pirataria)
python tools/extract_watermark.py \
  --source ./test_watermark

# Resultado esperado:
# [1/5] BD SQLite: ✓ ENCONTRADO → TESTE_INTERNO_2026_XX
# [2/5] Config YAML: ✓ ENCONTRADO → TESTE_INTERNO_2026_XX
# [3/5] SQL Comments: ✓ ENCONTRADO → TESTE_INTERNO_2026_XX
# [4/5] EXIF Metadata: ✓ ENCONTRADO → TESTE_INTERNO_2026_XX
# [5/5] Python Constants: ✓ ENCONTRADO → TESTE_INTERNO_2026_XX
#
# RESULTADO: 5/5 marcas confirmam → Comprador Original: Teste Interno

# 3. Testar resiliência (remover 2 locais)
rm test_watermark/data/legalshield.db
rm test_watermark/config/settings.yml
python tools/extract_watermark.py --source ./test_watermark
# Resultado: 3/5 → Comprador identificado! ✅

# 4. Limpar
rm -rf test_watermark
```

### 6.3 Testar os testes automatizados

```bash
# Da raiz do projeto
python -m pytest tests/test_enterprise.py tests/test_integration.py -v
# Esperado: 13 passed ✅
```

---

## 7. EM CASO DE PIRATARIA

### 7.1 Você encontrou seu software sendo usado sem licença

```bash
# 1. Obtenha acesso a uma cópia do software vazado
# (pode ser screenshot, VM, HD copiado, etc.)

# 2. Execute o extrator forense
python tools/extract_watermark.py \
  --source /caminho/para/software/vazado \
  --registry ../LegalShield_Vendas/registro/watermark_registry.db

# Resultado:
# RESULTADO: 5/5 marcas confirmam → Comprador Original: Escritório ABC
# Contrato: CONTRATO_2026_042
# Data da venda: 2026-05-04
#
# → Relatório forense salvo em: forensic_report_2026-05-04_153022.txt
```

### 7.2 O que fazer com o relatório

1. **Notifique o cliente** que a cópia foi identificada
2. **Envie o relatório forense** ao seu advogado
3. O relatório pode ser usado como **prova técnica** em:
   - Ação civil por quebra de contrato
   - Ação criminal por violação de direitos autorais (Lei 9.609/98)
   - Medida cautelar de busca e apreensão

### 7.3 Revogação da licença (remoto)

O Enterprise é 100% offline (sem phone-home), mas:
- **Se houver atualização futura:** gere nova licença com expiração curta
- **No contrato de venda:** inclua cláusula de revogação por violação

---

## 8. MANUTENÇÃO E ATUALIZAÇÕES

### 8.1 Enviar atualização para o cliente

```bash
# 1. Faça as alterações no código
# 2. Regere o build COM A MESMA MARCA D'ÁGUA

python tools/generate_watermark.py \
  --customer "Escritório Jurídico ABC" \
  --contract "CONTRATO_2026_042" \
  --build-path ../LegalShield_Vendas/builds/escritorio_abc_v1.1

# 3. Copie o app atualizado
cp -r app/ ../LegalShield_Vendas/builds/escritorio_abc_v1.1/app/
cp Dockerfile ../LegalShield_Vendas/builds/escritorio_abc_v1.1/
# ...

# 4. Entregue ao cliente a nova versão
# A licença existente continua válida (mesmo hardware + não expirou)
```

### 8.2 Renovar licença

```bash
# Quando a licença do cliente estiver perto de expirar:
python tools/generate_license.py generate \
  --customer "Escritório Jurídico ABC" \
  --hardware-id "a1b2c3d4..." \
  --days 365 \
  --private-key ../LegalShield_Vendas/keys_master/private_key.pem \
  --output nova_license.key

# Envie o novo license.key ao cliente
# Ele substitui o antigo e reinicia o Docker
```

### 8.3 Cliente trocou de servidor

```bash
# 1. Peça o NOVO Hardware ID
# 2. Gere NOVA licença com o novo hardware
# 3. A antiga licença para de funcionar no servidor novo automaticamente
```

---

## 9. CHECKLIST DE VENDA

### Para cada cliente, você deve:

```
ANTES DA VENDA:
  [ ] Contrato de venda assinado (com cláusula anti-pirataria)
  [ ] Valor e forma de pagamento definidos
  [ ] Hardware ID do servidor do cliente obtido

PREPARAÇÃO:
  [ ] Chaves RSA master existem (geradas uma vez)
  [ ] Licença gerada (vinculada ao hardware)
  [ ] Marca d'água injetada (5/5 locais)
  [ ] Registro salvo no watermark_registry.db
  [ ] Build testado localmente

ENTREGA:
  [ ] Docker image OU repositório privado criado
  [ ] license.key incluído no pacote
  [ ] public_key.pem incluído no pacote
  [ ] .env.example com instruções de BYOK
  [ ] Manual de instalação enviado ao cliente
  [ ] Chaves de API (OpenAI/Anthropic) configuradas pelo cliente

PÓS-VENDA:
  [ ] Sistema funcionando no servidor do cliente
  [ ] Backup do watermark_registry.db atualizado
  [ ] Data de renovação agendada no calendário

⚠️ NUNCA ENTREGUE:
  [ ] private_key.pem (sua chave de assinatura)
  [ ] watermark_registry.db (banco de registro de vendas)
  [ ] Pasta tools/ (ferramentas de administração)
  [ ] Código-fonte sem marca d'água
```

---

## 💰 MODELO DE PRECIFICAÇÃO SUGERIDO

| Item | Preço Sugerido |
|------|---------------|
| **Licença Anual** | R$ 15.000 — R$ 50.000 |
| **Instalação + Treinamento** | R$ 3.000 — R$ 8.000 |
| **Renovação Anual** | 40% do valor da licença |
| **Suporte Mensal** (opcional) | R$ 1.500 — R$ 3.000/mês |
| **Atualização Major** | R$ 5.000 — R$ 15.000 |

**Argumento de venda:** "O cliente economiza R$ 200-500 por análise manual de contrato. Com 10 contratos por mês, o sistema se paga em 1-3 meses."

---

## 🔒 RESUMO DA SEGURANÇA

```
O QUE O CLIENTE RECEBE:
├── Software funcional (Docker)
├── license.key (vinculada ao hardware DELE)
└── public_key.pem (só verifica, não cria licenças)

O QUE VOCÊ MANTÉM (NUNCA compartilhe):
├── private_key.pem (assina licenças)
├── watermark_registry.db (prova de vendas)
├── tools/ (gerador de licenças e marcas d'água)
└── Código-fonte original (sem marca d'água)

PROTEÇÕES ATIVAS:
├── Licença RSA-4096 vinculada ao hardware → Não roda em outro PC
├── Marca d'água em 5 locais ocultos → Identifica pirata mesmo se remover 2
├── Bloqueio binário → Funciona 100% ou bloqueia total (sem degradação)
└── Sem phone-home → 100% offline, sem dependência da sua infra
```

---

**Pronto!** Com este tutorial, você tem todo o fluxo: testar → vender → instalar → proteger → detectar pirataria. 🚀
