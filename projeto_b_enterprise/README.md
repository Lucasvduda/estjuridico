# 🏢 LegalShield AI — Enterprise (Venda Única)

Sistema standalone de análise jurídica de contratos com IA. Empacotado em Docker, autocontido, sem dependências externas além da API do LLM.

## Arquitetura

```
projeto_b_enterprise/
├── app/
│   ├── main.py                   # FastAPI + validação de licença binária
│   ├── core/
│   │   ├── license_manager.py    # Hardware ID + RSA-4096 (bloqueio binário)
│   │   └── steganography.py      # Esteganografia digital (5 métodos)
│   └── services/
│       ├── analysis_engine.py    # Orquestrador dos 4 modos de análise
│       ├── document_processor.py # Extração PDF/DOCX/TXT + OCR
│       ├── llm_connector.py      # LiteLLM (OpenAI → Anthropic fallback)
│       ├── prompt_templates.py   # Prompts jurídicos especializados
│       ├── prompt_guard.py       # Anti-prompt-injection
│       └── report_generator.py   # Relatórios PDF profissionais
├── tools/                        # Ferramentas do VENDEDOR (não vai pro cliente)
│   ├── generate_watermark.py     # Gerar marca d'água na venda
│   ├── extract_watermark.py      # Extrator forense (em vazamentos)
│   └── generate_license.py       # Gerador de chaves e licenças
├── Dockerfile
├── docker-compose.yml
└── requirements.txt
```

## 🧠 Modos de Análise

| Modo | Finalidade |
|------|-----------|
| **Defensivo** | Identificar multas, prazos abusivos, responsabilidades ocultas |
| **Ofensivo** | Encontrar brechas para rescisão/invalidação sem ônus |
| **Auditoria** | Mapear passivos e janelas de renegociação em contratos assinados |
| **Blindagem** | Revisar minutas antes do envio para fechar brechas |

## 🔑 Modelo BYOK (Bring Your Own Key)

O cliente insere suas próprias chaves de API:
```env
OPENAI_API_KEY=sk-...       # Obrigatório
ANTHROPIC_API_KEY=sk-ant-... # Opcional (fallback)
```

Nenhum dado sai da infraestrutura do cliente, exceto as chamadas HTTPS para a API do LLM.

## 🔒 Proteção de Licença

**Bloqueio Binário** — funciona 100% ou não funciona:

```
Inicialização → Verifica License Key
  → Se VÁLIDA (hardware + data): Sistema funcional
  → Se INVÁLIDA: Bloqueio total + "Licença inválida. Contate o suporte."
```

- Licença assinada com RSA-4096 (chave privada fica com VOCÊ)
- Vinculada ao Hardware ID (CPU + MAC + Disco + Placa-mãe)
- Verificação na inicialização e a cada 24h de uptime
- **Sem degradação gradual** — decisão jurídica

## 🕵️ Anti-Pirataria (Esteganografia)

O ID do comprador é injetado de forma criptografada em **5 locais não-óbvios**:

| # | Local | Método |
|---|-------|--------|
| 1 | BD SQLite | Tabela `_sys_calibration` disfarçada |
| 2 | Config YAML | Caracteres zero-width invisíveis |
| 3 | SQL Migrations | Hash disfarçado em comentário |
| 4 | Imagens PNG | Metadados EXIF (icc_profile_hash) |
| 5 | Código Python | Constantes de "calibração" fragmentadas |

**O cliente nunca sabe onde estão os IDs.** Mesmo que encontre e remova 1 ou 2, os outros permanecem.

## 🛠️ Ferramentas do Vendedor

```bash
# 1. Gerar chaves RSA (uma vez)
python tools/generate_license.py init-keys

# 2. Na venda: gerar licença + marca d'água
python tools/generate_license.py generate --customer "Empresa X" --hardware-id "abc..."
python tools/generate_watermark.py --customer "Empresa X" --contract "CT-001"

# 3. Em caso de vazamento: extração forense
python tools/extract_watermark.py --source /caminho/software/vazado

# 4. Consultar Hardware ID de uma máquina
python tools/generate_license.py hwid
```

## 🚀 Deploy para o Cliente

```bash
# O cliente recebe:
# - Imagem Docker customizada (com marca d'água)
# - license.key (vinculada ao hardware dele)
# - public_key.pem (para validação)

docker-compose up -d
```

## 📋 Requisitos

- Docker & Docker Compose
- Chave de API OpenAI e/ou Anthropic (BYOK)
- Arquivo `license.key` válido
- Tesseract OCR (incluído no Docker)

## ⚠️ IMPORTANTE

- A pasta `tools/` é para USO INTERNO (vendedor). **Nunca envie para o cliente.**
- O banco `watermark_registry.db` é a prova das vendas. **Guarde em local seguro.**
- A `private_key.pem` nunca deve ser compartilhada. Apenas a `public_key.pem` vai para o cliente.
