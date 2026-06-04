"""
LegalShield AI 2026 — Contract Cache (multi-backend)

Armazena temporariamente os BYTES de um contrato enquanto ele aguarda ou está
sendo analisado. Três backends disponíveis, escolhidos via STORAGE_BACKEND:

    memory  → dict em processo (testes, sem Docker, sem serviços externos)
    redis   → Redis com TTL (docker-compose local, até ~100 simultâneos)
    r2      → Cloudflare R2 (produção, 10k+ usuários simultâneos)

Fluxo invariante em todos os backends:

    [Upload] ─> bytes guardados (TTL 30 min)
                        │
                        ▼
          [Worker pega bytes, analisa com IA]
                        │
                        ▼
       [Salva relatório completo no banco]
                        │
                        ▼
    [TTL expira ou discard manual] ─> bytes somem

Apenas o RELATÓRIO (achados, score, resumo, tokens, custo) é persistido no
banco. O PDF/DOCX/TXT original nunca fica em disco ou banco permanente.

Isolamento de sessões: cada contrato tem um UUID único (contract_id). Chaves
no Redis e objetos no R2 usam esse UUID — nenhum usuário acessa dados de outro.

Por que R2 em produção?
    Com STORAGE_BACKEND=redis, 10k uploads simultâneos de 5 MB cada ocupariam
    50 GB no Redis — impossível. Com R2, o Redis guarda apenas a referência
    (chave do objeto, ~100 bytes), e os bytes ficam no R2 (escala ilimitada,
    grátis até 10 GB/mês).

Configuração:
    STORAGE_BACKEND=memory   → sem Redis, sem R2 (testes rápidos)
    STORAGE_BACKEND=redis    → requer REDIS_URL
    STORAGE_BACKEND=r2       → requer R2_ACCOUNT_ID, R2_ACCESS_KEY_ID,
                                R2_SECRET_ACCESS_KEY, R2_BUCKET_NAME
                                (+ REDIS_URL para guardar referência c/ TTL)
"""

from __future__ import annotations

import asyncio
import logging
from functools import partial
from typing import Optional

import boto3
from botocore.exceptions import ClientError

from ..config import get_settings
from .redis_client import get_redis_client

logger = logging.getLogger(__name__)
settings = get_settings()

# Prefixos de chave Redis
_KEY_PREFIX_BYTES = "contract:bytes:"    # backend redis: bytes direto
_KEY_PREFIX_R2 = "contract:r2_key:"     # backend r2: referência ao objeto no R2

# Fallback em memória (STORAGE_BACKEND=memory ou dev sem Redis)
_inmemory_store: dict[str, bytes] = {}


def get_active_backend() -> str:
    """Resolve qual backend de storage usar efetivamente.

    Ordem de prioridade quando storage_backend='auto':
      1. 'r2'     — se R2_ACCOUNT_ID e R2_ACCESS_KEY_ID estiverem configurados
      2. 'redis'  — se o cliente Redis estiver conectado (pool inicializado)
      3. 'memory' — fallback silencioso (análise roda inline, sem fila)

    Quando storage_backend é 'redis', 'r2' ou 'memory', retorna diretamente.
    """
    configured = settings.storage_backend
    if configured != "auto":
        return configured

    # Auto-detecção — sem chamadas de rede, usa estado já estabelecido no startup
    if settings.r2_account_id and settings.r2_access_key_id:
        return "r2"

    from .redis_client import get_redis_client
    if get_redis_client() is not None:
        return "redis"

    return "memory"


# ---------------------------------------------------------------------------
# Helpers internos
# ---------------------------------------------------------------------------

def _redis_bytes_key(contract_id: str) -> str:
    return f"{_KEY_PREFIX_BYTES}{contract_id}"


def _redis_r2ref_key(contract_id: str) -> str:
    return f"{_KEY_PREFIX_R2}{contract_id}"


def _r2_object_key(contract_id: str) -> str:
    """Caminho do objeto dentro do bucket R2."""
    return f"contracts/{contract_id}/bytes"


def _get_r2_client():
    """Retorna cliente boto3 S3-compatível apontando para o R2."""
    endpoint = settings.r2_endpoint_url or (
        f"https://{settings.r2_account_id}.r2.cloudflarestorage.com"
    )
    return boto3.client(
        "s3",
        endpoint_url=endpoint,
        aws_access_key_id=settings.r2_access_key_id,
        aws_secret_access_key=settings.r2_secret_access_key,
        region_name="auto",
    )


async def _run_sync(fn, *args, **kwargs) -> any:
    """Executa chamada boto3 síncrona em thread pool para não bloquear o event loop."""
    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(None, partial(fn, *args, **kwargs))


# ---------------------------------------------------------------------------
# Backend: R2
# ---------------------------------------------------------------------------

