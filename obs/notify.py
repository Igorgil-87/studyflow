"""
obs/notify.py — notificação de alertas de drift via webhook genérico.

Envia um POST JSON para DRIFT_WEBHOOK_URL. O payload traz `text` (compatível com
webhooks do Slack/Discord) e os `alerts` estruturados (para endpoints próprios).

Tudo fail-open: sem URL configurada, é no-op; falha de rede nunca propaga.
"""

from __future__ import annotations

import json
import os
import urllib.request

WEBHOOK_URL = os.getenv("DRIFT_WEBHOOK_URL", "").strip()


def format_text(report: dict) -> str:
    if report.get("status") != "alert":
        return "✅ Drift: sem desvios relevantes."
    lines = [f"⚠️ *Drift de IA detectado* — {len(report['alerts'])} alerta(s):"]
    for a in report["alerts"]:
        sev = a.get("severity", "").upper()
        lines.append(f"• [{sev}] {a['message']} "
                     f"({a['metric']}: {a['baseline']} → {a['recent']})")
    return "\n".join(lines)


def send_alert(report: dict, _opener=None) -> bool:
    """
    Notifica se houver alerta. Retorna True se enviou, False caso contrário.
    `_opener` permite injetar um cliente HTTP nos testes.
    """
    if report.get("status") != "alert":
        return False
    if not WEBHOOK_URL:
        print("[obs.notify] DRIFT_WEBHOOK_URL não configurado — alerta só no log.")
        print(format_text(report))
        return False

    payload = {
        "text": format_text(report),
        "status": report.get("status"),
        "ts": report.get("ts"),
        "alerts": report.get("alerts", []),
    }
    data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    try:
        if _opener is not None:           # injeção para teste
            _opener(WEBHOOK_URL, data)
        else:
            req = urllib.request.Request(
                WEBHOOK_URL, data=data,
                headers={"Content-Type": "application/json"},
            )
            urllib.request.urlopen(req, timeout=5)
        return True
    except Exception as e:
        print(f"[obs.notify] falha ao enviar webhook (seguindo): {e}")
        return False


class NotifyGate:
    """
    Evita spam: só notifica quando entra em alerta (transição) ou quando o
    conjunto de alertas muda, respeitando um cooldown mínimo.
    """

    def __init__(self, cooldown_s: float):
        self.cooldown_s = cooldown_s
        self._last_ts = 0.0
        self._last_sig = None

    @staticmethod
    def _signature(report: dict) -> str:
        return ",".join(sorted(a["metric"] for a in report.get("alerts", [])))

    def should(self, report: dict, now: float) -> bool:
        if report.get("status") != "alert":
            self._last_sig = None        # voltou ao normal: reseta
            return False
        sig = self._signature(report)
        changed = sig != self._last_sig
        cooled = (now - self._last_ts) >= self.cooldown_s
        if changed or cooled:
            self._last_ts = now
            self._last_sig = sig
            return True
        return False
