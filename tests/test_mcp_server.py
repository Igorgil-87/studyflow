import json

from mcp_server.policy import authorize
from mcp_server.server import call_tool, handle


def test_initialize_and_list_tools():
    response = handle({"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {}})
    assert response["result"]["serverInfo"]["name"] == "studyflow-mcp"

    response = handle({"jsonrpc": "2.0", "id": 2, "method": "tools/list"})
    names = {item["name"] for item in response["result"]["tools"]}
    assert names == {
        "studyflow_list_courses",
        "studyflow_tool_registry",
        "studyflow_control_plane_status",
    }


def test_registry_is_read_only():
    response = call_tool("studyflow_tool_registry", {})
    assert response["isError"] is False
    payload = json.loads(response["content"][0]["text"])
    assert payload
    assert all(item["permission"] == "READ" for item in payload)


def test_control_plane_declares_no_write_surface():
    response = call_tool("studyflow_control_plane_status", {})
    assert response["isError"] is False
    payload = json.loads(response["content"][0]["text"])
    assert payload["mcp"]["policy_enforced"] is True
    assert payload["mcp"]["write_tools_exposed"] is False
    assert payload["mcp"]["read_only"] is True


def test_unknown_tool_is_denied():
    assert authorize("youtube.publish")["allowed"] is False
    response = call_tool("youtube.publish", {})
    assert response["isError"] is True
