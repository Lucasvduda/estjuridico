"""
LegalShield AI 2026 — Steganography Engine (Projeto B Enterprise)
Sistema de esteganografia digital para marca d'água anti-pirataria.
100% offline. Nenhuma comunicação externa.

Injeta IDs criptografados em 5 locais não-óbvios para rastreamento
do comprador original em caso de vazamento/revenda.
"""

import base64
import hashlib
import json
import logging
import os
import re
import sqlite3
import struct
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from pydantic import BaseModel

logger = logging.getLogger(__name__)

# Chave de criptografia para os fingerprints (derivada, não é a master key)
_STEGO_KEY_SEED = b"legalshield-stego-v1-2026-fingerprint-key"


class FingerprintData(BaseModel):
    """Dados do fingerprint de rastreamento."""
    fingerprint_id: str  # Ex: "CLIENTE_X_2026_42"
    customer_name: str
    contract_id: str
    sale_date: str
    version: str = "1.0"


class ExtractionResult(BaseModel):
    """Resultado da extração forense de fingerprints."""
    location: str
    found: bool
    fingerprint_id: Optional[str] = None
    raw_data: Optional[str] = None
    error: Optional[str] = None


class ForensicReport(BaseModel):
    """Relatório forense completo."""
    scan_date: str
    source_path: str
    results: list[ExtractionResult]
    confirmed_fingerprint: Optional[str] = None
    confidence: str = ""  # "5/5", "4/5", etc.
    customer_name: Optional[str] = None
    contract_id: Optional[str] = None


# ---------------------------------------------------------------------------
# Criptografia interna do fingerprint
# ---------------------------------------------------------------------------

def _derive_stego_key() -> bytes:
    """Deriva chave AES-256 para criptografia dos fingerprints."""
    return hashlib.sha256(_STEGO_KEY_SEED).digest()


def _encrypt_fingerprint(data: str) -> str:
    """Criptografa dados do fingerprint em base64."""
    key = _derive_stego_key()
    nonce = os.urandom(12)
    aesgcm = AESGCM(key)
    ciphertext = aesgcm.encrypt(nonce, data.encode("utf-8"), None)
    return base64.b64encode(nonce + ciphertext).decode("ascii")


def _decrypt_fingerprint(encrypted_b64: str) -> Optional[str]:
    """Descriptografa dados do fingerprint."""
    try:
        key = _derive_stego_key()
        raw = base64.b64decode(encrypted_b64)
        nonce = raw[:12]
        ciphertext = raw[12:]
        aesgcm = AESGCM(key)
        plaintext = aesgcm.decrypt(nonce, ciphertext, None)
        return plaintext.decode("utf-8")
    except Exception:
        return None


# ---------------------------------------------------------------------------
# MÉTODO 1: Tabela oculta no SQLite
# ---------------------------------------------------------------------------

