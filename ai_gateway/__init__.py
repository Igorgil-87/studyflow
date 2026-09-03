"""StudyFlow AI Gateway.

Camada única de acesso a modelos de linguagem. Mantém a aplicação desacoplada
 dos SDKs de OpenAI/Anthropic/Gemini e oferece fallback, tracing e metadados
uniformes sem expor secrets.
"""
from .gateway import (
    AIGatewayError,
    GatewayResult,
    configured_providers,
    generate_messages,
    generate_text,
    gateway_config,
    provider_status,
)

__all__ = [
    "AIGatewayError", "GatewayResult", "configured_providers",
    "generate_messages", "generate_text", "gateway_config", "provider_status",
]
