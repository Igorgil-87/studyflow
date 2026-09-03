# Context Observability — StudyFlow

## Objetivo

Tratar a janela de contexto como recurso computacional finito e observável. O painel `/obs` passa a mostrar uso da janela, atribuição por origem, espaço livre, reserva de compactação, custo da chamada, outcome técnico e alertas acionáveis.

## Princípio de verdade

O StudyFlow **não inventa** percentuais por categoria. `System`, `Tools`, `Skills`, `Memory` e `Retrieved Knowledge` aparecem como `não instrumentado` quando o call site não consegue atribuir esses tokens. O que não puder ser atribuído fica em `Não atribuído`.

Nenhum prompt, documento ou mensagem é persistido pela feature. O banco guarda somente contagens, metadados e um hash curto do payload para detectar reinjeção **exata**.

## Métricas

- Context window configurada por modelo
- Used tokens
- System prompt
- Tool definitions
- Skills
- Memory
- Conversation/messages
- Retrieved knowledge
- Unattributed
- Free context
- Compaction reserve (default 17%, configurável)
- Attribution coverage
- Cost per call
- Technical outcome
- Exact duplicate payload count (7d)

## Alertas atuais

- Contexto >= 65%: aproximando-se da reserva de compactação
- Contexto >= 80%: próximo do limite operacional
- Tool definitions >= 15% da janela, quando instrumentado
- Cobertura de atribuição < 80%
- Payload idêntico reinjetado >= 2 vezes em 7 dias

Alertas de baixa relevância de retrieval só devem ser adicionados quando existir um sinal real de relevância/score. Não existe `Context Efficiency` artificial nesta versão.

## Pilares

1. Context Observability
2. Model Routing
3. Agent FinOps
4. Tool / MCP Governance
5. Autonomy Control

## Configuração

- `CONTEXT_WINDOW_DEFAULT=128000`
- `CONTEXT_COMPACTION_RESERVE_PCT=17`
- Override por modelo: `MODEL_CONTEXT_<NOME_NORMALIZADO>`

Exemplo: `MODEL_CONTEXT_GPT_4O_MINI=128000`.
