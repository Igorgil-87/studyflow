"""Security audit trail backed by the observability database."""
from __future__ import annotations

import json
import time
from obs import db as obs_db


def record_event(*, event_type: str, action: str, user_key: str = "", target: str = "", trace_id: str = "", risk: str = "low", reasons=None, metadata=None) -> None:
    obs_db.insert_security_event({
        "ts": time.time(), "event_type": event_type, "action": action,
        "user_key": user_key, "target": target, "trace_id": trace_id,
        "risk": risk, "reasons": reasons or [], "metadata": metadata or {},
    })


def recent_events(limit: int = 50) -> list[dict]:
    return obs_db.query(
        "SELECT ts,event_type,action,user_key,target,trace_id,risk,reasons_json,metadata_json FROM security_events ORDER BY ts DESC LIMIT ?",
        (limit,),
    )


def summary() -> dict:
    rows = obs_db.query("SELECT action,risk,count(*) n FROM security_events GROUP BY action,risk")
    totals = {"events": 0, "blocked": 0, "redacted": 0, "allowed": 0, "high_risk": 0}
    for r in rows:
        n = int(r.get("n") or 0)
        totals["events"] += n
        action = r.get("action") or ""
        if action in totals:
            totals[action] += n
        if r.get("risk") == "high":
            totals["high_risk"] += n
    return totals
