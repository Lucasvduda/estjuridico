"""
LegalShield AI 2026 — License Manager (Projeto B Enterprise)
Validação de licença vinculada ao Hardware ID com bloqueio binário.
Sem phone-home. Sem degradação gradual. 100% offline.
"""

import hashlib
import json
import logging
import platform
import subprocess
import uuid as uuid_lib
from datetime import datetime, timezone
from typing import Optional

from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding, rsa
from pydantic import BaseModel

logger = logging.getLogger(__name__)


class LicenseInfo(BaseModel):
    """Informações da licença."""
    customer_id: str
    customer_name: str
    hardware_id: str
    issued_at: str
    expires_at: str
    features: list[str] = ["defensive", "offensive", "audit", "shield"]
    max_documents_per_month: int = 0  # 0 = ilimitado
    version: str = "1.0"


class LicenseStatus(BaseModel):
    """Status atual da licença."""
    is_valid: bool
    message: str
    customer_name: str = ""
    expires_at: str = ""
    days_remaining: int = 0
    hardware_match: bool = False


class LicenseError(Exception):
    """Erro de licença."""
    pass


# ---------------------------------------------------------------------------
# Hardware ID
# ---------------------------------------------------------------------------

def get_hardware_id() -> str:
    """
    Gera identificador único do hardware baseado em múltiplos componentes.
    Combina: UUID da máquina + nome do processador + nome do host.
    Hash SHA-256 do resultado.
    """
    components = []

    # 1. UUID do sistema (placa-mãe/BIOS)
    try:
        if platform.system() == "Windows":
            result = subprocess.run(
                ["wmic", "csproduct", "get", "UUID"],
                capture_output=True, text=True, timeout=10,
            )
            lines = [l.strip() for l in result.stdout.strip().split("\n") if l.strip() and l.strip() != "UUID"]
            if lines:
                components.append(lines[0])
        elif platform.system() == "Linux":
            try:
                with open("/sys/class/dmi/id/product_uuid", "r") as f:
                    components.append(f.read().strip())
            except (FileNotFoundError, PermissionError):
                # Fallback: machine-id
                try:
                    with open("/etc/machine-id", "r") as f:
                        components.append(f.read().strip())
                except FileNotFoundError:
                    pass
    except Exception as e:
        logger.warning("Não foi possível obter UUID do sistema: %s", str(e))

    # 2. Informações do processador
    components.append(platform.processor() or platform.machine())

    # 3. Nome do host
    components.append(platform.node())

    # 4. Fallback: uuid.getnode() (MAC address como inteiro)
    components.append(str(uuid_lib.getnode()))

    # Combinar e gerar hash
    combined = "|".join(components)
    hardware_id = hashlib.sha256(combined.encode("utf-8")).hexdigest()

    logger.debug("Hardware ID gerado: %s...", hardware_id[:16])
    return hardware_id


# ---------------------------------------------------------------------------
# Geração de Licença (usado pelo VENDEDOR, não pelo cliente)
# ---------------------------------------------------------------------------

def generate_rsa_keypair() -> tuple[bytes, bytes]:
    """
    Gera par de chaves RSA para assinatura de licenças.
    Retorna (private_key_pem, public_key_pem).
    MANTER A CHAVE PRIVADA EM SEGREDO ABSOLUTO.
    """
    private_key = rsa.generate_private_key(
        public_exponent=65537,
        key_size=4096,
    )

    private_pem = private_key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    )

    public_pem = private_key.public_key().public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo,
    )

    return private_pem, public_pem


def create_license(
    license_info: LicenseInfo,
    private_key_pem: bytes,
) -> str:
    """
    Cria licença assinada digitalmente.
    Retorna string da licença (JSON + assinatura em base64).
    """
    import base64

    # Serializar info da licença
    payload = license_info.model_dump_json().encode("utf-8")

    # Assinar com chave privada RSA
    private_key = serialization.load_pem_private_key(private_key_pem, password=None)
    signature = private_key.sign(
        payload,
        padding.PSS(
            mgf=padding.MGF1(hashes.SHA256()),
            salt_length=padding.PSS.MAX_LENGTH,
        ),
        hashes.SHA256(),
    )

    # Formato da licença: JSON base64 + "." + assinatura base64
    license_str = (
        base64.b64encode(payload).decode("utf-8")
        + "."
        + base64.b64encode(signature).decode("utf-8")
    )

    return license_str


# ---------------------------------------------------------------------------
# Validação de Licença (usado pelo SOFTWARE DO CLIENTE)
# ---------------------------------------------------------------------------

# Chave pública embutida (substituir pela sua chave real em produção)
EMBEDDED_PUBLIC_KEY = b"""-----BEGIN PUBLIC KEY-----
SUBSTITUIR_PELA_CHAVE_PUBLICA_REAL_EM_PRODUCAO
-----END PUBLIC KEY-----"""


def validate_license(
    license_str: str,
    public_key_pem: Optional[bytes] = None,
) -> LicenseStatus:
    """
    Valida licença: verifica assinatura RSA, hardware ID e data de expiração.
    Bloqueio BINÁRIO: ou funciona 100% ou não funciona.
    """
    import base64

    pub_key_bytes = public_key_pem or EMBEDDED_PUBLIC_KEY

    try:
        # 1. Separar payload e assinatura
        parts = license_str.strip().split(".")
        if len(parts) != 2:
            return LicenseStatus(
                is_valid=False,
                message="Formato de licença inválido.",
            )

        payload_b64, signature_b64 = parts
        payload = base64.b64decode(payload_b64)
        signature = base64.b64decode(signature_b64)

        # 2. Verificar assinatura RSA
        public_key = serialization.load_pem_public_key(pub_key_bytes)
        try:
            public_key.verify(
                signature,
                payload,
                padding.PSS(
                    mgf=padding.MGF1(hashes.SHA256()),
                    salt_length=padding.PSS.MAX_LENGTH,
                ),
                hashes.SHA256(),
            )
        except Exception:
            return LicenseStatus(
                is_valid=False,
                message="Assinatura da licença inválida. Licença corrompida ou adulterada.",
            )

        # 3. Parsear informações da licença
        license_info = LicenseInfo.model_validate_json(payload)

        # 4. Verificar Hardware ID
        current_hw_id = get_hardware_id()
        hardware_match = license_info.hardware_id == current_hw_id
        if not hardware_match:
            return LicenseStatus(
                is_valid=False,
                message="Licença inválida para este hardware. Contate o suporte.",
                hardware_match=False,
            )

        # 5. Verificar expiração
        expires = datetime.fromisoformat(license_info.expires_at)
        now = datetime.now(timezone.utc)

        if now > expires:
            return LicenseStatus(
                is_valid=False,
                message="Licença expirada. Contate o suporte para renovação.",
                customer_name=license_info.customer_name,
                expires_at=license_info.expires_at,
                days_remaining=0,
                hardware_match=True,
            )

        days_remaining = (expires - now).days

        # ✅ Licença válida
        return LicenseStatus(
            is_valid=True,
            message=f"Licença válida. {days_remaining} dias restantes.",
            customer_name=license_info.customer_name,
            expires_at=license_info.expires_at,
            days_remaining=days_remaining,
            hardware_match=True,
        )

    except Exception as e:
        logger.error("Erro na validação da licença: %s", str(e))
        return LicenseStatus(
            is_valid=False,
            message="Erro ao validar licença. Contate o suporte.",
        )
