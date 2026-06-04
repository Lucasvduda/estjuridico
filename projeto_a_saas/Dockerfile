FROM python:3.12-slim

LABEL maintainer="LegalShield AI"
LABEL description="LegalShield AI SaaS - Multi-tenant Legal Analysis"

WORKDIR /app

# Instalar dependências do sistema (Tesseract OCR)
RUN apt-get update && apt-get install -y --no-install-recommends \
    tesseract-ocr \
    tesseract-ocr-por \
    libmagic1 \
    && rm -rf /var/lib/apt/lists/*

# Instalar dependências Python
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copiar código
COPY . .

# Criar usuário não-root para segurança (impede privilege escalation)
RUN groupadd -r appuser && useradd -r -g appuser -d /app -s /sbin/nologin appuser \
    && chown -R appuser:appuser /app
USER appuser

# Porta
EXPOSE 8000

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD python -c "import httpx; httpx.get('http://localhost:8000/health').raise_for_status()" || exit 0

# Roles suportadas via variável ROLE:
#   ROLE=api    -> sobe FastAPI/Uvicorn (recebe HTTP, enfileira análises)
#   ROLE=worker -> sobe Arq (consome fila Redis e roda análises pesadas)
# UVICORN_WORKERS controla quantos processos do uvicorn cada instância sobe.
ENV ROLE=api \
    UVICORN_WORKERS=2

CMD ["/bin/sh", "-c", "\
if [ \"$ROLE\" = \"worker\" ]; then \
    echo 'Iniciando Arq worker...'; \
    exec arq app.worker.WorkerSettings; \
else \
    echo \"Iniciando Uvicorn API (workers=${UVICORN_WORKERS})...\"; \
    exec uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers ${UVICORN_WORKERS}; \
fi"]
