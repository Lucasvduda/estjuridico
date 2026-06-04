# LegalShield AI — Tutorial Deploy no Render com Escala Real

> **Versão:** 2.0 (Maio 2026) — abordagem "zero-armazenamento de contrato"
> **Foco:** Subir o `projeto_a_saas/` no Render de forma **simples, segura e que escala por uso**.
> **Privacidade:** o contrato em si NUNCA é armazenado de forma persistente.
> Só o **relatório completo** (achados, score, resumo, recomendações) fica no banco.

---

## Índice

1. [Conceito: por que o código foi reorganizado](#1-conceito)
2. [Arquitetura final (o que vamos montar)](#2-arquitetura-final)
3. [Modelo de custo proporcional ao uso](#3-modelo-de-custo)
4. [O que mudou no código (já aplicado)](#4-codigo)
5. [Configurar o Render passo a passo](#5-passo-a-passo-render)
6. [Apontar o domínio (Registro.br/Cloudflare → Render)](#6-dominio)
7. [Travas de segurança e LGPD](#7-seguranca)
8. [Como medir o custo real e proteger a conta](#8-medicao-custo)
9. [Roteiro de quando escalar mais](#9-quando-escalar)
10. [Testar localmente antes de subir](#10-testar-local)

---

<a id="1-conceito"></a>

## 1. Por que o código foi reorganizado

A versão anterior do `projeto_a_saas/` fazia a análise **dentro da requisição HTTP**:
o usuário clicava em "Analisar" e a API só respondia depois que a OpenAI/Anthropic
terminasse (10–90s). Isso tem dois problemas graves:

1. **Não escala** — cada análise segura um worker por dezenas de segundos. 100k
   pedidos simultâneos derrubam qualquer servidor.
2. **Não é privado** — o contrato ficava criptografado em disco indefinidamente.
   Mau para LGPD; ponto extra de ataque.

A nova arquitetura resolve as duas coisas com uma única ideia: **mover o trabalho
pesado para um worker em background** e usar o **Redis como memória temporária**
dos bytes do contrato.

```
[Cliente]
   |
   |  1) POST /v1/contracts/upload (PDF)         -> bytes vão pro Redis (TTL 30 min)
   |     responde {contract_id} em < 1s
   |
   |  2) POST /v1/analysis (contract_id, mode)   -> enfileira job no Redis
   |     responde {analysis_id, status: "queued"} em < 1s
   |
   |  3) GET /v1/analysis/{id}  (polling 3-5s)   -> banco devolve achados quando prontos
   v
[API FastAPI]  ────────────┐
                            │ enqueue
                            ▼
                        [Redis: fila Arq + bytes do contrato]
                            ▲
                            │ pega job + bytes
                  ┌─────────┴───────────┐
                  │  Workers Arq (1..N) │  ← Render escala automaticamente
                  └─────────┬───────────┘
                            │ chama OpenAI/Anthropic
                            │ grava resultado completo
                            ▼
                       [PostgreSQL]    ← achados, score, resumo,
                                          recomendações, tokens, custo
```

**O que NÃO fica armazenado:** PDF/DOCX/TXT do contrato.
**O que FICA armazenado:** nome do arquivo + hash + páginas + **TODO o relatório**.

Após 30 minutos sem uso, o Redis apaga os bytes sozinho (TTL automático).

---

<a id="2-arquitetura-final"></a>

## 2. Arquitetura final no Render

| Componente | Serviço Render | Função |
| --- | --- | --- |
| **API Web** | Web Service (autoscale 1→4) | Recebe HTTP, enfileira análises |
| **Worker(s) IA** | Background Worker (autoscale 1→10) | Consome fila e chama OpenAI/Anthropic |
| **PostgreSQL** | Render Postgres (Basic 256 MB) | Banco gerenciado (backup automático) |
| **Redis** | Render Key Value (Standard 1 GB) | Fila + bytes temporários do contrato |
| **DNS + WAF** | Cloudflare (externo, gratuito) | Domínio + proteção contra DDoS |

> **Por que Redis Standard e não Starter?**
> Os bytes do PDF vivem no Redis durante a análise. Com `MAX_FILE_SIZE_MB=25` e
> alguns picos simultâneos, o plano Starter (25 MB) lota fácil. Standard (1 GB)
> custa ~US$ 30/mês e segura conforto.

---

<a id="3-modelo-de-custo"></a>

## 3. Modelo de custo proporcional ao uso

### 3.1. Custo fixo mínimo (sempre ligado — 0 a poucos usuários)

| Item | Plano | Custo aprox. (USD/mês) |
| --- | --- | --- |
| Web Service (API) | Starter (512 MB) | ~7 |
| Background Worker | Starter (512 MB) | ~7 |
| Postgres | Basic 256 MB | ~7 |
| Redis (Key Value Standard 1 GB) | Standard | ~30 |
| Cloudflare DNS/WAF | Free | 0 |
| **TOTAL FIXO** | | **~51 USD (~R$ 265/mês)** |

Esse é o piso, com **zero usuário** o site fica no ar custando isso.

> Se quiser economizar: pode começar com Redis Starter (25 MB) e
> `MAX_FILE_SIZE_MB=5`. Suporta uns 4-5 contratos simultâneos. Custa ~R$ 200/mês.

### 3.2. Quando o uso cresce (autoscaling)

Você configura **autoscale baseado em CPU/memória**:

| Carga (análises/dia) | Web Services | Workers | Custo infra aprox. |
| --- | --- | --- | --- |
| < 100 (uso mínimo / 1000 pessoas só lendo) | 1 | 1 | ~R$ 265/mês |
| 1.000 | 1 | 1–2 | ~R$ 320/mês |
| 10.000 | 1–2 | 2–5 | ~R$ 500–800/mês |
| 100.000 | 2–4 | 5–15 | ~R$ 1.500–3.000/mês |

> Os workers só "acordam" quando tem fila. Se ninguém está analisando contrato,
> você fica só com o piso. **É exatamente "1000 pessoas usando = custo menor".**

### 3.3. Custo da IA (variável, sempre o maior componente)

| Cenário | Custo aprox. de IA (OpenAI/Anthropic) |
| --- | --- |
| 100 análises/dia | R$ 30–200/mês |
| 1.000 análises/dia | R$ 300–2.000/mês |
| 10.000 análises/dia | R$ 3.000–20.000/mês |
| 100.000 análises/dia | R$ 30.000–200.000/mês |

**A IA é sempre o custo dominante.** A infra escala junto, mas é fração disso.

### 3.4. Limitação real: rate limits da OpenAI/Anthropic

Para **realmente** processar 100k contratos/dia você precisa:
- **OpenAI Tier 4+** (acima de US$ 250 pagos) ou Enterprise
- **Anthropic Build Tier 3+** (acima de US$ 400 pagos)

Sem isso, mesmo com 50 workers prontos, eles ficam esperando a IA destravar.
Use o fallback model + ajuste `WORKER_MAX_JOBS_PER_MINUTE`.

---

<a id="4-codigo"></a>

## 4. O que mudou no código (já aplicado)

Essas mudanças já estão aplicadas no `projeto_a_saas/`. Lista para referência:

### 4.1. Novas dependências (`requirements.txt`)

```text
redis[hiredis]==5.2.1     # já existia
arq==0.26.1               # NOVO — fila de tarefas em cima de Redis
```

### 4.2. Novas variáveis em `app/config.py`

```python
contract_cache_ttl_seconds: int = 1800    # 30 min — TTL dos bytes no Redis
worker_concurrency: int = 4               # jobs em paralelo por worker
worker_max_jobs_per_minute: int = 60      # rate limit p/ proteger OpenAI
worker_job_timeout: int = 600             # 10 min por job
```

### 4.3. Modelo `Contract` (em `app/models/__init__.py`)

Tornou-se um **registro de metadados**, sem caminho de arquivo:

- `original_filename`, `file_type`, `file_size_bytes`, `sha256_hash`, `page_count` → mantidos
- `encrypted_path` e `stored_filename` → opcionais (nullable), não usados
- Novo `bytes_discarded_at` → marca quando os bytes foram apagados do Redis
- Novo status `discarded` → quando os bytes já foram embora

### 4.4. NOVO: `app/services/contract_cache.py`

Helper para guardar/buscar/apagar bytes do contrato no Redis com TTL automático.
Funciona com fallback em memória quando `REDIS_URL` está vazio (modo dev).

### 4.5. NOVO: `app/worker.py`

Worker Arq que:
1. Pega `analysis_id` da fila.
2. Busca metadados do contrato + bytes do Redis.
3. Roda o `AnalysisEngine` (extração + IA).
4. Salva **todo o relatório** (achados, score, resumo, tokens, custo) no banco.
5. Marca `Analysis.status = "completed"`.

Iniciado por: `arq app.worker.WorkerSettings`.

### 4.6. Refatorado: `app/api/v1/contracts.py`

- `POST /v1/contracts/upload`: bytes vão para Redis (não para disco). Retorna `contract_id`.
- `DELETE /v1/contracts/{id}`: apaga bytes do Redis e a linha de metadados. Os
  relatórios (Analysis) gerados a partir desse contrato **permanecem** no histórico.

### 4.7. Refatorado: `app/api/v1/analysis.py`

- `POST /v1/analysis/`: agora retorna **HTTP 202** com `status="queued"`. Enfileira no Arq.
- Se os bytes já expiraram do Redis: retorna **HTTP 410** com instrução de reupload.
- `GET /v1/analysis/{id}`: igual ao anterior — usado para **polling** do frontend.

### 4.8. `Dockerfile`

Mesma imagem serve API ou worker via variável `ROLE`:

```sh
ROLE=api    -> uvicorn ... (porta 8000)
ROLE=worker -> arq app.worker.WorkerSettings
```

### 4.9. `docker-compose.yml`

Agora tem 4 serviços: `api`, `worker`, `db`, `redis`. Sobe tudo com `docker compose up --build`.

### 4.10. `render.yaml`

Blueprint pronto: 1 web + 1 worker + Postgres + Redis Standard. Autoscaling configurado.

---

<a id="5-passo-a-passo-render"></a>

## 5. Passo a passo no Render

### 5.1. Pré-requisitos

- [ ] Conta no Render (https://render.com — **crie usando "Sign up with GitHub"**,
  assim o Render já fica autorizado a ler seus repositórios e o deploy na etapa 5.3
  funciona sem nenhum passo extra. Evite criar com Google/email; teria que vincular
  o GitHub manualmente depois).
- [ ] Conta na **Cloudflare** (opcional mas recomendado, https://cloudflare.com — grátis, p/ DNS + WAF).
- [ ] Conta na **OpenAI** e/ou **Anthropic** com chaves API.
- [ ] Domínio já registrado (Registro.br, etc.).
- [ ] Repositório do `projeto_a_saas/` no GitHub.

### 5.2. Gerar segredos para colar no painel

Gere agora (anote em local seguro):

```bash
# JWT (Render também pode gerar automático)
openssl rand -hex 64

# Master key da criptografia (32 bytes em base64)
openssl rand -base64 32
```

### 5.3. Subir o blueprint (1 clique cria tudo)

O arquivo `projeto_a_saas/render.yaml` já descreve toda a infra. No Render:

1. **New +** → **Blueprint**.
2. Conectar o repositório do GitHub.
3. O Render detecta o `render.yaml` e propõe criar 4 recursos:
   - `legalshield-api` (Web Service, autoscale 1→4)
   - `legalshield-worker` (Background Worker, autoscale 1→10)
   - `legalshield-db` (PostgreSQL)
   - `legalshield-redis` (Key Value / Redis Standard 1 GB)
4. Clique em **Apply**. Em 5–10 minutos tudo sobe.

### 5.4. Definir as variáveis sensíveis

No painel de **cada serviço** (`legalshield-api` e `legalshield-worker`),
aba **Environment**, defina:

| Variável | Valor | Observação |
| --- | --- | --- |
| `OPENAI_API_KEY` | sua chave | obrigatório se usar OpenAI |
| `ANTHROPIC_API_KEY` | sua chave | obrigatório se usar Claude |
| `ENCRYPTION_MASTER_KEY` | gerado no 5.2 | **MESMO valor em API e Worker** |
| `CORS_ORIGINS` | `["https://app.seudominio.com.br"]` | seu domínio |
| `ADMIN_EMAIL` | seu email | conta inicial de admin |
| `ADMIN_INITIAL_PASSWORD` | senha forte | troque após primeiro login |

`JWT_SECRET_KEY` é gerado automaticamente pelo Render (já está no blueprint).
`DATABASE_URL` e `REDIS_URL` são preenchidos automaticamente entre os serviços.

> **Não comite o `.env` no GitHub.** Verifique se está no `.gitignore`.

### 5.5. Rodar as migrações (uma vez só)

No serviço `legalshield-api`, aba **Shell**:

```bash
alembic upgrade head
```

Se ainda não tem alembic configurado, em primeiro deploy a app já cria tabelas
via `init_db()` no startup (verificar `app/main.py` linha ~65 — só quando `DEBUG=true`).

### 5.6. Ativar autoscaling

Em **cada serviço** (API e Worker), o blueprint já ativou autoscaling, mas
confira em **Settings** → **Scaling**:

- API: Min 1, Max 4, CPU 60%
- Worker: Min 1, Max 10, CPU 70%

Pronto. A partir daqui, quando a fila enche, o Render sobe mais workers
automaticamente. Quando esvazia, derruba e para de cobrar.

---

<a id="6-dominio"></a>

## 6. Apontar o domínio

### Caso A — Usando Cloudflare como DNS (recomendado, gratuito, com proteção DDoS)

1. No Cloudflare, adicione o seu domínio (segue assistente).
2. No Registro.br (ou onde comprou), aponte os nameservers para os da Cloudflare.
3. Aguarde propagação (até 24h, geralmente < 1h).
4. No Render, serviço `legalshield-api` → **Settings** → **Custom Domains** →
   adicionar `app.seudominio.com.br`. O Render mostra um CNAME tipo
   `legalshield-api.onrender.com`.
5. No Cloudflare → **DNS** → adicionar `CNAME app legalshield-api.onrender.com`
   com **Proxy status: DNS only** (a primeira vez; depois você pode ligar o proxy).
6. O Render emite o certificado HTTPS (Let's Encrypt) sozinho em ~2 min.

### Caso B — Domínio direto pelo Registro.br

Mesmos passos, só não passa pela Cloudflare. Você perde o WAF/DDoS grátis,
mas é mais simples.

---

<a id="7-seguranca"></a>

## 7. Travas de segurança e LGPD

### 7.1. O que a nova arquitetura entrega de cara

- **Contrato não persistido**: bytes somem do Redis em 30 min (TTL automático).
  Mesmo um vazamento do banco **não expõe os PDFs originais** (eles não existem mais).
- **HTTPS automático** (Let's Encrypt).
- **Patches de OS e Docker** cuidados pelo Render.
- **Postgres com backup diário automático** (7 dias retidos no Basic).
- **Variáveis de ambiente criptografadas** em repouso.
- **Rede privada** entre serviços (DB e Redis não expostos à internet).

### 7.2. O que VOCÊ ainda tem que fazer

- **Rotacionar `JWT_SECRET_KEY` e `ENCRYPTION_MASTER_KEY`** a cada 6–12 meses.
- **Limitar gasto na OpenAI/Anthropic** (painel deles → "Usage limits"). Ex: cap
  mensal de US$ 500 para começar.
- **Termo de Uso + Política de Privacidade** acessíveis no site.
- **DPO designado** (LGPD obriga para tratamento de dados pessoais sensíveis).
- **Decidir sobre o `results_json`**: ele guarda trechos das cláusulas que podem
  conter dados pessoais. Para nível "enterprise" considere anonimizar (CPF/nomes
  via regex antes de salvar). Você já tem `prompt_guard.py` no projeto que pode
  ser estendido para isso.

### 7.3. Onde os dados ficam (LGPD)

- Render Postgres rodando em **Frankfurt (UE)** (já configurado no `render.yaml`).
- Cloudflare DNS distribuído globalmente.
- OpenAI/Anthropic recebem o texto do contrato em chamada API. Você pode pedir
  contrato de "no-training" (eles têm). **Para LGPD enterprise**, exija isso.

---

<a id="8-medicao-custo"></a>

## 8. Como medir o custo real e proteger a conta

### 8.1. Painéis de custo

- **Render** → dashboard mostra USD acumulado no mês por serviço.
- **OpenAI** → https://platform.openai.com/usage → defina **hard limit** (cap).
- **Anthropic** → https://console.anthropic.com/usage → defina **spend limit**.

### 8.2. Alarme próprio no banco (recomendado)

O modelo `Analysis` já guarda `cost_usd` por análise. Crie um cron job no worker
(Arq suporta cron nativo). Em `app/worker.py`, dentro de `WorkerSettings`:

```python
from arq.cron import cron
from datetime import timedelta
from sqlalchemy import func, select

async def daily_cost_alert(ctx):
    async with async_session_factory() as db:
        result = await db.execute(
            select(func.sum(Analysis.cost_usd)).where(
                Analysis.created_at >= datetime.now(timezone.utc) - timedelta(days=1)
            )
        )
        total = result.scalar() or 0.0
        if total > 50.0:  # > US$ 50/dia
            # enviar email/Slack
            ...

class WorkerSettings:
    functions = [run_analysis]
    cron_jobs = [cron(daily_cost_alert, hour=8, minute=0)]
    ...
```

### 8.3. Rate limit por tenant (já existe no projeto)

O campo `max_analyses_per_month` em `Tenant` já trava no endpoint
`POST /v1/analysis/`. Para os planos:

| Plano | Análises/mês |
| --- | --- |
| Free | 10 |
| Pro | 200 |
| Enterprise | ilimitado (com SLA contratual) |

---

<a id="9-quando-escalar"></a>

## 9. Roteiro de quando escalar mais

| Sintoma | Ação |
| --- | --- |
| Fila Redis > 1000 itens persistentemente | Aumentar `maxInstances` do worker no `render.yaml` |
| Postgres CPU > 80% por 10+ min | Upgrade para plano Standard ou Pro |
| Redis memória > 80% | Aumentar plano do Key Value (Standard 1GB → Pro 5GB) |
| Latência da API > 1s | Adicionar instância da API |
| OpenAI batendo `429 rate limit` | Pedir upgrade de tier OR reduzir `WORKER_MAX_JOBS_PER_MINUTE` |
| Custo de IA explodindo | Trocar `LLM_PRIMARY_MODEL` para modelo mais barato (GPT-4o-mini, Claude Haiku) |
| Bytes do contrato muito grandes no Redis | Reduzir `MAX_FILE_SIZE_MB` ou `CONTRACT_CACHE_TTL_SECONDS` |

Quando ultrapassar **~50k análises/dia** consistentemente, vale considerar:
- **Cache de análises idênticas** (mesmo SHA256 do contrato → resultado cacheado).
- **Migração para AWS/GCP** com Spot Instances (custo 40-60% menor).
- **Negociar com OpenAI/Anthropic** preço por volume.

---

<a id="10-testar-local"></a>

## 10. Testar localmente antes de subir

```bash
# 1. Subir tudo (api + worker + db + redis)
cd projeto_a_saas
docker compose up --build

# 2. Em outro terminal: ver os logs do worker
docker compose logs -f worker

# 3. Smoke test (fazer upload de um contrato e ver a fila trabalhar)
#    Use o frontend em http://localhost:8000 ou:
curl -X POST http://localhost:8000/api/v1/contracts/upload \
  -H "Authorization: Bearer <token>" \
  -F "file=@meu_contrato.pdf"
# Anote o {id} retornado.

curl -X POST http://localhost:8000/api/v1/analysis/ \
  -H "Authorization: Bearer <token>" \
  -H "Content-Type: application/json" \
  -d '{"contract_id": "<id>", "mode": "defensive"}'
# Deve retornar status="queued" na hora.

# 4. Poll do resultado
curl http://localhost:8000/api/v1/analysis/<analysis_id> \
  -H "Authorization: Bearer <token>"
# Repete a cada 3s até status="completed".

# 5. Encerrar
docker compose down
```

---

## Resumo do que fazer AGORA (ordem prática)

1. [ ] Criar conta Render + chaves OpenAI/Anthropic.
2. [ ] Commitar e dar `git push` no GitHub (código já refatorado).
3. [ ] Render → Blueprint → apontar o repositório → Apply.
4. [ ] Preencher as variáveis de ambiente sensíveis (5.4).
5. [ ] Apontar domínio (passo 6).
6. [ ] Definir limites de gasto nos painéis OpenAI/Anthropic.
7. [ ] Testar com 1 contrato real. Depois 100. Depois 1.000.

**Não pule o passo 6.** Sem cap de gasto na OpenAI, um bug ou ataque pode gerar
conta de milhares de dólares em horas.
