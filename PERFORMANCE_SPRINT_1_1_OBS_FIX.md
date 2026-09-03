# Performance Sprint 1.1 — correção do painel /obs (V44)

## Sintoma
O painel de Performance exibia `Unexpected token '<'` e marcava configuração/execuções como indisponíveis.

## Causa raiz
A rota `/api/observability/pipeline-stages` referenciava `llm_cache` sem importá-lo. O Flask respondia com sua página HTML de erro 500. O JavaScript do `/obs` chamava `response.json()` diretamente; ao receber HTML iniciado por `<`, escondia a causa real sob um erro de parse JSON.

## Correções
- import local explícito de `cache.llm_cache` no endpoint;
- endpoint encapsulado para devolver JSON também em falha interna;
- resposta de sucesso inclui `ok: true`;
- frontend valida HTTP e `Content-Type` antes de parsear JSON;
- frontend preserva diagnóstico legível se um proxy/login/500 devolver HTML;
- `credentials: same-origin` explícito na leitura da telemetria;
- novo teste `_performance_obs_endpoint_test.py` impede regressão do contrato JSON.

## Escopo
Nenhuma otimização, worker, ffmpeg, Whisper, RAG ou regra de pipeline foi alterada. Esta versão corrige exclusivamente a observabilidade necessária para medir a performance com confiança.
