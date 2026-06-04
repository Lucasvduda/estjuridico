"""
LegalShield AI 2026 — Analysis Router (Projeto A SaaS)

Endpoints:
    POST   /                — enfileira uma análise (responde em < 1s)
    GET    /                — lista análises do tenant (com paginação)
    GET    /{analysis_id}   — busca o relatório completo (usado para polling
                              do frontend até `status == "completed"`)

PRIVACIDADE:
Nada do contrato em si fica armazenado em disco. O endpoint POST apenas
verifica que os bytes ainda estão no cache (Redis) e enfileira o job. O
worker em background processa, e o relatório completo (achados, score,
resumo, recomendações, modelo usado, tokens, custo) é gravado em `Analysis`.
"""

import logging
import uuid as _uuid
from datetime import datetime, timezone

from arq import create_pool
from arq.connections import RedisSettings
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from ...config import get_settings
from ...models import Analysis, Contract, Tenant, User
from ...schemas import (
    AnalysisFindingSchema,
    AnalysisListResponse,
    AnalysisRequest,
    AnalysisResponse,
)
from ...services.contract_cache import get_active_backend, get_ttl_seconds
from ..deps import get_current_user, get_db, log_audit

logger = logging.getLogger(__name__)
settings = get_settings()
router = APIRouter()


def _analysis_to_response(analysis: Analysis, with_achados: bool = True) -> AnalysisResponse:
    """Serializa Analysis -> AnalysisResponse, opcionalmente sem o array de achados."""
    achados: list[AnalysisFindingSchema] = []
    if with_achados and analysis.results_json:
        for i, a in enumerate(analysis.results_json):
            achados.append(
                AnalysisFindingSchema(
                    id=i + 1,
                    titulo=a.get("titulo", ""),
                    severidade=a.get("severidade", "MÉDIO"),
                    clausula=a.get("clausula", ""),
                    descricao=a.get("descricao", ""),
                    fundamentacao_legal=a.get("fundamentacao_legal", ""),
                    recomendacao=a.get("recomendacao", ""),
                    impacto_financeiro=a.get("impacto_financeiro", ""),
                )
            )

    return AnalysisResponse(
        id=str(analysis.id),
        contract_id=str(analysis.contract_id),
        mode=analysis.analysis_mode,
        status=analysis.status,
        resumo_executivo=analysis.resumo_executivo or "",
        score_risco=analysis.score_risco or 0,
        achados=achados,
        total_achados=analysis.total_achados or 0,
        model_used=analysis.model_used or "",
        tokens_used=analysis.tokens_used or 0,
        cost_usd=analysis.cost_usd or 0.0,
        created_at=analysis.created_at,
        completed_at=analysis.completed_at,
    )


