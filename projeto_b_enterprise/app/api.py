"""
LegalShield AI 2026 — API Router (Projeto B Enterprise)
Endpoints: contratos, análise, BYOK settings, relatórios.
Tudo em um único router (standalone, sem multi-tenancy).
"""

import hashlib
import io
import json
import logging
import os
import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, File, HTTPException, UploadFile
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from typing import Optional

from .config import get_enterprise_settings
from .database import get_connection

logger = logging.getLogger(__name__)
settings = get_enterprise_settings()
router = APIRouter()


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------

class ContractResponse(BaseModel):
    id: str
    filename: str
    file_type: str
    file_size_bytes: int
    status: str
    created_at: str


class AnalysisRequest(BaseModel):
    contract_id: str
    mode: str = Field(pattern="^(defensive|offensive|audit|shield)$")


class AnalysisResponse(BaseModel):
    id: str
    contract_id: str
    mode: str
    status: str
    resumo_executivo: str = ""
    score_risco: int = 0
    achados: list = []
    total_achados: int = 0
    model_used: str = ""
    tokens_used: int = 0
    cost_usd: float = 0.0
    created_at: str
    completed_at: Optional[str] = None


class BYOKSettingsRequest(BaseModel):
    openai_api_key: Optional[str] = None
    anthropic_api_key: Optional[str] = None
    primary_model: Optional[str] = None
    fallback_model: Optional[str] = None
    temperature: Optional[float] = None


class BYOKSettingsResponse(BaseModel):
    openai_configured: bool
    anthropic_configured: bool
    primary_model: str
    fallback_model: str
    temperature: float


ALLOWED_TYPES = {
    "application/pdf": "pdf",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document": "docx",
    "text/plain": "txt",
}


# ---------------------------------------------------------------------------
# Contracts
# ---------------------------------------------------------------------------

@router.post("/contracts/upload", response_model=ContractResponse, status_code=201)
async def upload_contract(file: UploadFile = File(...)):
    """Upload de contrato."""
    content_type = file.content_type or ""
    file_type = ALLOWED_TYPES.get(content_type)
    if not file_type:
        raise HTTPException(status_code=400, detail=f"Tipo não suportado: {content_type}")

    file_bytes = await file.read()
    file_size = len(file_bytes)

    max_size = settings.max_file_size_mb * 1024 * 1024
    if file_size > max_size:
        raise HTTPException(status_code=413, detail=f"Arquivo excede {settings.max_file_size_mb}MB")

    contract_id = str(uuid.uuid4())
    sha256 = hashlib.sha256(file_bytes).hexdigest()
    stored_name = f"{contract_id}.{file_type}"

    os.makedirs(settings.upload_dir, exist_ok=True)
    stored_path = os.path.join(settings.upload_dir, stored_name)
    with open(stored_path, "wb") as f:
        f.write(file_bytes)

    now = datetime.now(timezone.utc).isoformat()
    conn = get_connection()
    conn.execute(
        """INSERT INTO contracts (id, filename, file_type, file_size_bytes,
           sha256_hash, stored_path, created_at)
           VALUES (?, ?, ?, ?, ?, ?, ?)""",
        (contract_id, file.filename, file_type, file_size, sha256, stored_path, now),
    )
    conn.commit()
    conn.close()

    return ContractResponse(
        id=contract_id, filename=file.filename or "sem_nome",
        file_type=file_type, file_size_bytes=file_size,
        status="uploaded", created_at=now,
    )


@router.get("/contracts", response_model=list[ContractResponse])
async def list_contracts():
    """Lista todos os contratos."""
    conn = get_connection()
    rows = conn.execute(
        "SELECT id, filename, file_type, file_size_bytes, status, created_at FROM contracts ORDER BY created_at DESC"
    ).fetchall()
    conn.close()

    return [
        ContractResponse(
            id=r["id"], filename=r["filename"], file_type=r["file_type"],
            file_size_bytes=r["file_size_bytes"], status=r["status"],
            created_at=r["created_at"],
        ) for r in rows
    ]


@router.delete("/contracts/{contract_id}")
async def delete_contract(contract_id: str):
    """Exclui contrato e arquivo."""
    conn = get_connection()
    row = conn.execute("SELECT stored_path FROM contracts WHERE id = ?", (contract_id,)).fetchone()
    if not row:
        conn.close()
        raise HTTPException(status_code=404, detail="Contrato não encontrado")

    if os.path.exists(row["stored_path"]):
        os.remove(row["stored_path"])

    conn.execute("DELETE FROM contracts WHERE id = ?", (contract_id,))
    conn.commit()
    conn.close()
    return {"message": "Contrato excluído"}


