"""
LegalShield AI 2026 — Worker assíncrono (Arq + Redis)

Consome a fila de análises e executa o trabalho pesado fora do request HTTP.
Iniciado por:

    arq app.worker.WorkerSettings

Fluxo de um job:

    1. Recebe analysis_id (UUID da Analysis em status="queued").
    2. Busca metadados do contrato no Postgres.
    3. Busca bytes do contrato no Redis (contract_cache).
    4. Roda o AnalysisEngine (extração + IA).
    5. Persiste TODO o relatório (achados, score, resumo, tokens, custo) na
       linha de Analysis. Nada do contrato fica armazenado em disco/S3.
    6. Marca o contrato como "analyzed" — bytes seguem no Redis até o TTL
       expirar (permite o usuário rodar outro modo). Pode ser descartado
       manualmente via DELETE /contracts/{id}.

Se os bytes já expiraram quando o worker pega o job (caso raro de fila lenta),
a análise é marcada como "failed" com motivo claro, e o frontend pede reupload.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone

from arq.connections import RedisSettings
from sqlalchemy import select

from .config import get_settings
from .database import async_session_factory
from .models import Analysis, Contract, TokenUsage
from .services.analysis_engine import AnalysisEngine
from .services.contract_cache import fetch_contract_bytes
from .services.llm_connector import LLMConfig
from .services.prompt_templates import AnalysisMode

logger = logging.getLogger(__name__)
settings = get_settings()


_MODE_MAP = {
    "defensive": AnalysisMode.DEFENSIVE,
    "offensive": AnalysisMode.OFFENSIVE,
    "audit": AnalysisMode.AUDIT,
    "shield": AnalysisMode.SHIELD,
}


async def run_analysis(ctx: dict, analysis_id: str) -> dict:
    """Job principal — executa a análise pesada e persiste o relatório."""
    import os
    openai_key = settings.openai_api_key or os.environ.get("OPENAI_API_KEY", "")
    anthropic_key = settings.anthropic_api_key or os.environ.get("ANTHROPIC_API_KEY", "")
    # print() garante saída no stdout do Render (logger.info é filtrado)
    print(f"[WORKER] analysis={analysis_id[:8]} openai={'SET('+openai_key[:8]+')' if openai_key else 'EMPTY'} settings_key={'SET' if settings.openai_api_key else 'NONE'} env_key={'SET' if os.environ.get('OPENAI_API_KEY') else 'NONE'}", flush=True)

    llm_config = LLMConfig(
        openai_api_key=openai_key,
        anthropic_api_key=anthropic_key,
    )
    engine = AnalysisEngine(config=llm_config)

    async with async_session_factory() as db:
        result = await db.execute(select(Analysis).where(Analysis.id == analysis_id))
        analysis = result.scalar_one_or_none()
        if not analysis:
            logger.error("worker: analysis_id=%s não existe no banco", analysis_id)
            return {"ok": False, "reason": "analysis_not_found"}

        analysis.status = "processing"
        await db.commit()

        contract_q = await db.execute(
            select(Contract).where(Contract.id == analysis.contract_id)
        )
        contract = contract_q.scalar_one_or_none()
        if not contract:
            analysis.status = "failed"
            await db.commit()
            return {"ok": False, "reason": "contract_not_found"}

        file_bytes = await fetch_contract_bytes(str(contract.id))
        if file_bytes is None:
            logger.warning(
                "worker: bytes do contrato %s não estão mais no Redis (TTL expirou). "
                "Marcando análise como failed.",
                contract.id,
            )
            analysis.status = "failed"
            analysis.resumo_executivo = (
                "Os bytes do contrato expiraram do cache antes que a análise pudesse "
                "ser processada. Faça upload do contrato novamente."
            )
            contract.status = "discarded"
            contract.bytes_discarded_at = datetime.now(timezone.utc)
            await db.commit()
            return {"ok": False, "reason": "contract_bytes_expired"}

        try:
            ar = await engine.analyze_file(
                file_bytes=file_bytes,
                filename=contract.original_filename,
                mode=_MODE_MAP[analysis.analysis_mode],
            )
        except Exception as e:
            logger.exception("worker: falha na análise %s: %s", analysis_id, e)
            analysis.status = "failed"
            analysis.resumo_executivo = f"Erro ao processar: {e}"
            await db.commit()
            return {"ok": False, "reason": "engine_error", "error": str(e)}

        analysis.status = "completed"
        analysis.results_json = [a.model_dump() for a in ar.achados]
        analysis.resumo_executivo = ar.resumo_executivo
        analysis.score_risco = ar.score_risco
        analysis.total_achados = ar.estatisticas.total_achados
        analysis.injection_detected = ar.injection_detected
        if ar.token_usage:
            analysis.model_used = ar.token_usage.model_used
            analysis.tokens_used = ar.token_usage.total_tokens
            analysis.cost_usd = ar.token_usage.cost_estimate_usd
            analysis.latency_seconds = ar.token_usage.latency_seconds

            db.add(
                TokenUsage(
                    tenant_id=analysis.tenant_id,
                    analysis_id=analysis.id,
                    provider="openai" if "openai" in (ar.token_usage.model_used or "").lower() else "anthropic",
                    model=ar.token_usage.model_used or "",
                    prompt_tokens=getattr(ar.token_usage, "prompt_tokens", 0),
                    completion_tokens=getattr(ar.token_usage, "completion_tokens", 0),
                    total_tokens=ar.token_usage.total_tokens,
                    cost_usd=ar.token_usage.cost_estimate_usd,
                )
            )

        analysis.completed_at = datetime.now(timezone.utc)
        contract.status = "analyzed"
        contract.page_count = ar.page_count or contract.page_count
        contract.ocr_used = ar.ocr_used

        await db.commit()
        logger.info(
            "worker: análise %s concluída — score=%s, achados=%s, tokens=%s",
            analysis_id,
            analysis.score_risco,
            analysis.total_achados,
            analysis.tokens_used,
        )

        return {
            "ok": True,
            "analysis_id": analysis_id,
            "score_risco": analysis.score_risco,
            "total_achados": analysis.total_achados,
        }


async def startup(ctx: dict) -> None:
    import os
    from .services.redis_client import init_redis_pool
    redis = await init_redis_pool()
    key = settings.openai_api_key or os.environ.get("OPENAI_API_KEY", "")
    print(f"[WORKER STARTUP] redis={'OK' if redis else 'FAIL'} openai={'SET('+key[:8]+')' if key else 'EMPTY'}", flush=True)


async def shutdown(ctx: dict) -> None:
    from .services.redis_client import close_redis_pool
    await close_redis_pool()
    logger.info("worker: encerrado")


class WorkerSettings:
    """Configuração que o CLI do Arq descobre via `arq app.worker.WorkerSettings`."""

    functions = [run_analysis]
    on_startup = startup
    on_shutdown = shutdown
    redis_settings = RedisSettings.from_dsn(settings.redis_url or "redis://localhost:6379/0")
    max_jobs = settings.worker_concurrency
    job_timeout = settings.worker_job_timeout
    keep_result = 86400  # mantém resultado da fila por 1 dia
    max_burst_jobs = -1
