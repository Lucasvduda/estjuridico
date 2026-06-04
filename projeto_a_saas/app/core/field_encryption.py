"""
LegalShield AI 2026 — Encryption Helpers para Campos Sensíveis

Funções utilitárias para criptografar/descriptografar campos individuais
(MFA secrets, API keys, etc.) usando AES-256-GCM com a chave mestra.

Diferente de encrypt_file/decrypt_file (que derivam chave por tenant),
essas funções usam a chave mestra diretamente para dados do SISTEMA
(não vinculados a um tenant específico).
"""

import base64
import logging
import os

from cryptography.hazmat.primitives.ciphers.aead import AESGCM

from ..config import get_settings

logger = logging.getLogger(__name__)


class FieldEncryptionError(Exception):
    """Erro de criptografia de campo."""
    pass


def _get_field_key() -> bytes:
    """Obtém a chave mestra para criptografia de campos."""
    settings = get_settings()
    key_b64 = settings.encryption_master_key
    try:
        key = base64.b64decode(key_b64)
        if len(key) < 32:
            raise FieldEncryptionError("Chave mestra inválida para criptografia de campos")
        return key[:32]
    except Exception as e:
        raise FieldEncryptionError(f"Chave mestra inválida: {e}") from e


def encrypt_field(plaintext: str) -> str:
    """
    Criptografa um campo de texto e retorna como base64.

    Args:
        plaintext: Texto a criptografar.

    Returns:
        String base64 contendo nonce + ciphertext (seguro para armazenar em VARCHAR).
    """
    if not plaintext:
        return ""

    try:
        key = _get_field_key()
        nonce = os.urandom(12)
        aesgcm = AESGCM(key)
        ciphertext = aesgcm.encrypt(nonce, plaintext.encode("utf-8"), None)
        # Formato: base64(nonce || ciphertext+tag)
        return base64.b64encode(nonce + ciphertext).decode("utf-8")
    except FieldEncryptionError:
        raise
    except Exception as e:
        raise FieldEncryptionError(f"Erro ao criptografar campo: {e}") from e


def decrypt_field(encrypted_b64: str) -> str:
    """
    Descriptografa um campo criptografado.

    Args:
        encrypted_b64: String base64 com nonce + ciphertext.

    Returns:
        Texto original descriptografado.
    """
    if not encrypted_b64:
        return ""

    try:
        key = _get_field_key()
        raw = base64.b64decode(encrypted_b64)
        nonce = raw[:12]
        ciphertext = raw[12:]
        aesgcm = AESGCM(key)
        plaintext = aesgcm.decrypt(nonce, ciphertext, None)
        return plaintext.decode("utf-8")
    except FieldEncryptionError:
        raise
    except Exception as e:
        # Se falhar a descriptografia, pode ser um valor antigo em texto puro
        # (migração gradual). Logar e retornar o valor original.
        logger.warning(
            "Falha ao descriptografar campo — pode ser valor legado em texto puro: %s",
            str(e)[:100],
        )
        return encrypted_b64


def encrypt_json_field(data: list | dict | None) -> str | None:
    """Criptografa dados JSON (listas, dicts) para armazenamento."""
    if data is None:
        return None
    import json
    return encrypt_field(json.dumps(data))


def decrypt_json_field(encrypted_b64: str | None) -> list | dict | None:
    """Descriptografa dados JSON criptografados."""
    if not encrypted_b64:
        return None
    import json
    decrypted = decrypt_field(encrypted_b64)
    try:
        return json.loads(decrypted)
    except (json.JSONDecodeError, TypeError):
        # Pode ser valor legado não criptografado
        return None