def inject_sqlite_fingerprint(db_path: str, fingerprint: FingerprintData) -> bool:
    """
    Injeta fingerprint em tabela disfarçada de dados internos do sistema.
    Tabela: _sys_calibration (parece dados de calibração interna)
    """
    try:
        encrypted = _encrypt_fingerprint(fingerprint.model_dump_json())
        os.makedirs(os.path.dirname(db_path), exist_ok=True)
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()

        # Criar tabela que parece ser de dados internos do sistema
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS _sys_calibration (
                param_id INTEGER PRIMARY KEY,
                module_name TEXT NOT NULL,
                gc_threshold_vector TEXT NOT NULL,
                calibrated_at TEXT NOT NULL,
                checksum TEXT NOT NULL
            )
        """)

        # Inserir fingerprint disfarçado
        checksum = hashlib.md5(encrypted.encode()).hexdigest()[:8]
        cursor.execute("""
            INSERT OR REPLACE INTO _sys_calibration
            (param_id, module_name, gc_threshold_vector, calibrated_at, checksum)
            VALUES (?, ?, ?, ?, ?)
        """, (
            1,
            "analysis_engine.precision_matrix",
            encrypted,
            datetime.now(timezone.utc).isoformat(),
            checksum,
        ))

        conn.commit()
        conn.close()
        logger.info("Fingerprint injetado no SQLite")
        return True

    except Exception as e:
        logger.error("Falha ao injetar fingerprint no SQLite: %s", str(e))
        return False


def extract_sqlite_fingerprint(db_path: str) -> ExtractionResult:
    """Extrai fingerprint da tabela oculta do SQLite."""
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        cursor.execute(
            "SELECT gc_threshold_vector FROM _sys_calibration WHERE param_id = 1"
        )
        row = cursor.fetchone()
        conn.close()

        if not row:
            return ExtractionResult(location="SQLite DB", found=False)

        decrypted = _decrypt_fingerprint(row[0])
        if decrypted:
            data = FingerprintData.model_validate_json(decrypted)
            return ExtractionResult(
                location="SQLite DB (_sys_calibration)",
                found=True,
                fingerprint_id=data.fingerprint_id,
                raw_data=decrypted,
            )

        return ExtractionResult(
            location="SQLite DB", found=False, error="Dados corrompidos"
        )

    except Exception as e:
        return ExtractionResult(location="SQLite DB", found=False, error=str(e))


# ---------------------------------------------------------------------------
# MÉTODO 2: Espaços em branco invisíveis (Zero-Width Characters)
# ---------------------------------------------------------------------------

# Caracteres zero-width usados para codificação
_ZWC_ZERO = "\u200b"   # Zero Width Space     → bit 0
_ZWC_ONE = "\u200c"    # Zero Width Non-Joiner → bit 1
_ZWC_SEP = "\u200d"    # Zero Width Joiner     → separador
_ZWC_END = "\ufeff"    # BOM / Zero Width No-Break Space → fim


def _encode_zwc(text: str) -> str:
    """Codifica texto em caracteres zero-width invisíveis."""
    bits = ""
    for byte in text.encode("utf-8"):
        bits += format(byte, "08b")

    encoded = ""
    for bit in bits:
        encoded += _ZWC_ONE if bit == "1" else _ZWC_ZERO

    return encoded + _ZWC_END


def _decode_zwc(hidden: str) -> Optional[str]:
    """Decodifica caracteres zero-width de volta para texto."""
    try:
        # Extrair apenas os caracteres ZWC
        zwc_chars = "".join(
            c for c in hidden if c in (_ZWC_ZERO, _ZWC_ONE, _ZWC_END)
        )

        # Remover marcador de fim
        zwc_chars = zwc_chars.rstrip(_ZWC_END)

        if not zwc_chars:
            return None

        # Converter bits para bytes
        bits = ""
        for c in zwc_chars:
            if c == _ZWC_ONE:
                bits += "1"
            elif c == _ZWC_ZERO:
                bits += "0"

        # Converter bits para bytes
        byte_list = []
        for i in range(0, len(bits), 8):
            byte_chunk = bits[i : i + 8]
            if len(byte_chunk) == 8:
                byte_list.append(int(byte_chunk, 2))

        return bytes(byte_list).decode("utf-8")

    except Exception:
        return None


def inject_config_fingerprint(config_path: str, fingerprint: FingerprintData) -> bool:
    """
    Injeta fingerprint como caracteres zero-width invisíveis em arquivo YAML/config.
    O fingerprint fica entre linhas normais de configuração — invisível a olho nu.
    """
    try:
        encrypted = _encrypt_fingerprint(fingerprint.model_dump_json())
        zwc_encoded = _encode_zwc(encrypted)
        os.makedirs(os.path.dirname(config_path), exist_ok=True)

        # Ler config existente ou criar uma
        if os.path.exists(config_path):
            with open(config_path, "r", encoding="utf-8") as f:
                content = f.read()
        else:
            content = "# LegalShield AI Configuration\n# Auto-generated - do not modify\n"

        # Inserir ZWC entre as primeiras linhas
        lines = content.split("\n")
        if len(lines) >= 2:
            # Inserir após a segunda linha (invisível)
            lines.insert(2, zwc_encoded)
        else:
            lines.append(zwc_encoded)

        with open(config_path, "w", encoding="utf-8") as f:
            f.write("\n".join(lines))

        logger.info("Fingerprint injetado no config (zero-width chars)")
        return True

    except Exception as e:
        logger.error("Falha ao injetar fingerprint no config: %s", str(e))
        return False


def extract_config_fingerprint(config_path: str) -> ExtractionResult:
    """Extrai fingerprint dos caracteres zero-width do arquivo de config."""
    try:
        with open(config_path, "r", encoding="utf-8") as f:
            content = f.read()

        # Procurar caracteres ZWC no conteúdo
        zwc_pattern = f"[{_ZWC_ZERO}{_ZWC_ONE}{_ZWC_END}]+"
        matches = re.findall(zwc_pattern, content)

        if not matches:
            return ExtractionResult(location="Config YAML", found=False)

        # Tentar decodificar cada match
        for match in matches:
            decoded = _decode_zwc(match)
            if decoded:
                decrypted = _decrypt_fingerprint(decoded)
                if decrypted:
                    data = FingerprintData.model_validate_json(decrypted)
                    return ExtractionResult(
                        location="Config YAML (zero-width chars)",
                        found=True,
                        fingerprint_id=data.fingerprint_id,
                        raw_data=decrypted,
                    )

        return ExtractionResult(
            location="Config YAML", found=False, error="ZWC encontrados mas não decodificáveis"
        )

    except Exception as e:
        return ExtractionResult(location="Config YAML", found=False, error=str(e))


# ---------------------------------------------------------------------------
# MÉTODO 3: Comentários SQL nas migrations
# ---------------------------------------------------------------------------

def inject_sql_comment_fingerprint(
    migrations_dir: str, fingerprint: FingerprintData
) -> bool:
    """
    Injeta fingerprint como comentário SQL que parece ser um hash de versão.
    Ex: -- migration_checksum: a3f8c9d2e1... (na verdade é o fingerprint criptografado)
    """
    try:
        encrypted = _encrypt_fingerprint(fingerprint.model_dump_json())

        migration_file = os.path.join(migrations_dir, "001_initial_schema.sql")
        os.makedirs(migrations_dir, exist_ok=True)

        content = f"""-- LegalShield AI Enterprise - Initial Schema