# ---------------------------------------------------------------------------
# Analysis
# ---------------------------------------------------------------------------

@router.post("/analysis", response_model=AnalysisResponse, status_code=201)
async def create_analysis(body: AnalysisRequest):
    """Cria análise jurídica (4 modos)."""
    conn = get_connection()
    contract_row = conn.execute(
        "SELECT * FROM contracts WHERE id = ?", (body.contract_id,)
    ).fetchone()

    if not contract_row:
        conn.close()
        raise HTTPException(status_code=404, detail="Contrato não encontrado")

    # Ler arquivo
    with open(contract_row["stored_path"], "rb") as f:
        file_bytes = f.read()

    # Executar análise
    from .services.analysis_engine import AnalysisEngine
    from .services.prompt_templates import AnalysisMode

    mode_map = {
        "defensive": AnalysisMode.DEFENSIVE,
        "offensive": AnalysisMode.OFFENSIVE,
        "audit": AnalysisMode.AUDIT,
        "shield": AnalysisMode.SHIELD,
    }

    engine = AnalysisEngine(
        openai_api_key=settings.openai_api_key,
        anthropic_api_key=settings.anthropic_api_key,
    )

    analysis_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc).isoformat()

    try:
        result = engine.analyze(
            file_bytes=file_bytes,
            filename=contract_row["filename"],
            mode=mode_map[body.mode],
        )
        completed_at = datetime.now(timezone.utc).isoformat()

        conn.execute(
            """INSERT INTO analyses
               (id, contract_id, analysis_mode, status, results_json,
                resumo_executivo, score_risco, total_achados, model_used,
                tokens_used, cost_usd, latency_seconds, injection_detected,
                created_at, completed_at)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (
                analysis_id, body.contract_id, body.mode, "completed",
                json.dumps(result.get("achados", []), ensure_ascii=False),
                result.get("resumo_executivo", ""),
                result.get("score_risco", 0),
                len(result.get("achados", [])),
                result.get("model_used", ""),
                result.get("tokens_used", 0),
                result.get("cost_usd", 0.0),
                result.get("latency_seconds", 0.0),
                1 if result.get("injection_detected") else 0,
                now, completed_at,
            ),
        )

        # Atualizar status do contrato
        conn.execute("UPDATE contracts SET status = 'analyzed' WHERE id = ?", (body.contract_id,))
        conn.commit()
        conn.close()

        return AnalysisResponse(
            id=analysis_id, contract_id=body.contract_id,
            mode=body.mode, status="completed",
            resumo_executivo=result.get("resumo_executivo", ""),
            score_risco=result.get("score_risco", 0),
            achados=result.get("achados", []),
            total_achados=len(result.get("achados", [])),
            model_used=result.get("model_used", ""),
            tokens_used=result.get("tokens_used", 0),
            cost_usd=result.get("cost_usd", 0.0),
            created_at=now, completed_at=completed_at,
        )

    except Exception as e:
        conn.execute(
            "INSERT INTO analyses (id, contract_id, analysis_mode, status, created_at) VALUES (?,?,?,?,?)",
            (analysis_id, body.contract_id, body.mode, "failed", now),
        )
        conn.commit()
        conn.close()
        raise HTTPException(status_code=500, detail=f"Erro na análise: {str(e)}")


@router.get("/analysis", response_model=list[AnalysisResponse])
async def list_analyses(contract_id: str = None):
    """Lista análises realizadas."""
    conn = get_connection()
    if contract_id:
        rows = conn.execute(
            "SELECT * FROM analyses WHERE contract_id = ? ORDER BY created_at DESC",
            (contract_id,),
        ).fetchall()
    else:
        rows = conn.execute("SELECT * FROM analyses ORDER BY created_at DESC").fetchall()
    conn.close()

    return [
        AnalysisResponse(
            id=r["id"], contract_id=r["contract_id"],
            mode=r["analysis_mode"], status=r["status"],
            resumo_executivo=r["resumo_executivo"] or "",
            score_risco=r["score_risco"] or 0,
            achados=json.loads(r["results_json"]) if r["results_json"] else [],
            total_achados=r["total_achados"] or 0,
            model_used=r["model_used"] or "",
            tokens_used=r["tokens_used"] or 0,
            cost_usd=r["cost_usd"] or 0.0,
            created_at=r["created_at"],
            completed_at=r["completed_at"],
        ) for r in rows
    ]


@router.get("/analysis/{analysis_id}", response_model=AnalysisResponse)
async def get_analysis(analysis_id: str):
    """Obtém análise por ID."""
    conn = get_connection()
    r = conn.execute("SELECT * FROM analyses WHERE id = ?", (analysis_id,)).fetchone()
    conn.close()

    if not r:
        raise HTTPException(status_code=404, detail="Análise não encontrada")

    return AnalysisResponse(
        id=r["id"], contract_id=r["contract_id"],
        mode=r["analysis_mode"], status=r["status"],
        resumo_executivo=r["resumo_executivo"] or "",
        score_risco=r["score_risco"] or 0,
        achados=json.loads(r["results_json"]) if r["results_json"] else [],
        total_achados=r["total_achados"] or 0,
        model_used=r["model_used"] or "",
        tokens_used=r["tokens_used"] or 0,
        cost_usd=r["cost_usd"] or 0.0,
        created_at=r["created_at"],
        completed_at=r["completed_at"],
    )


# ---------------------------------------------------------------------------
# Reports
# ---------------------------------------------------------------------------

@router.post("/reports/export/{analysis_id}")
async def export_report(analysis_id: str):
    """Exporta relatório PDF de uma análise."""
    conn = get_connection()
    analysis_row = conn.execute("SELECT * FROM analyses WHERE id = ?", (analysis_id,)).fetchone()
    if not analysis_row:
        conn.close()
        raise HTTPException(status_code=404, detail="Análise não encontrada")

    if analysis_row["status"] != "completed":
        conn.close()
        raise HTTPException(status_code=400, detail="Análise não concluída")

    contract_row = conn.execute(
        "SELECT filename FROM contracts WHERE id = ?", (analysis_row["contract_id"],)
    ).fetchone()
    conn.close()

    from .services.report_generator import ReportGenerator

    generator = ReportGenerator()
    report_data = {
        "resumo_executivo": analysis_row["resumo_executivo"] or "",
        "score_risco": analysis_row["score_risco"] or 0,
        "achados": json.loads(analysis_row["results_json"]) if analysis_row["results_json"] else [],
        "modo": analysis_row["analysis_mode"],
    }

    metadata = {
        "contrato": contract_row["filename"] if contract_row else "N/A",
        "modo_analise": analysis_row["analysis_mode"],
        "modelo_ia": analysis_row["model_used"] or "N/A",
        "data_analise": analysis_row["completed_at"] or "N/A",
    }

    pdf_bytes = generator.generate_pdf(analysis_result=report_data, metadata=metadata)
    filename = f"relatorio_{analysis_row['analysis_mode']}_{analysis_id[:8]}.pdf"

    return StreamingResponse(
        io.BytesIO(pdf_bytes),
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


# ---------------------------------------------------------------------------
# BYOK Settings
# ---------------------------------------------------------------------------

@router.get("/settings/byok", response_model=BYOKSettingsResponse)
async def get_byok_settings():
    """Retorna configurações de API keys (sem expor as chaves)."""
    return BYOKSettingsResponse(
        openai_configured=bool(settings.openai_api_key),
        anthropic_configured=bool(settings.anthropic_api_key),
        primary_model=settings.llm_primary_model,
        fallback_model=settings.llm_fallback_model,
        temperature=settings.llm_temperature,
    )


@router.put("/settings/byok", response_model=BYOKSettingsResponse)
async def update_byok_settings(body: BYOKSettingsRequest):
    """Atualiza configurações BYOK (persistidas no banco)."""
    conn = get_connection()
    now = datetime.now(timezone.utc).isoformat()

    if body.openai_api_key is not None:
        settings.openai_api_key = body.openai_api_key
        conn.execute(
            "INSERT OR REPLACE INTO settings (key, value, updated_at) VALUES (?,?,?)",
            ("openai_api_key", body.openai_api_key, now),
        )
    if body.anthropic_api_key is not None:
        settings.anthropic_api_key = body.anthropic_api_key
        conn.execute(
            "INSERT OR REPLACE INTO settings (key, value, updated_at) VALUES (?,?,?)",
            ("anthropic_api_key", body.anthropic_api_key, now),
        )
    if body.primary_model is not None:
        settings.llm_primary_model = body.primary_model
    if body.fallback_model is not None:
        settings.llm_fallback_model = body.fallback_model
    if body.temperature is not None:
        settings.llm_temperature = body.temperature

    conn.commit()
    conn.close()

    return BYOKSettingsResponse(
        openai_configured=bool(settings.openai_api_key),
        anthropic_configured=bool(settings.anthropic_api_key),
        primary_model=settings.llm_primary_model,
        fallback_model=settings.llm_fallback_model,
        temperature=settings.llm_temperature,
    )
