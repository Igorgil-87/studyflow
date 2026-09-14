"""Read-only policy boundary for the StudyFlow MCP surface.

The current StudyFlow checkout does not contain the historical V54/V55
Tool Governance runtime module. This policy therefore protects the MCP
boundary locally instead of pretending that a missing governance module exists.

When the project's central governance runtime is restored, this module is the
single integration point to replace/delegate.
"""
from __future__ import annotations

from dataclasses import dataclass, asdict


@dataclass(frozen=True)
class ToolPolicy:
    name: str
    permission: str = "READ"
    risk: str = "LOW"
    approval_required: bool = False
    enabled: bool = True

    def to_dict(self) -> dict:
        return asdict(self)


POLICIES = {
    "studyflow_list_courses": ToolPolicy("studyflow_list_courses"),
    "studyflow_tool_registry": ToolPolicy("studyflow_tool_registry"),
    "studyflow_control_plane_status": ToolPolicy("studyflow_control_plane_status"),
}


def list_policies() -> list[dict]:
    return [policy.to_dict() for policy in POLICIES.values()]


def authorize(tool_name: str) -> dict:
    policy = POLICIES.get(tool_name)
    if policy is None:
        return {"allowed": False, "reason": "tool_not_registered"}
    if not policy.enabled:
        return {"allowed": False, "reason": "tool_disabled"}
    if policy.permission != "READ":
        return {"allowed": False, "reason": "mcp_v1_read_only"}
    if policy.approval_required:
        return {"allowed": False, "reason": "approval_not_supported_in_mcp_v1"}
    return {"allowed": True, "reason": "read_only_allowlist"}