-- Generated: {datetime.now(timezone.utc).isoformat()}
-- migration_checksum: {encrypted}
-- DO NOT MODIFY: This hash is used for schema integrity validation

CREATE TABLE IF NOT EXISTS contracts (
    id TEXT PRIMARY KEY,
    filename TEXT NOT NULL,
    created_at TEXT NOT NULL
);
"""

        with open(migration_file, "w", encoding="utf-8") as f:
            f.write(content)

        logger.info("Fingerprint injetado em comentário SQL")
        return True

    except Exception as e:
        logger.error("Falha ao injetar fingerprint no SQL: %s", str(e))
        return False


def extract_sql_comment_fingerprint(migrations_dir: str) -> ExtractionResult:
    """Extrai fingerprint dos comentários SQL das migrations."""
    try:
        migration_file = os.path.join(migrations_dir, "001_initial_schema.sql")

        if not os.path.exists(migration_file):
            return ExtractionResult(location="SQL Comments", found=False)

        with open(migration_file, "r", encoding="utf-8") as f:
            content = f.read()

        # Procurar o comentário de checksum
        match = re.search(r"-- migration_checksum: (.+)", content)
        if not match:
            return ExtractionResult(location="SQL Comments", found=False)

        encrypted = match.group(1).strip()
        decrypted = _decrypt_fingerprint(encrypted)

        if decrypted:
            data = FingerprintData.model_validate_json(decrypted)
            return ExtractionResult(
                location="SQL Comments (migration_checksum)",
                found=True,
                fingerprint_id=data.fingerprint_id,
                raw_data=decrypted,
            )

        return ExtractionResult(
            location="SQL Comments", found=False, error="Hash corrompido"
        )

    except Exception as e:
        return ExtractionResult(location="SQL Comments", found=False, error=str(e))


# ---------------------------------------------------------------------------
# MÉTODO 4: Metadados EXIF em imagens estáticas
# ---------------------------------------------------------------------------

def inject_exif_fingerprint(image_path: str, fingerprint: FingerprintData) -> bool:
    """
    Injeta fingerprint nos metadados EXIF/XMP de uma imagem PNG.
    Usa chunk tEXt do PNG para armazenar dados disfarçados.
    """
    try:
        from PIL import Image
        from PIL.PngImagePlugin import PngInfo

        encrypted = _encrypt_fingerprint(fingerprint.model_dump_json())
        os.makedirs(os.path.dirname(image_path), exist_ok=True)

        # Criar ou abrir imagem
        if os.path.exists(image_path):
            img = Image.open(image_path)
        else:
            # Criar um ícone 1x1 transparente se não existir
            img = Image.new("RGBA", (16, 16), (0, 0, 0, 0))

        # Adicionar metadados PNG
        metadata = PngInfo()
        metadata.add_text("Software", "LegalShield AI v1.0")
        metadata.add_text("icc_profile_hash", encrypted)  # Disfarçado como hash ICC
        metadata.add_text("Creation Time", datetime.now(timezone.utc).isoformat())

        img.save(image_path, "PNG", pnginfo=metadata)

        logger.info("Fingerprint injetado em metadados EXIF")
        return True

    except Exception as e:
        logger.error("Falha ao injetar fingerprint EXIF: %s", str(e))
        return False


def extract_exif_fingerprint(image_path: str) -> ExtractionResult:
    """Extrai fingerprint dos metadados EXIF de uma imagem."""
    try:
        from PIL import Image

        if not os.path.exists(image_path):
            return ExtractionResult(location="EXIF Metadata", found=False)

        img = Image.open(image_path)
        metadata = img.info

        icc_hash = metadata.get("icc_profile_hash")
        if not icc_hash:
            return ExtractionResult(location="EXIF Metadata", found=False)

        decrypted = _decrypt_fingerprint(icc_hash)
        if decrypted:
            data = FingerprintData.model_validate_json(decrypted)
            return ExtractionResult(
                location="EXIF Metadata (icc_profile_hash)",
                found=True,
                fingerprint_id=data.fingerprint_id,
                raw_data=decrypted,
            )

        return ExtractionResult(
            location="EXIF Metadata", found=False, error="Dados corrompidos"
        )

    except Exception as e:
        return ExtractionResult(location="EXIF Metadata", found=False, error=str(e))


# ---------------------------------------------------------------------------
# MÉTODO 5: Constantes Python ofuscadas
# ---------------------------------------------------------------------------

def inject_python_constants_fingerprint(
    target_file: str, fingerprint: FingerprintData
) -> bool:
    """
    Injeta fingerprint fragmentado em constantes Python que parecem
    dados de calibração do sistema.
    """
    try:
        encrypted = _encrypt_fingerprint(fingerprint.model_dump_json())

        # Fragmentar o encrypted em 4 partes
        chunk_size = len(encrypted) // 4
        chunks = [
            encrypted[: chunk_size],
            encrypted[chunk_size : chunk_size * 2],
            encrypted[chunk_size * 2 : chunk_size * 3],
            encrypted[chunk_size * 3 :],
        ]

        code = f'''"""