@router.post("/", response_model=AnalysisResponse, status_code=202)
async def create_analysis(
    body: AnalysisRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Enfileira uma análise. Responde em < 1s com status='queued'.

    O frontend deve fazer polling em GET /{analysis_id} a cada 3-5s até o
    `status` virar `completed` (ou `failed`).
    """

    result = await db.execute(
        select(Contract).where(
            Contract.id == body.contract_id,
            Contract.tenant_id == user.tenant_id,
        )
    )
    contract = result.scalar_one_or_none()
    if not contract:
        raise HTTPException(status_code=404, detail="Contrato não encontrado")

    tenant_q = await db.execute(select(Tenant).where(Tenant.id == user.tenant_id))
    tenant = tenant_q.scalar_one()

    first_of_month = datetime.now(timezone.utc).replace(
        day=1, hour=0, minute=0, second=0, microsecond=0
    )
    monthly_count = await db.execute(
        select(func.count()).select_from(Analysis).where(
            Analysis.tenant_id == user.tenant_id,
            Analysis.created_at >= first_of_month,
        )
    )
    current_count = monthly_count.scalar() or 0

    if tenant.max_analyses_per_month > 0 and current_count >= tenant.max_analyses_per_month:
        raise HTTPException(
            status_code=429,
            detail=f"Limite mensal de {tenant.max_analyses_per_month} análises atingido",
        )

    ttl = await get_ttl_seconds(str(contract.id))
    if ttl is None:
        raise HTTPException(
            status_code=410,
            detail=(
                "Os bytes do contrato expiraram do cache temporário. "
                "Faça upload do contrato novamente para iniciar a análise."
            ),
        )

    analysis = Analysis(
        tenant_id=user.tenant_id,
        contract_id=contract.id,
        requested_by=user.id,
        analysis_mode=body.mode,
        status="queued",
    )
    db.add(analysis)
    await db.flush()

    if get_active_backend() == "memory":
        # Modo sem fila: executa a análise diretamente no request.
        # Ativado quando: REDIS_URL vazio, Redis offline, ou STORAGE_BACKEND=memory.
        # Ideal para testes locais sem Docker. Em produção nunca deve cair aqui.
        await db.commit()
        from ...worker import run_analysis as _run_analysis_inline

        logger.warning(
            "storage=memory — análise rodando INLINE (sem fila). "
            "Normal em dev sem Docker; não deve ocorrer em produção."
        )
        await _run_analysis_inline({}, str(analysis.id))
        await db.refresh(analysis)
    else:
        await db.commit()
        pool = None
        try:
            pool = await create_pool(RedisSettings.from_dsn(settings.redis_url))
            await pool.enqueue_job("run_analysis", str(analysis.id))
        except Exception as e:
            logger.error("Falha ao enfileirar análise %s: %s", analysis.id, e)
            analysis.status = "failed"
            analysis.resumo_executivo = "Não foi possível enfileirar a análise."
            await db.flush()
            raise HTTPException(
                status_code=503,
                detail="Sistema de fila indisponível. Tente novamente em instantes.",
            )
        finally:
            if pool is not None:
                try:
                    await pool.aclose()
                except Exception:
                    try:
                        await pool.close()
                    except Exception:
                        pass

    await log_audit(
        db,
        action="enqueue_analysis",
        user_id=str(user.id),
        tenant_id=str(user.tenant_id),
        resource_type="analysis",
        resource_id=str(analysis.id),
        details={"mode": body.mode, "contract_id": str(contract.id)},
    )

    return _analysis_to_response(analysis)


@router.get("/", response_model=AnalysisListResponse)
async def list_analyses(
    contract_id: str | None = None,
    page: int = 1,
    per_page: int = 20,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Lista análises do tenant, opcionalmente filtradas por contrato."""
    query = select(Analysis).where(Analysis.tenant_id == user.tenant_id)
    count_query = select(func.count()).select_from(Analysis).where(
        Analysis.tenant_id == user.tenant_id
    )

    if contract_id:
        # Validar que o contrato pertence ao tenant do usuário (prevenir IDOR)
        contract_check = await db.execute(
            select(Contract.id).where(
                Contract.id == contract_id,
                Contract.tenant_id == user.tenant_id,
            )
        )
        if not contract_check.scalar_one_or_none():
            raise HTTPException(status_code=404, detail="Contrato não encontrado")
        query = query.where(Analysis.contract_id == contract_id)
        count_query = count_query.where(Analysis.contract_id == contract_id)

    total = (await db.execute(count_query)).scalar() or 0

    query = (
        query.order_by(Analysis.created_at.desc())
        .offset((page - 1) * per_page)
        .limit(per_page)
    )
    result = await db.execute(query)
    analyses = result.scalars().all()

    items = [_analysis_to_response(a, with_achados=False) for a in analyses]
    return AnalysisListResponse(analyses=items, total=total)


@router.get("/{analysis_id}", response_model=AnalysisResponse)
async def get_analysis(
    analysis_id: str,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Retorna o relatório completo. Frontend faz polling até status='completed'."""
    try:
        _uuid.UUID(analysis_id)
    except (ValueError, AttributeError):
        raise HTTPException(status_code=404, detail="Análise não encontrada")

    result = await db.execute(
        select(Analysis).where(
            Analysis.id == analysis_id,
            Analysis.tenant_id == user.tenant_id,
        )
    )
    analysis = result.scalar_one_or_none()
    if not analysis:
        raise HTTPException(status_code=404, detail="Análise não encontrada")

    return _analysis_to_response(analysis)
