"""
LegalShield AI 2026 — LLM Connector
Abstração unificada via LiteLLM para conexão com OpenAI (primário) e Anthropic (fallback).
"""

import json
import logging
import time
from typing import Any, Optional

from pydantic import BaseModel, Field

from .prompt_templates import AnalysisMode, get_analysis_prompt, get_system_prompt

logger = logging.getLogger(__name__)


class LLMConfig(BaseModel):
    """Configuração do conector LLM."""
    openai_api_key: Optional[str] = None
    anthropic_api_key: Optional[str] = None
    primary_model: str = "openai/gpt-4o"
    fallback_model: str = "anthropic/claude-sonnet-4-20250514"
    max_tokens: int = 8192
    temperature: float = 0.1  # Baixa para análise jurídica (precisão)
    timeout: int = 120
    max_retries: int = 2


class TokenUsage(BaseModel):
    """Rastreamento de uso de tokens."""
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0
    model_used: str = ""
    cost_estimate_usd: float = 0.0
    latency_seconds: float = 0.0


class LLMResponse(BaseModel):
    """Resposta do LLM com metadados."""
    content: str
    parsed_json: Optional[dict[str, Any]] = None
    usage: TokenUsage
    fallback_used: bool = False


class LLMConnectorError(Exception):
    """Erro na comunicação com LLM."""
    pass


class LLMConnector:
    """
    Conector LLM unificado via LiteLLM.
    OpenAI como primário, Anthropic como fallback automático.
    """

    def __init__(self, config: LLMConfig):
        self.config = config
        self._setup_keys()

    def _setup_keys(self) -> None:
        """Configura API keys como variáveis de ambiente para LiteLLM."""
        import os
        if self.config.openai_api_key:
            os.environ["OPENAI_API_KEY"] = self.config.openai_api_key
        if self.config.anthropic_api_key:
            os.environ["ANTHROPIC_API_KEY"] = self.config.anthropic_api_key

    def _estimate_cost(self, usage: dict, model: str) -> float:
        """Estima custo em USD baseado no modelo e tokens usados."""
        # Preços aproximados por 1M tokens (maio 2026)
        pricing = {
            "openai/gpt-4o": {"input": 2.50, "output": 10.00},
            "anthropic/claude-sonnet-4-20250514": {"input": 3.00, "output": 15.00},
        }
        prices = pricing.get(model, {"input": 5.00, "output": 15.00})
        prompt_cost = (usage.get("prompt_tokens", 0) / 1_000_000) * prices["input"]
        completion_cost = (usage.get("completion_tokens", 0) / 1_000_000) * prices["output"]
        return round(prompt_cost + completion_cost, 6)

    async def completion(
        self,
        system_prompt: str,
        user_prompt: str,
        model: Optional[str] = None,
    ) -> LLMResponse:
        """
        Executa completion com fallback automático.

        Args:
            system_prompt: Prompt do sistema.
            user_prompt: Prompt do usuário.
            model: Modelo específico (opcional, usa primary por padrão).

        Returns:
            LLMResponse com conteúdo e metadados.
        """
        import litellm

        # Configurar litellm
        litellm.set_verbose = False

        models_to_try = [
            model or self.config.primary_model,
            self.config.fallback_model,
        ]
        # Remover duplicatas mantendo ordem
        seen = set()
        models_to_try = [m for m in models_to_try if m not in seen and not seen.add(m)]

        last_error = None
        fallback_used = False

        for i, current_model in enumerate(models_to_try):
            try:
                start_time = time.time()

                call_kwargs = dict(
                    model=current_model,
                    messages=[
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_prompt},
                    ],
                    max_tokens=self.config.max_tokens,
                    temperature=self.config.temperature,
                    timeout=self.config.timeout,
                )
                if "openai" in current_model and self.config.openai_api_key:
                    call_kwargs["api_key"] = self.config.openai_api_key
                elif "anthropic" in current_model and self.config.anthropic_api_key:
                    call_kwargs["api_key"] = self.config.anthropic_api_key

                response = await litellm.acompletion(**call_kwargs)

                latency = time.time() - start_time

                # Extrair dados da resposta
                content = response.choices[0].message.content
                usage_data = {
                    "prompt_tokens": response.usage.prompt_tokens,
                    "completion_tokens": response.usage.completion_tokens,
                }

                usage = TokenUsage(
                    prompt_tokens=usage_data["prompt_tokens"],
                    completion_tokens=usage_data["completion_tokens"],
                    total_tokens=response.usage.total_tokens,
                    model_used=current_model,
                    cost_estimate_usd=self._estimate_cost(usage_data, current_model),
                    latency_seconds=round(latency, 2),
                )

                # Tentar parsear JSON da resposta
                parsed = self._try_parse_json(content)

                if i > 0:
                    fallback_used = True
                    logger.warning(
                        "Fallback usado: %s → %s",
                        models_to_try[0],
                        current_model,
                    )

                logger.info(
                    "LLM completion concluída",
                    extra={
                        "model": current_model,
                        "tokens": usage.total_tokens,
                        "latency_s": usage.latency_seconds,
                        "cost_usd": usage.cost_estimate_usd,
                        "fallback": fallback_used,
                    },
                )

                return LLMResponse(
                    content=content,
                    parsed_json=parsed,
                    usage=usage,
                    fallback_used=fallback_used,
                )

            except Exception as e:
                last_error = e
                logger.warning(
                    "Modelo %s falhou: %s. Tentando próximo...",
                    current_model,
                    str(e),
                )
                continue

        raise LLMConnectorError(
            f"Todos os modelos falharam. Último erro: {last_error}"
        )

    def _try_parse_json(self, content: str) -> Optional[dict]:
        """Tenta extrair JSON da resposta do LLM."""
        # Tentar parse direto
        try:
            return json.loads(content)
        except json.JSONDecodeError:
            pass

        # Tentar extrair JSON de blocos de código
        import re
        json_match = re.search(r"```(?:json)?\s*\n(.*?)\n```", content, re.DOTALL)
        if json_match:
            try:
                return json.loads(json_match.group(1))
            except json.JSONDecodeError:
                pass

        # Tentar encontrar o maior bloco JSON no texto
        brace_start = content.find("{")
        if brace_start != -1:
            brace_count = 0
            for i in range(brace_start, len(content)):
                if content[i] == "{":
                    brace_count += 1
                elif content[i] == "}":
                    brace_count -= 1
                    if brace_count == 0:
                        try:
                            return json.loads(content[brace_start : i + 1])
                        except json.JSONDecodeError:
                            break

        logger.warning("Não foi possível parsear JSON da resposta do LLM")
        return None

    async def analyze_document(
        self,
        document_text: str,
        mode: AnalysisMode,
    ) -> LLMResponse:
        """
        Executa análise jurídica de um documento.

        Args:
            document_text: Texto extraído do documento.
            mode: Modo de análise (defensive, offensive, audit, shield).

        Returns:
            LLMResponse com resultado da análise.
        """
        system_prompt = get_system_prompt()
        user_prompt = get_analysis_prompt(mode, document_text)

        logger.info(
            "Iniciando análise jurídica",
            extra={
                "mode": mode.value,
                "text_length": len(document_text),
            },
        )

        return await self.completion(system_prompt, user_prompt)
