"""
scheduler.py — agendador do drift (processo próprio, leve).

A cada DRIFT_INTERVAL_SECONDS roda uma verificação de drift e, em caso de
alerta, notifica via webhook (respeitando cooldown anti-spam). Persiste cada
verificação em `drift_runs`, então o histórico aparece na tela /obs.

Funciona em qualquer modo (lê o mesmo SQLite do obs). No modo redis, rode UMA
réplica deste processo (não precisa escalar).

Uso:
    python scheduler.py                 # loop contínuo
    python scheduler.py --once          # roda uma vez e sai (útil em cron/CI)

Em K8s, pode ser um CronJob chamando `--once`, ou um Deployment com 1 réplica.
"""

import os
import signal
import sys
import time

from dotenv import load_dotenv

load_dotenv()

from obs import db, drift, notify  # noqa: E402

INTERVAL = int(os.getenv("DRIFT_INTERVAL_SECONDS", "3600"))
COOLDOWN = int(os.getenv("DRIFT_NOTIFY_COOLDOWN_MIN", "60")) * 60

_running = True


def _stop(signum, frame):
    global _running
    _running = False
    print("\n[scheduler] SIGTERM recebido — encerrando após o ciclo atual.")


def tick(gate: notify.NotifyGate) -> dict:
    report = drift.run_check()
    n = len(report["alerts"])
    print(f"[scheduler] drift status={report['status']} alertas={n} "
          f"(recente {report['window']['recent_h']}h vs baseline "
          f"{report['window']['baseline_h']}h)")
    if report["status"] == "alert" and gate.should(report, time.time()):
        sent = notify.send_alert(report)
        print(f"[scheduler] notificação {'enviada' if sent else 'não enviada'}.")
    return report


def main() -> None:
    db.init()
    gate = notify.NotifyGate(COOLDOWN)

    if "--once" in sys.argv:
        tick(gate)
        return

    signal.signal(signal.SIGTERM, _stop)
    signal.signal(signal.SIGINT, _stop)
    print(f"[scheduler] iniciado · intervalo={INTERVAL}s · cooldown={COOLDOWN}s")
    while _running:
        try:
            tick(gate)
        except Exception as e:               # nunca morre por erro de um ciclo
            print(f"[scheduler] erro no ciclo (seguindo): {e}")
        # sleep fatiado para responder rápido ao SIGTERM
        for _ in range(INTERVAL):
            if not _running:
                break
            time.sleep(1)
    print("[scheduler] encerrado.")


if __name__ == "__main__":
    main()
