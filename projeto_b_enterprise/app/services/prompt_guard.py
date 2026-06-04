"""
LegalShield AI 2026 — Prompt Guard
Detecção e sanitização de tentativas de Prompt Injection em documentos.
"""

import re
import logging
from typing import Optional

from pydantic import BaseModel

logger = logging.getLogger(__name__)


class InjectionDetectionResult(BaseModel):
    """Resultado da verificação de prompt injection."""
    is_safe: bool
    threats_found: list[str] = []
    sanitized_text: str
    original_length: int
    sanitized_length: int


# ---------------------------------------------------------------------------
# Padrões de Prompt Injection conhecidos
# ---------------------------------------------------------------------------

INJECTION_PATTERNS = [
    # Tentativas de override do system prompt
    r"(?i)ignore\s+(all\s+)?(previous|above|prior)\s+(instructions?|prompts?|rules?|directions?)",
    r"(?i)disregard\s+(all\s+)?(previous|above|prior)\s+(instructions?|prompts?)",
    r"(?i)forget\s+(everything|all)\s+(you\s+)?(know|learned|were told)",
    r"(?i)you\s+are\s+now\s+(a|an)\s+",
    r"(?i)new\s+instructions?:\s*",
    r"(?i)system\s*prompt\s*override",
    r"(?i)act\s+as\s+(if|though)\s+you\s+(are|were)",
    r"(?i)pretend\s+(you\s+are|to\s+be)",

    # Tentativas de extração do system prompt
    r"(?i)what\s+(are|is)\s+your\s+(system\s+)?prompt",
    r"(?i)repeat\s+(your\s+)?(system\s+)?(prompt|instructions)",
    r"(?i)show\s+(me\s+)?(your\s+)?(system\s+)?(prompt|instructions)",
    r"(?i)print\s+(your\s+)?(system\s+)?(prompt|instructions)",
    r"(?i)reveal\s+(your\s+)?(system\s+)?(prompt|instructions|rules)",

    # Delimitadores de prompt
    r"```system",
    r"\[SYSTEM\]",
    r"\[INST\]",
    r"<\|im_start\|>",
    r"<\|system\|>",
    r"<<SYS>>",
    r"\[\/INST\]",

    # Instruções maliciosas em português
    r"(?i)ignore\s+as\s+instru[çc][õo]es\s+anteriores",
    r"(?i)esquec[ea]\s+tudo\s+que\s+foi\s+dito",
    r"(?i)novas?\s+instru[çc][õo]es?\s*:",
    r"(?i)a\s+partir\s+de\s+agora\s+voc[êe]\s+[eé]",
    r"(?i)finja\s+que\s+voc[êe]\s+[eé]",

    # Jailbreak patterns
    r"(?i)DAN\s+(mode|prompt)",
    r"(?i)developer\s+mode",
    r"(?i)jailbreak",
    r"(?i)do\s+anything\s+now",
]

# Padrões que são apenas suspeitos (não bloqueiam, mas são registrados)
SUSPICIOUS_PATTERNS = [
    r"(?i)respond\s+(only\s+)?(with|in)\s+(python|code|json)",
    r"(?i)output\s+(only\s+)?(the\s+)?(raw|pure)",
    r"(?i)execute\s+(the\s+following|this)\s+code",
]


def detect_injection(text: str) -> InjectionDetectionResult:
    """
    Analisa texto em busca de padrões de prompt injection.

    Args:
        text: Texto extraído do documento para análise.

    Returns:
        InjectionDetectionResult com status de segurança e texto sanitizado.
    """
    threats = []
    sanitized = text

    # Verificar padrões de injeção
    for pattern in INJECTION_PATTERNS:
        matches = re.findall(pattern, text)
        if matches:
            pattern_name = pattern[:60].replace(r"(?i)", "")
            threats.append(f"Padrão de injeção detectado: {pattern_name}")
            # Remover o trecho malicioso
            sanitized = re.sub(pattern, "[CONTEÚDO REMOVIDO POR SEGURANÇA]", sanitized)

    # Verificar padrões suspeitos (apenas log, não remove)
    for pattern in SUSPICIOUS_PATTERNS:
        matches = re.findall(pattern, text)
        if matches:
            logger.warning(
                "Padrão suspeito detectado no documento (não bloqueado): %s",
                pattern[:60],
            )

    # Sanitizações adicionais
    # Remover sequências de escape potencialmente perigosas
    sanitized = sanitized.replace("\x00", "")  # Null bytes
    sanitized = sanitized.replace("\r", "\n")  # Normalizar line endings

    is_safe = len(threats) == 0

    if not is_safe:
        logger.warning(
            "Prompt injection detectado! %d ameaças encontradas.",
            len(threats),
            extra={"threats": threats},
        )

    return InjectionDetectionResult(
        is_safe=is_safe,
        threats_found=threats,
        sanitized_text=sanitized,
        original_length=len(text),
        sanitized_length=len(sanitized),
    )


def sanitize_for_llm(text: str, max_chars: Optional[int] = None) -> str:
    """
    Sanitiza texto para envio seguro ao LLM.
    Remove injeções e aplica limite de caracteres.

    Args:
        text: Texto a sanitizar.
        max_chars: Limite máximo de caracteres (None = sem limite).

    Returns:
        Texto sanitizado pronto para envio ao LLM.
    """
    result = detect_injection(text)

    output = result.sanitized_text

    if max_chars and len(output) > max_chars:
        output = output[:max_chars]
        output += "\n\n[... TEXTO TRUNCADO POR LIMITE DE TAMANHO ...]"

    return output
