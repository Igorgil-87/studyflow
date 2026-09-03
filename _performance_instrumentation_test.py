"""Regression test — performance telemetry integrity.

Validates:
- additive schema has CPU/memory-headroom columns;
- process-tree RSS includes a child process (proxy for ffmpeg/MoviePy);
- recent/aggregate queries expose the new fields.
"""
import os
import subprocess
import sys
import tempfile
import time

_tmp = tempfile.NamedTemporaryFile(prefix="studyflow-perf-", suffix=".db", delete=False)
_tmp.close()
os.environ["OBS_DB"] = _tmp.name

from obs import db
from obs.stage_timer import medir_etapa


def main():
    db.init()
    with medir_etapa("perf-test-job", "youtuber", "cut", detail="1 clip"):
        code = "import time; x=bytearray(48*1024*1024); time.sleep(0.9)"
        p = subprocess.Popen([sys.executable, "-c", code])
        p.wait(timeout=5)
        time.sleep(0.1)

    rows = db.etapas_recentes("youtuber", 10)
    assert rows, "pipeline_stages não gravou linha"
    row = rows[0]
    assert row["stage"] == "cut"
    assert row["duration_ms"] >= 800
    assert row["peak_rss_mb"] is not None and row["peak_rss_mb"] >= 40, row
    for key in ("min_available_mb", "peak_system_mem_pct", "avg_cpu_pct", "peak_cpu_pct"):
        assert key in row, key

    agg = db.resumo_por_etapa("youtuber")
    assert agg and agg[0]["n"] >= 1
    for key in ("min_available_mb", "media_peak_system_mem_pct", "media_cpu_pct", "max_peak_cpu_pct"):
        assert key in agg[0], key

    print("PERFORMANCE INSTRUMENTATION V2 OK")


if __name__ == "__main__":
    try:
        main()
    finally:
        try:
            os.unlink(_tmp.name)
        except OSError:
            pass
