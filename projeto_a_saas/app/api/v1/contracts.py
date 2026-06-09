"""
LegalShield AI 2026 — Contracts Router (Projeto A SaaS)

Upload, listagem e exclusão de contratos.

PRIVACIDADE / LGPD (importante):
Os BYTES do contrato NÃO ficam armazenados em disco nem em S3. Eles vivem
no Redis (via `contract_cache`) com TTL configurável (padrão 30 min) e são
apagados automaticamente. O que fica gravado de forma permanente é apenas
o RELATÓRIO (achados, score, resumo) — na tabela `analyses`.

Fluxo:
    1. POST /upload   -> bytes vão para o Redis; metadados (nome, hash, páginas)
                          vão para o Postgres. Retorna contract_id.
    2. POST /analyses -> enfileira análise. Worker pega os bytes do Redis, processa,
                          salva o relatório no banco.
    3. DELETE /{id}   -> apaga bytes do Redis (se ainda existirem) e a linha de
                          metadados do banco. Análises antigas (relatórios) são
                          mantidas porque são úteis para o histórico.
"""

import hashlib
import logging
import uuid as _uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from ...config import get_settings
from ...models import Analysis, Contract, User
from ...schemas import (
    ContractListResponse,
    ContractListItem,
    ContractUploadResponse,
    MessageResponse,
)
from ...services.contract_cache import (
    discard_contract_bytes,
    store_contract_bytes,
)
from ..deps import get_current_user, get_db, log_audit

logger = logging.getLogger(__name__)
settings = get_settings()
router = APIRouter()

ALLOWED_TYPES = {
    "application/pdf": "pdf",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document": "docx",
    "text/plain": "txt",
}


@router.post("/upload", response_model=ContractUploadResponse, status_code=201)
async def upload_contract(
    file: UploadFile = File(...),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Recebe o contrato, valida e guarda os bytes no Redis (TTL curto).

    NÃO grava em disco. Apenas metadados vão para o banco (filename, hash,
    tamanho, número estimado de páginas). Os bytes ficam disponíveis no Redis
    para que o worker possa pegá-los quando a análise for enfileirada.
    """

    content_type = file.content_type or ""
    file_type = ALLOWED_TYPES.get(content_type)
    if not file_type:
        raise HTTPException(
            status_code=400,
            detail=f"Tipo de arquivo não suportado: {content_type}. Use PDF, DOCX ou TXT.",
        )

    file_bytes = await file.read()
    file_size = len(file_bytes)

    # Validar magic bytes reais do arquivo (evitar Content-Type spoofing)
    try:
        import magic
        detected_mime = magic.from_buffer(file_bytes[:2048], mime=True)
        detected_type = ALLOWED_TYPES.get(detected_mime)
        if not detected_type:
            raise HTTPException(
                status_code=400,
                detail=f"Conteúdo real do arquivo ({detected_mime}) não corresponde a PDF, DOCX ou TXT.",
            )
        file_type = detected_type
    except ImportError:
        # python-magic não instalado — aceitar Content-Type header (dev local)
        pass

    max_size = settings.max_file_size_mb * 1024 * 1024
    if file_size > max_size:
        raise HTTPException(
            status_code=413,
            detail=f"Arquivo excede o limite de {settings.max_file_size_mb}MB",
        )

    sha256 = hashlib.sha256(file_bytes).hexdigest()
    contract_id = _uuid.uuid4()

    contract = Contract(
        id=contract_id,
        tenant_id=user.tenant_id,
        uploaded_by=user.id,
        original_filename=file.filename or "sem_nome",
        file_type=file_type,
        file_size_bytes=file_size,
        sha256_hash=sha256,
        status="uploaded",
    )
    db.add(contract)
    await db.flush()

    try:
        await store_contract_bytes(str(contract_id), file_bytes)
    except Exception as e:
        logger.error(
            "Falha ao guardar bytes no cache — abortando upload. "
            "Tipo: %s | Erro: %s | Backend: %s",
            type(e).__name__, e,
            settings.storage_backend if hasattr(settings, 'storage_backend') else 'unknown',
            exc_info=True,
        )
        raise HTTPException(
            status_code=503,
            detail=f"Cache temporário indisponível ({type(e).__name__}). Tente novamente em instantes.",
        )

    await log_audit(
        db,
        action="upload_contract",
        user_id=str(user.id),
        tenant_id=str(user.tenant_id),
        resource_type="contract",
        resource_id=str(contract.id),
        details={
            "filename": file.filename,
            "size": file_size,
            "sha256": sha256,
            "ttl_seconds": settings.contract_cache_ttl_seconds,
        },
    )

    return ContractUploadResponse(
        id=str(contract.id),
        filename=contract.original_filename,
        file_type=contract.file_type,
        file_size_bytes=contract.file_size_bytes,
        page_count=contract.page_count,
        ocr_used=contract.ocr_used,
        status=contract.status,
        created_at=contract.created_at,
    )


@router.get("/", response_model=ContractListResponse)
async def list_contracts(
    page: int = 1,
    per_page: int = 20,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Lista contratos do tenant com paginação."""
    offset = (page - 1) * per_page

    count_q = select(func.count()).select_from(Contract).where(
        Contract.tenant_id == user.tenant_id
    )
    total = (await db.execute(count_q)).scalar() or 0

    query = (
        select(Contract)
        .where(Contract.tenant_id == user.tenant_id)
        .order_by(Contract.created_at.desc())
        .offset(offset)
        .limit(per_page)
    )
    result = await db.execute(query)
    contracts = result.scalars().all()

    items = []
    for c in contracts:
        ac = await db.execute(
            select(func.count()).select_from(Analysis)
            .where(Analysis.contract_id == c.id)
        )
        analysis_count = ac.scalar() or 0

        items.append(ContractListItem(
            id=str(c.id),
            filename=c.original_filename,
            file_type=c.file_type,
            file_size_bytes=c.file_size_bytes,
            status=c.status,
            created_at=c.created_at,
            analysis_count=analysis_count,
        ))

    return ContractListResponse(
        contracts=items, total=total, page=page, per_page=per_page,
    )


@router.delete("/{contract_id}", response_model=MessageResponse)
async def delete_contract(
    contract_id: str,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Apaga bytes do Redis e metadados do banco.

    Os relatórios (Analysis) gerados a partir do contrato são preservados,
    porque pertencem ao histórico do tenant. Cascade está configurado em
    `Tenant.contracts = relationship(..., cascade="all, delete-orphan")` para
    casos extremos de exclusão de tenant.
    """
    try:
        _uuid.UUID(contract_id)
    except (ValueError, AttributeError):
        raise HTTPException(status_code=404, detail="Contrato não encontrado")

    result = await db.execute(
        select(Contract).where(
            Contract.id == contract_id,
            Contract.tenant_id == user.tenant_id,
        )
    )
    contract = result.scalar_one_or_none()
    if not contract:
        raise HTTPException(status_code=404, detail="Contrato não encontrado")

    discarded = await discard_contract_bytes(contract_id)
    if discarded and contract.bytes_discarded_at is None:
        contract.bytes_discarded_at = datetime.now(timezone.utc)
        contract.status = "discarded"

    await db.delete(contract)

    await log_audit(
        db,
        action="delete_contract",
        user_id=str(user.id),
        tenant_id=str(user.tenant_id),
        resource_type="contract",
        resource_id=contract_id,
        details={"bytes_were_in_cache": discarded},
    )

    return MessageResponse(message="Contrato excluído com sucesso")
