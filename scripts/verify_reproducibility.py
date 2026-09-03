"""Static reproducibility preflight. Does not start Docker or call paid APIs."""
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parent.parent
required = [
    "Dockerfile", "docker-compose.full.yml", "docker-compose.prod.yml",
    ".env.example", "requirements.txt", "app.py", "worker.py", "scheduler.py",
    "db/init_pgvector.sql", "README.md",
]
missing = [p for p in required if not (ROOT / p).exists()]
if missing:
    print("REPRODUCIBILITY PRECHECK FAIL:", ", ".join(missing))
    sys.exit(1)
print("REPRODUCIBILITY PRECHECK OK ✅")
print("Required artifacts:", len(required))