Constantes de calibração do motor de análise.
NÃO MODIFIQUE — estes valores afetam a precisão da IA.
Gerado automaticamente durante a compilação.
"""

# Vetores de calibração do tokenizer (pré-calculados)
_TOKENIZER_BIAS_VECTOR_A = "{chunks[0]}"
_TOKENIZER_BIAS_VECTOR_B = "{chunks[1]}"

# Constantes de normalização do embedding space
_EMBEDDING_NORM_FACTOR_X = "{chunks[2]}"
_EMBEDDING_NORM_FACTOR_Y = "{chunks[3]}"

# Número de fragmentos para reconstrução
_CALIBRATION_FRAGMENTS = 4
_CALIBRATION_VERSION = "1.0"


def get_calibration_checksum() -> str:
    """Retorna checksum de integridade dos dados de calibração."""
    import hashlib
    combined = (
        _TOKENIZER_BIAS_VECTOR_A
        + _TOKENIZER_BIAS_VECTOR_B
        + _EMBEDDING_NORM_FACTOR_X
        + _EMBEDDING_NORM_FACTOR_Y
    )
    return hashlib.md5(combined.encode()).hexdigest()
'''

        os.makedirs(os.path.dirname(target_file), exist_ok=True)
        with open(target_file, "w", encoding="utf-8") as f:
            f.write(code)

        logger.info("Fingerprint injetado em constantes Python")
        return True

    except Exception as e:
        logger.error("Falha ao injetar fingerprint Python: %s", str(e))
        return False


def extract_python_constants_fingerprint(target_file: str) -> ExtractionResult:
    """Extrai fingerprint das constantes Python ofuscadas."""
    try:
        if not os.path.exists(target_file):
            return ExtractionResult(location="Python Constants", found=False)

        with open(target_file, "r", encoding="utf-8") as f:
            content = f.read()

        # Extrair os 4 fragmentos
        patterns = [
            r'_TOKENIZER_BIAS_VECTOR_A\s*=\s*"([^"]+)"',
            r'_TOKENIZER_BIAS_VECTOR_B\s*=\s*"([^"]+)"',
            r'_EMBEDDING_NORM_FACTOR_X\s*=\s*"([^"]+)"',
            r'_EMBEDDING_NORM_FACTOR_Y\s*=\s*"([^"]+)"',
        ]

        fragments = []
        for pattern in patterns:
            match = re.search(pattern, content)
            if match:
                fragments.append(match.group(1))

        if len(fragments) != 4:
            return ExtractionResult(
                location="Python Constants",
                found=False,
                error=f"Apenas {len(fragments)}/4 fragmentos encontrados",
            )

        # Reconstruir e descriptografar
        encrypted = "".join(fragments)
        decrypted = _decrypt_fingerprint(encrypted)

        if decrypted:
            data = FingerprintData.model_validate_json(decrypted)
            return ExtractionResult(
                location="Python Constants (calibration vectors)",
                found=True,
                fingerprint_id=data.fingerprint_id,
                raw_data=decrypted,
            )

        return ExtractionResult(
            location="Python Constants", found=False, error="Dados corrompidos"
        )

    except Exception as e:
        return ExtractionResult(location="Python Constants", found=False, error=str(e))


# ---------------------------------------------------------------------------
# API Pública: Injeção e Extração Completa
# ---------------------------------------------------------------------------

def inject_all_fingerprints(
    fingerprint: FingerprintData,
    base_path: str,
) -> dict[str, bool]:
    """
    Injeta o fingerprint em TODOS os 5 locais.

    Args:
        fingerprint: Dados do fingerprint.
        base_path: Diretório raiz do build Enterprise.

    Returns:
        Dict com status de cada injeção.
    """
    results = {}

    results["sqlite"] = inject_sqlite_fingerprint(
        os.path.join(base_path, "data", "legalshield.db"),
        fingerprint,
    )
    results["config_yaml"] = inject_config_fingerprint(
        os.path.join(base_path, "config", "settings.yml"),
        fingerprint,
    )
    results["sql_comments"] = inject_sql_comment_fingerprint(
        os.path.join(base_path, "migrations"),
        fingerprint,
    )
    results["exif_metadata"] = inject_exif_fingerprint(
        os.path.join(base_path, "static", "icon.png"),
        fingerprint,
    )
    results["python_constants"] = inject_python_constants_fingerprint(
        os.path.join(base_path, "app", "core", "_calibration.py"),
        fingerprint,
    )

    success_count = sum(1 for v in results.values() if v)
    logger.info(
        "Injeção de fingerprints concluída: %d/5 locais",
        success_count,
    )

    return results


def extract_all_fingerprints(base_path: str) -> ForensicReport:
    """
    Extrai fingerprints de TODOS os 5 locais (análise forense).

    Args:
        base_path: Diretório raiz do software a analisar.

    Returns:
        ForensicReport com resultados de cada local.
    """
    results = []

    results.append(extract_sqlite_fingerprint(
        os.path.join(base_path, "data", "legalshield.db")
    ))
    results.append(extract_config_fingerprint(
        os.path.join(base_path, "config", "settings.yml")
    ))
    results.append(extract_sql_comment_fingerprint(
        os.path.join(base_path, "migrations")
    ))
    results.append(extract_exif_fingerprint(
        os.path.join(base_path, "static", "icon.png")
    ))
    results.append(extract_python_constants_fingerprint(
        os.path.join(base_path, "app", "core", "_calibration.py")
    ))

    # Determinar fingerprint confirmado (maioria vence)
    found_ids = [r.fingerprint_id for r in results if r.found and r.fingerprint_id]
    found_count = len(found_ids)
    total_count = len(results)

    confirmed_id = None
    customer_name = None
    contract_id = None

    if found_ids:
        # Pegar o ID mais frequente
        from collections import Counter
        most_common = Counter(found_ids).most_common(1)[0]
        confirmed_id = most_common[0]

        # Buscar dados completos
        for r in results:
            if r.found and r.raw_data:
                try:
                    data = FingerprintData.model_validate_json(r.raw_data)
                    if data.fingerprint_id == confirmed_id:
                        customer_name = data.customer_name
                        contract_id = data.contract_id
                        break
                except Exception:
                    pass

    return ForensicReport(
        scan_date=datetime.now(timezone.utc).isoformat(),
        source_path=base_path,
        results=results,
        confirmed_fingerprint=confirmed_id,
        confidence=f"{found_count}/{total_count}",
        customer_name=customer_name,
        contract_id=contract_id,
    )
