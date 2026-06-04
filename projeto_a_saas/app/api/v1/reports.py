"""
LegalShield AI 2026 — Reports Router (Projeto A SaaS)
Endpoint de exportação de relatórios em PDF.
"""

import io
import logging

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ...models import Analysis, Contract, Tenant, User
from ...schemas import ReportExportRequest
from ..deps import get_current_user, get_db, log_audit

logger = logging.getLogger(__name__)
router = APIRouter()


@router.post("/export")
async def export_report(
    body: ReportExportRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Gera relatório PDF de uma análise concluída."""

    # Buscar análise
    result = await db.execute(
        select(Analysis).where(
            Analysis.id == body.analysis_id,
            Analysis.tenant_id == user.tenant_id,
        )
    )
    analysis = result.scalar_one_or_none()
    if not analysis:
        raise HTTPException(status_code=404, detail="Análise não encontrada")

    if analysis.status != "completed":
        raise HTTPException(status_code=400, detail="Análise ainda não foi concluída")

    # Buscar contrato e tenant para metadados do relatório
    contract_q = await db.execute(
        select(Contract).where(Contract.id == analysis.contract_id)
    )
    contract = contract_q.scalar_one()

    tenant_q = await db.execute(
        select(Tenant).where(Tenant.id == user.tenant_id)
    )
    tenant = tenant_q.scalar_one()

    # Gerar PDF usando o report_generator do services
    from ...services.report_generator import ReportGenerator

    generator = ReportGenerator()

    # Montar dados para o relatório
    report_data = {
        "resumo_executivo": analysis.resumo_executivo or "",
        "score_risco": analysis.score_risco or 0,
        "achados": analysis.results_json or [],
        "modo": analysis.analysis_mode,
    }

    metadata = {
        "empresa": tenant.name,
        "contrato": contract.original_filename,
        "modo_analise": analysis.analysis_mode,
        "modelo_ia": analysis.model_used or "N/A",
        "data_analise": analysis.completed_at.strftime("%d/%m/%Y %H:%M") if analysis.completed_at else "N/A",
        "solicitante": user.full_name,
    }

    pdf_bytes = generator.generate_pdf(
        analysis_result=report_data,
        metadata=metadata,
    )

    # Audit
    await log_audit(
        db, action="export_report", user_id=str(user.id),
        tenant_id=str(user.tenant_id), resource_type="analysis",
        resource_id=str(analysis.id),
    )

    # Sanitizar nome do arquivo (prevenir header injection)
    import re
    safe_name = re.sub(r'[^\w\s\-\.]', '_', contract.original_filename)
    filename = f"relatorio_{analysis.analysis_mode}_{safe_name}.pdf"

    return StreamingResponse(
        io.BytesIO(pdf_bytes),
        media_type="application/pdf",
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"'
        },
    )
