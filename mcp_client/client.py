"""Minimal StudyFlow MCP stdio client.

No third-party MCP SDK is required. Useful for local testing and for StudyFlow
components that want to consume the MCP server through the same boundary an
external client would use.
"""
from __future__ import annotations

import json
import subprocess
import sys
import threading
from typing import Any


class StudyFlowMCPClient:
    def __init__(self, command: list[str] | None = None):
        self.command = command or [sys.executable, "-m", "mcp_server"]
        self._process: subprocess.Popen[str] | None = None
        self._next_id = 1
        self._lock = threading.Lock()

    def start(self) -> "StudyFlowMCPClient":
        if self._process and self._process.poll() is None:
            return self

        self._process = subprocess.Popen(
            self.command,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            bufsize=1,
        )
        self.initialize()
        return self

    def close(self) -> None:
        process = self._process
        self._process = None
        if not process:
            return
        if process.poll() is None:
            process.terminate()
            try:
                process.wait(timeout=3)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait(timeout=3)

    def __enter__(self) -> "StudyFlowMCPClient":
        return self.start()

    def __exit__(self, exc_type, exc, tb) -> None:
        self.close()

    def _request(self, method: str, params: dict | None = None) -> dict:
        if not self._process or self._process.poll() is not None:
            raise RuntimeError("MCP server não está em execução")

        if not self._process.stdin or not self._process.stdout:
            raise RuntimeError("stdio MCP indisponível")

        with self._lock:
            request_id = self._next_id
            self._next_id += 1

            payload: dict[str, Any] = {
                "jsonrpc": "2.0",
                "id": request_id,
                "method": method,
            }
            if params is not None:
                payload["params"] = params

            self._process.stdin.write(
                json.dumps(payload, ensure_ascii=False) + "\n"
            )
            self._process.stdin.flush()

            line = self._process.stdout.readline()
            if not line:
                stderr = ""
                if self._process.stderr:
                    stderr = self._process.stderr.read()[-1000:]
                raise RuntimeError(
                    "MCP server encerrou sem resposta"
                    + (f": {stderr}" if stderr else "")
                )

            response = json.loads(line)
            if response.get("id") != request_id:
                raise RuntimeError("Resposta MCP fora de sequência")
            if "error" in response:
                err = response["error"]
                raise RuntimeError(
                    f"MCP error {err.get('code')}: {err.get('message')}"
                )
            return response.get("result") or {}

    def initialize(self) -> dict:
        result = self._request(
            "initialize",
            {
                "protocolVersion": "2025-06-18",
                "capabilities": {},
                "clientInfo": {
                    "name": "studyflow-native-client",
                    "version": "1.0.0",
                },
            },
        )
        # Notification has no response by protocol design.
        assert self._process and self._process.stdin
        self._process.stdin.write(
            json.dumps(
                {
                    "jsonrpc": "2.0",
                    "method": "notifications/initialized",
                }
            )
            + "\n"
        )
        self._process.stdin.flush()
        return result

    def ping(self) -> dict:
        return self._request("ping")

    def list_tools(self) -> list[dict]:
        return self._request("tools/list").get("tools", [])

    def call_tool(self, name: str, arguments: dict | None = None) -> dict:
        return self._request(
            "tools/call",
            {"name": name, "arguments": arguments or {}},
        )


def main() -> None:
    with StudyFlowMCPClient() as client:
        print(
            json.dumps(
                {
                    "server": client.ping(),
                    "tools": client.list_tools(),
                },
                ensure_ascii=False,
                indent=2,
            )
        )


if __name__ == "__main__":
    main()