async def _r2_store(contract_id: str, data: bytes, ttl: int) -> None:
    """Upload para R2 + referência no Redis com TTL."""
    obj_key = _r2_object_key(contract_id)

    def _upload():
        client = _get_r2_client()
        client.put_object(
            Bucket=settings.r2_bucket_name,
            Key=obj_key,
            Body=data,
            ContentType="application/octet-stream",
        )

    await _run_sync(_upload)
    logger.info(
        "contract_cache[r2]: %d bytes enviados para R2 bucket=%s key=%s",
        len(data),
        settings.r2_bucket_name,
        obj_key,
    )

    # Guarda referência no Redis com TTL para saber que o objeto existe
    redis = get_redis_client()
    if redis:
        await redis.set(_redis_r2ref_key(contract_id), obj_key.encode(), ex=ttl)
    else:
        # Se não há Redis, guarda na memória como fallback (dev)
        _inmemory_store[f"r2ref:{contract_id}"] = obj_key.encode()


async def _r2_fetch(contract_id: str) -> Optional[bytes]:
    """Baixa bytes do R2 se a referência ainda estiver viva no Redis."""
    redis = get_redis_client()
    if redis:
        ref = await redis.get(_redis_r2ref_key(contract_id))
    else:
        ref = _inmemory_store.get(f"r2ref:{contract_id}")

    if not ref:
        return None

    obj_key = ref.decode() if isinstance(ref, bytes) else ref

    def _download():
        client = _get_r2_client()
        try:
            resp = client.get_object(Bucket=settings.r2_bucket_name, Key=obj_key)
            return resp["Body"].read()
        except ClientError as e:
            if e.response["Error"]["Code"] in ("NoSuchKey", "404"):
                return None
            raise

    return await _run_sync(_download)


async def _r2_discard(contract_id: str) -> bool:
    """Apaga objeto no R2 e remove referência do Redis."""
    redis = get_redis_client()
    if redis:
        ref = await redis.get(_redis_r2ref_key(contract_id))
    else:
        ref = _inmemory_store.pop(f"r2ref:{contract_id}", None)

    if not ref:
        return False

    obj_key = ref.decode() if isinstance(ref, bytes) else ref

    def _delete():
        client = _get_r2_client()
        try:
            client.delete_object(Bucket=settings.r2_bucket_name, Key=obj_key)
            return True
        except ClientError:
            return False

    deleted = await _run_sync(_delete)
    if redis:
        await redis.delete(_redis_r2ref_key(contract_id))
    logger.info("contract_cache[r2]: objeto deletado contract_id=%s", contract_id)
    return deleted


async def _r2_ttl(contract_id: str) -> Optional[int]:
    redis = get_redis_client()
    if not redis:
        return -1 if f"r2ref:{contract_id}" in _inmemory_store else None
    ttl = await redis.ttl(_redis_r2ref_key(contract_id))
    return None if (ttl is None or ttl < 0) else int(ttl)


# ---------------------------------------------------------------------------
# API pública
# ---------------------------------------------------------------------------

async def store_contract_bytes(
    contract_id: str,
    data: bytes,
    ttl_seconds: Optional[int] = None,
) -> None:
    """Salva bytes do contrato no backend resolvido automaticamente.

    Args:
        contract_id: UUID do contrato (string).
        data: Bytes brutos do PDF/DOCX/TXT (já extraídos, não criptografados).
        ttl_seconds: Sobrescreve TTL padrão de settings.
    """
    ttl = ttl_seconds or settings.contract_cache_ttl_seconds
    backend = get_active_backend()

    if backend == "r2":
        await _r2_store(contract_id, data, ttl)
        return

    redis = get_redis_client()
    if backend == "redis" and redis is not None:
        await redis.set(_redis_bytes_key(contract_id), data, ex=ttl)
        logger.info(
            "contract_cache[redis]: %d bytes guardados (TTL=%ds) contract_id=%s",
            len(data),
            ttl,
            contract_id,
        )
        return

    # Fallback em memória (STORAGE_BACKEND=memory ou sem Redis)
    _inmemory_store[contract_id] = data
    logger.debug(
        "contract_cache[memory]: %d bytes guardados contract_id=%s",
        len(data),
        contract_id,
    )


async def fetch_contract_bytes(contract_id: str) -> Optional[bytes]:
    """Recupera bytes do contrato. Retorna None se expirou ou não existe."""
    backend = get_active_backend()

    if backend == "r2":
        return await _r2_fetch(contract_id)

    redis = get_redis_client()
    if backend == "redis" and redis is not None:
        return await redis.get(_redis_bytes_key(contract_id))

    return _inmemory_store.get(contract_id)


async def discard_contract_bytes(contract_id: str) -> bool:
    """Apaga bytes do contrato imediatamente. Idempotente — True se algo foi apagado."""
    backend = get_active_backend()

    if backend == "r2":
        return await _r2_discard(contract_id)

    redis = get_redis_client()
    if backend == "redis" and redis is not None:
        removed = await redis.delete(_redis_bytes_key(contract_id))
        if removed:
            logger.info("contract_cache[redis]: bytes descartados contract_id=%s", contract_id)
        return bool(removed)

    return _inmemory_store.pop(contract_id, None) is not None


async def get_ttl_seconds(contract_id: str) -> Optional[int]:
    """Retorna segundos restantes até os bytes sumirem. None = não há bytes."""
    backend = get_active_backend()

    if backend == "r2":
        return await _r2_ttl(contract_id)

    redis = get_redis_client()
    if backend == "redis" and redis is not None:
        ttl = await redis.ttl(_redis_bytes_key(contract_id))
        return None if (ttl is None or ttl < 0) else int(ttl)

    return None if contract_id not in _inmemory_store else -1
