from mcp_client.client import StudyFlowMCPClient


def test_native_client_roundtrip():
    with StudyFlowMCPClient() as client:
        tools = client.list_tools()
        names = {item["name"] for item in tools}
        assert "studyflow_tool_registry" in names

        result = client.call_tool("studyflow_control_plane_status")
        assert result["isError"] is False
