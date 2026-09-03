"""Context-window observability without storing prompt contents.

The panel is deliberately conservative: categories are only reported when the
caller can attribute them. Unknown context is shown as "unattributed", never as
zero-cost/zero-token context.
"""
from __future__ import annotations

import hashlib
import os
from . import pricing

# Conservative defaults. Override with MODEL_CONTEXT_<NORMALIZED_MODEL> or
# CONTEXT_WINDOW_DEFAULT when a provider/model has a different deployed limit.
_MODEL_LIMITS = {
    "gpt-4o": 128_000,
    "gpt-4o-mini": 128_000,
    "gpt-4.1": 1_000_000,
    "gpt-4.1-mini": 1_000_000,
    "gpt-5": 400_000,
    "gpt-5-mini": 400_000,
    "claude-sonnet-4": 200_000,
    "claude-sonnet-4-6": 200_000,
    "claude-haiku-4-5": 200_000,
    "gemini-2.5-pro": 1_048_576,
    "gemini-2.5-flash": 1_048_576,
}

CATEGORIES = ("system", "tools", "skills", "memory", "conversation", "retrieved")


def context_limit(model: str) -> int:
    norm = (model or "").lower().strip()
    env_key = "MODEL_CONTEXT_" + "".join(c if c.isalnum() else "_" for c in norm).upper()
    if os.getenv(env_key):
        try: return int(os.getenv(env_key, "0"))
        except ValueError: pass
    for key, value in _MODEL_LIMITS.items():
        if norm.startswith(key): return value
    try: return int(os.getenv("CONTEXT_WINDOW_DEFAULT", "128000"))
    except ValueError: return 128_000


def reserve_tokens(limit: int) -> int:
    try: ratio = float(os.getenv("CONTEXT_COMPACTION_RESERVE_PCT", "17")) / 100.0
    except ValueError: ratio = 0.17
    ratio = max(0.05, min(0.35, ratio))
    return int(limit * ratio)


def hash_input(text: str) -> str:
    if not text: return ""
    return hashlib.sha256(text.encode("utf-8", errors="ignore")).hexdigest()[:24]


def estimate_breakdown(model: str, input_text: str, breakdown: dict | None = None) -> dict:
    total = pricing.estimate_tokens(input_text or "", model)
    out = {k: None for k in CATEGORIES}
    known = 0
    if breakdown:
        for key in CATEGORIES:
            value = breakdown.get(key)
            if value is None: continue
            if isinstance(value, str): value = pricing.estimate_tokens(value, model)
            try: value = max(0, int(value))
            except (TypeError, ValueError): continue
            out[key] = value; known += value
    # If no caller-level attribution exists, preserve truth: the payload is known,
    # but its internal origin is not. Do not label it all as conversation.
    unattributed = max(0, total - known)
    out["unattributed"] = unattributed
    out["used"] = total
    out["coverage_pct"] = round((known / total * 100.0), 1) if total else 100.0
    return out


def breakdown_from_messages(messages: list[dict], model: str) -> dict:
    system = []
    conversation = []
    for m in messages or []:
        role = (m.get("role") or "").lower()
        content = m.get("content") or ""
        if role == "system": system.append(content)
        else: conversation.append(content)
    # generate_messages does not accept tool definitions, so tools=0 is known.
    return {
        "system": pricing.estimate_tokens("\n".join(system), model),
        "tools": 0,
        "conversation": pricing.estimate_tokens("\n".join(conversation), model),
        # skills/memory/retrieved remain unknown unless a caller instruments them.
    }
