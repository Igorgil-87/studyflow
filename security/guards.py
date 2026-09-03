"""Deterministic guardrails for AI-facing inputs and outputs.

These guards are deliberately model-independent: they protect the prompt boundary
before any provider call and prevent obvious secret material from being returned.
They are not marketed as a perfect prompt-injection detector; every decision is
auditable and can run in monitor or enforce mode.
"""
from __future__ import annotations

import os
import re
from dataclasses import dataclass, asdict

_MAX_INPUT = int(os.getenv("AI_GUARD_MAX_INPUT_CHARS", "8000"))
_MODE = os.getenv("AI_GUARD_MODE", "enforce").strip().lower()
if _MODE not in {"off", "monitor", "enforce"}:
    _MODE = "enforce"

_PATTERNS = [
    ("ignore_instructions", re.compile(r"\b(ignore|disregard|forget)\b.{0,50}\b(previous|prior|above|system|developer)\b.{0,30}\b(instruction|prompt|message)s?\b", re.I | re.S), "high"),
    ("system_prompt_exfiltration", re.compile(r"\b(show|reveal|print|dump|repeat|expose|return)\b.{0,60}\b(system prompt|developer message|hidden prompt|internal instructions?)\b", re.I | re.S), "high"),
    ("role_override", re.compile(r"\b(you are now|act as|pretend to be|switch role)\b.{0,80}\b(system|developer|administrator|root|unrestricted|jailbreak)\b", re.I | re.S), "medium"),
    ("secret_exfiltration", re.compile(r"\b(show|reveal|print|dump|expose|return)\b.{0,80}\b(api[_ -]?key|secret[_ -]?key|password|token|credentials?|\.env)\b", re.I | re.S), "high"),
    ("tool_abuse", re.compile(r"\b(run|execute|call|use)\b.{0,50}\b(shell|terminal|bash|powershell|system command|rm -rf|curl)\b", re.I | re.S), "medium"),
]

_SECRET_PATTERNS = [
    re.compile(r"\bsk-[A-Za-z0-9_-]{16,}\b"),
    re.compile(r"\bAIza[0-9A-Za-z_-]{20,}\b"),
    re.compile(r"\b(?:ghp|github_pat)_[A-Za-z0-9_]{16,}\b"),
    re.compile(r"(?i)\b(?:api[_ -]?key|secret[_ -]?key|password|token)\s*[:=]\s*['\"]?[A-Za-z0-9_./+\-=]{12,}"),
]

@dataclass
class GuardResult:
    allowed: bool
    mode: str
    risk: str
    reasons: list[str]
    length: int
    sanitized: str

    def to_dict(self) -> dict:
        return asdict(self)


def security_config() -> dict:
    return {"mode": _MODE, "max_input_chars": _MAX_INPUT, "patterns": len(_PATTERNS), "output_secret_redaction": True}


def inspect_input(text: str) -> GuardResult:
    text = (text or "").strip()
    reasons: list[str] = []
    severities: list[str] = []
    if len(text) > _MAX_INPUT:
        reasons.append("input_too_long")
        severities.append("medium")
    for name, pattern, severity in _PATTERNS:
        if pattern.search(text):
            reasons.append(name)
            severities.append(severity)
    risk = "high" if "high" in severities else "medium" if severities else "low"
    blocked = bool(reasons) and _MODE == "enforce"
    sanitized = text[:_MAX_INPUT] if len(text) > _MAX_INPUT else text
    return GuardResult(not blocked, _MODE, risk, reasons, len(text), sanitized)


def protect_output(text: str) -> tuple[str, list[str]]:
    """Redact obvious credential-shaped material from model output."""
    output = text or ""
    redactions: list[str] = []
    for idx, pattern in enumerate(_SECRET_PATTERNS, start=1):
        if pattern.search(output):
            redactions.append(f"secret_pattern_{idx}")
            output = pattern.sub("[REDACTED_BY_STUDYFLOW]", output)
    return output, redactions
