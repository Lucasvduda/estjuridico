"""
LegalShield AI 2026 — Encryption (Projeto A SaaS)
Criptografia AES-256-GCM para arquivos em repouso com chaves por tenant.
"""

import base64
import logging
import os

from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.hkdf import HKDF
from cryptography.hazmat.primitives import hashes

from ..config import get_settings

logger = logging.getLogger(__name__)

settings = get_settings()


class EncryptionError(Exception):
    """Erro de criptografia."""
    pass


def _get_master_key() -> bytes:
    """Obtém a chave mestra de criptografia."""
    key_b64 = settings.encryption_master_key
    try:
        key = base64.b64decode(key_b64)
        if len(key) < 32:
            raise EncryptionError(
                "Chave mestra deve ter pelo menos 32 bytes. "
                "Gere com: python -c \"import os,base64; print(base64.b64encode(os.urandom(32)).decode())\""
            )
        return key[:32]
    except Exception as e:
        raise EncryptionError(f"Chave mestra inválida: {e}") from e


def derive_tenant_key(tenant_id: str) -> bytes:
    """
    Deriva uma chave única para cada tenant usando HKDF.
    Mesmo master key + tenant_id diferente = chave diferente.
    """
    master_key = _get_master_key()

    hkdf = HKDF(
        algorithm=hashes.SHA256(),
        length=32,  # 256 bits
        salt=b"legalshield-tenant-key-v1",
        info=tenant_id.encode("utf-8"),
    )
    return hkdf.derive(master_key)


def encrypt_file(file_bytes: bytes, tenant_id: str) -> bytes:
    """
    Criptografa arquivo usando AES-256-GCM com chave derivada do tenant.

    Args:
        file_bytes: Conteúdo original do arquivo.
        tenant_id: ID do tenant para derivação da chave.

    Returns:
        Bytes criptografados (nonce || ciphertext || tag).
    """
    try:
        key = derive_tenant_key(tenant_id)
        nonce = os.urandom(12)  # 96 bits para AES-GCM
        aesgcm = AESGCM(key)

        ciphertext = aesgcm.encrypt(nonce, file_bytes, None)

        # Formato: nonce (12 bytes) || ciphertext+tag
        encrypted = nonce + ciphertext

        logger.info(
            "Arquivo criptografado",
            extra={
                "tenant_id": tenant_id[:8] + "...",
                "original_size": len(file_bytes),
                "encrypted_size": len(encrypted),
            },
        )

        return encrypted

    except Exception as e:
        raise EncryptionError(f"Erro ao criptografar: {e}") from e


def decrypt_file(encrypted_bytes: bytes, tenant_id: str) -> bytes:
    """
    Descriptografa arquivo usando AES-256-GCM.

    Args:
        encrypted_bytes: Conteúdo criptografado.
        tenant_id: ID do tenant.

    Returns:
        Bytes originais do arquivo.
    """
    try:
        key = derive_tenant_key(tenant_id)

        # Extrair nonce (primeiros 12 bytes)
        nonce = encrypted_bytes[:12]
        ciphertext = encrypted_bytes[12:]

        aesgcm = AESGCM(key)
        plaintext = aesgcm.decrypt(nonce, ciphertext, None)

        return plaintext

    except Exception as e:
        raise EncryptionError(f"Erro ao descriptografar: {e}") from e


def generate_master_key() -> str:
    """Utilitário: gera nova chave mestra em Base64."""
    key = os.urandom(32)
    return base64.b64encode(key).decode("utf-8")
