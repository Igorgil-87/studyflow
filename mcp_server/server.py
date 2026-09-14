"""StudyFlow MCP Server — functional read-only stdio JSON-RPC server."""
from __future__ import annotations

import json
import sys
from typing import Any

from .policy import authorize, list_policies

PROTOCOL_VERSION = "2025-06-18"
SERVER_INFO = {"name": "studyflow-mcp", "version": "1.1.0"}

TOOLS = {
    "studyflow_list_courses": {
        "description": "Lista cursos disponíveis no catálogo local do StudyFlow.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "limit": {"type": "integer", "minimum": 1, "maximum": 100, "default": 20}
            },
            "additionalProperties": False,
        },
    },
    "studyflow_tool_registry": {
        "description": "Lista a superfície MCP autorizada e sua política read-only.",
        "inputSchema": {"type": "object", "properties": {}, "additionalProperties": False},
    },
    "studyflow_control_plane_status": {
        "description": "Retorna o status seguro da boundary MCP do StudyFlow.",
        "inputSchema": {"type": "object", "properties": {}, "additionalProperties": False},
    },
}


def _text_content(data: Any, *, is_error: bool = False) -> dict:
    text = data if isinstance(data, str) else json.dumps(data, ensure_ascii=False, default=str)
    return {"content": [{"type": "text", "text": text}], "isError": bool(is_error)}


def _safe_courses(limit: int = 20) -> list[dict]:
    # Delayed import keeps initialize/tools-list independent from app dependencies.
    from catalog import all_courses

    rows = all_courses() or []
    safe_limit = max(1, min(int(limit or 20), 100))
    allowed_fields = (
        "id", "title", "titulo", "description", "descricao", "status", "created_at"
    )
    output = []
    for row in rows[:safe_limit]:
        if isinstance(row, dict):
            output.append({k: row.get(k) for k in allowed_fields if row.get(k) is not None})
        else:
            output.append({"value": str(row)})
    return output


def _control_plane() -> dict:
    return {
        "mcp": {
            "transport": "stdio",
            "protocol_version": PROTOCOL_VERSION,
            "read_only": True,
            "write_tools_exposed": False,
            "policy_enforced": True,
            "policy_source": "mcp_server.policy",
        },
        "boundary": (
            "MCP V1.1 uses an explicit read-only allowlist. "
            "The current checkout has no central Tool Governance runtime module."
        ),
        "tools": list_policies(),
    }


def call_tool(name: str, args: dict | None = None) -> dict:
    if name not in TOOLS:
        return _text_content(f"Tool MCP não encontrada: {name}", is_error=True)

    decision = authorize(name)
    if not decision["allowed"]:
        return _text_content(
            f"Tool bloqueada pela política MCP: {decision['reason']}",
            is_error=True,
        )

    args = args or {}
    try:
        if name == "studyflow_list_courses":
            return _text_content(_safe_courses(args.get("limit", 20)))
        if name == "studyflow_tool_registry":
            return _text_content(list_policies())
        if name == "studyflow_control_plane_status":
            return _text_content(_control_plane())
        return _text_content("Tool sem implementação", is_error=True)
    except Exception as exc:
        return _text_content(
            f"Falha controlada: {type(exc).__name__}: {str(exc)[:240]}",
            is_error=True,
        )


def handle(request: dict) -> dict | None:
    method = request.get("method")
    request_id = request.get("id")

    if method == "notifications/initialized":
        return None

    if method == "initialize":
        result = {
            "protocolVersion": PROTOCOL_VERSION,
            "capabilities": {"tools": {"listChanged": False}},
            "serverInfo": SERVER_INFO,
            "instructions": "StudyFlow MCP V1.1 read-only with explicit local policy boundary.",
        }
    elif method == "ping":
        result = {}
    elif method == "tools/list":
        result = {
            "tools": [
                {"name": name, "description": spec["description"], "inputSchema": spec["inputSchema"]}
                for name, spec in TOOLS.items()
            ]
        }
    elif method == "tools/call":
        params = request.get("params") or {}
        result = call_tool(str(params.get("name") or ""), params.get("arguments") or {})
    else:
        return {
            "jsonrpc": "2.0",
            "id": request_id,
            "error": {"code": -32601, "message": f"Method not found: {method}"},
        }

    return {"jsonrpc": "2.0", "id": request_id, "result": result}


def run_stdio() -> None:
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue

        request = None
        try:
            request = json.loads(line)
            response = handle(request)
            if response is not None:
                sys.stdout.write(json.dumps(response, ensure_ascii=False) + "\n")
                sys.stdout.flush()
        except Exception as exc:
            request_id = request.get("id") if isinstance(request, dict) else None
            error = {
                "jsonrpc": "2.0",
                "id": request_id,
                "error": {"code": -32603, "message": f"Internal error: {type(exc).__name__}"},
            }
            sys.stdout.write(json.dumps(error, ensure_ascii=False) + "\n")
            sys.stdout.flush()


if __name__ == "__main__":
    run_stdio()
