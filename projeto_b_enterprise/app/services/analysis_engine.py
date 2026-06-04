"""
LegalShield AI 2026 — Analysis Engine
Orquestrador central dos 4 modos de análise jurídica.
"""

import logging
from datetime import datetime, timezone
from typing import Any, Optional

from pydantic import BaseModel, Field

from .document_processor import ProcessedDocument, process_document
from .llm_connector import LLMConfig, LLMConnector, LLMResponse, TokenUsage
from .prompt_guard import detect_injection, sanitize_for_llm
from .prompt_templates import AnalysisMode, MODE_DESCRIPTIONS

logger = logging.getLogger(__name__)


class AnalysisFinding(BaseModel):
    """Um achado individual da análise."""
    id: int
    titulo: str
    severidade: str  # CRÍTICO, ALTO, MÉDIO, BAIXO
    clausula: str = ""
    descricao: str
    fundamentacao_legal: str = ""
    recomendacao: str = ""
    impacto_financeiro: str = ""


class AnalysisStatistics(BaseModel):
    """Estatísticas resumidas da análise."""
    total_achados: int = 0
    criticos: int = 0
    altos: int = 0
    medios: int = 0
    baixos: int = 0


class AnalysisResult(BaseModel):
    """Resultado completo de uma análise jurídica."""
    # Identificação
    analysis_id: str = ""
    mode: AnalysisMode
    mode_description: str = ""
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    # Documento
    filename: str = ""
    file_type: str = ""
    page_count: int = 0
    ocr_used: bool = False
    document_hash: str = ""

    # Resultados
    resumo_executivo: str = ""
    score_risco: int = 0
    achados: list[AnalysisFinding] = []
    estatisticas: AnalysisStatistics = AnalysisStatistics()

    # Dados brutos (caso o JSON não parse perfeitamente)
    raw_response: str = ""
    parsed_successfully: bool = False

    # Segurança
    injection_detected: bool = False
    threats_found: list[str] = []

    # Uso de recursos
    token_usage: Optional[TokenUsage] = None
    fallback_used: bool = False

    # Campos extras para modo AUDIT
    timeline: list[dict[str, Any]] = []
    passivo_estimado: str = ""


