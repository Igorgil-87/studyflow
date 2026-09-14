# StudyFlow MCP Functional Patch V1.1

Correção da V1 após validação contra o checkout atual.

## O que foi corrigido

A V1 assumia que existia `obs.tool_governance`. O source atual não contém esse
módulo. A V1.1 remove essa dependência inexistente.

Foi adicionada uma boundary local e explícita:

`mcp_server/policy.py`

Ela aplica allowlist read-only e deny-by-default.

## Boundary

MCP Client -> stdio JSON-RPC -> MCP Server -> MCP Policy -> StudyFlow capability

A política V1.1 expõe somente:

- `studyflow_list_courses`
- `studyflow_tool_registry`
- `studyflow_control_plane_status`

Qualquer tool desconhecida é negada. Nenhuma capability WRITE é exposta.

## Importante

Isto não afirma que o Tool Governance histórico V54/V55 está presente no runtime
atual. Quando o Control Plane central for restaurado/reimplementado, a integração
deve ser feita em `mcp_server/policy.py`.

## Testes

```bash
pytest -q tests/test_mcp_server.py tests/test_mcp_client.py
```

## Execução

```bash
python3 -m mcp_client
```

ou diretamente:

```bash
python3 -m mcp_server
```