class AnalysisEngine:
    """
    Engine central de análise jurídica.
    Orquestra: validação → extração → sanitização → LLM → resultado estruturado.
    """

    def __init__(self, config: LLMConfig):
        self.llm = LLMConnector(config)
        self.config = config

    async def analyze_file(
        self,
        file_bytes: bytes,
        filename: str,
        mode: AnalysisMode,
        max_text_chars: int = 100_000,
    ) -> AnalysisResult:
        """
        Pipeline completo de análise de um arquivo.

        Args:
            file_bytes: Conteúdo bruto do arquivo.
            filename: Nome do arquivo.
            mode: Modo de análise.
            max_text_chars: Limite de caracteres para envio ao LLM.

        Returns:
            AnalysisResult com todos os achados.
        """
        import uuid

        analysis_id = str(uuid.uuid4())[:12]

        logger.info(
            "Iniciando pipeline de análise",
            extra={
                "analysis_id": analysis_id,
                "filename": filename,
                "mode": mode.value,
            },
        )

        # 1. Processar documento (validação + extração)
        doc = process_document(file_bytes, filename)

        # 2. Verificar prompt injection
        injection_result = detect_injection(doc.text)
        safe_text = sanitize_for_llm(doc.text, max_chars=max_text_chars)

        if not injection_result.is_safe:
            logger.warning(
                "Prompt injection detectado no documento %s! "
                "Texto sanitizado antes do envio.",
                filename,
                extra={"threats": injection_result.threats_found},
            )

        # 3. Enviar ao LLM
        llm_response = await self.llm.analyze_document(safe_text, mode)

        # 4. Construir resultado
        result = self._build_result(
            analysis_id=analysis_id,
            mode=mode,
            doc=doc,
            llm_response=llm_response,
            injection_result=injection_result,
        )

        logger.info(
            "Análise concluída",
            extra={
                "analysis_id": analysis_id,
                "mode": mode.value,
                "achados": result.estatisticas.total_achados,
                "score_risco": result.score_risco,
                "tokens": result.token_usage.total_tokens if result.token_usage else 0,
            },
        )

        return result

    async def analyze_text(
        self,
        text: str,
        mode: AnalysisMode,
        filename: str = "texto_direto",
    ) -> AnalysisResult:
        """
        Analisa texto diretamente (sem arquivo).

        Args:
            text: Texto do contrato.
            mode: Modo de análise.
            filename: Nome de referência.

        Returns:
            AnalysisResult com resultados.
        """
        import uuid

        analysis_id = str(uuid.uuid4())[:12]

        # Verificar injection
        injection_result = detect_injection(text)
        safe_text = sanitize_for_llm(text)

        # Enviar ao LLM
        llm_response = await self.llm.analyze_document(safe_text, mode)

        # Construir resultado simplificado
        result = AnalysisResult(
            analysis_id=analysis_id,
            mode=mode,
            mode_description=MODE_DESCRIPTIONS[mode],
            filename=filename,
            raw_response=llm_response.content,
            injection_detected=not injection_result.is_safe,
            threats_found=injection_result.threats_found,
            token_usage=llm_response.usage,
            fallback_used=llm_response.fallback_used,
        )

        if llm_response.parsed_json:
            result = self._populate_from_json(result, llm_response.parsed_json)

        return result

    def _build_result(
        self,
        analysis_id: str,
        mode: AnalysisMode,
        doc: ProcessedDocument,
        llm_response: LLMResponse,
        injection_result: Any,
    ) -> AnalysisResult:
        """Constrói o AnalysisResult a partir das respostas."""
        result = AnalysisResult(
            analysis_id=analysis_id,
            mode=mode,
            mode_description=MODE_DESCRIPTIONS[mode],
            filename=doc.filename,
            file_type=doc.file_type.value,
            page_count=doc.page_count,
            ocr_used=doc.ocr_used,
            document_hash=doc.sha256_hash,
            raw_response=llm_response.content,
            injection_detected=not injection_result.is_safe,
            threats_found=injection_result.threats_found,
            token_usage=llm_response.usage,
            fallback_used=llm_response.fallback_used,
        )

        # Tentar popular com dados JSON parseados
        if llm_response.parsed_json:
            result = self._populate_from_json(result, llm_response.parsed_json)

        return result

    def _populate_from_json(
        self,
        result: AnalysisResult,
        data: dict,
    ) -> AnalysisResult:
        """Popula o AnalysisResult com dados JSON parseados do LLM."""
        try:
            result.resumo_executivo = data.get("resumo_executivo", "")
            result.score_risco = int(data.get("score_risco", 0))

            # Parsear achados
            achados_raw = data.get("achados", [])
            achados = []
            for item in achados_raw:
                try:
                    achado = AnalysisFinding(
                        id=item.get("id", len(achados) + 1),
                        titulo=item.get("titulo", ""),
                        severidade=item.get("severidade", "MÉDIO"),
                        clausula=item.get("clausula", ""),
                        descricao=item.get("descricao", ""),
                        fundamentacao_legal=item.get("fundamentacao_legal", ""),
                        recomendacao=item.get("recomendacao", ""),
                        impacto_financeiro=item.get("impacto_financeiro", ""),
                    )
                    achados.append(achado)
                except Exception as e:
                    logger.warning("Erro ao parsear achado: %s", str(e))

            result.achados = achados

            # Estatísticas
            stats_raw = data.get("estatisticas", {})
            result.estatisticas = AnalysisStatistics(
                total_achados=stats_raw.get("total_achados", len(achados)),
                criticos=stats_raw.get("criticos", 0),
                altos=stats_raw.get("altos", 0),
                medios=stats_raw.get("medios", 0),
                baixos=stats_raw.get("baixos", 0),
            )

            # Campos extras do modo AUDIT
            result.timeline = data.get("timeline", [])
            result.passivo_estimado = data.get("passivo_estimado", "")

            result.parsed_successfully = True

        except Exception as e:
            logger.error("Erro ao popular resultado do JSON: %s", str(e))
            result.parsed_successfully = False

        return result
