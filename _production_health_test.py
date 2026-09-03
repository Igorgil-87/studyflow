import os
from production import health

old = dict(os.environ)
try:
    os.environ.pop("REDIS_URL", None)
    os.environ["RUN_MODE"] = "inline"
    os.environ["RAG_ENABLED"] = "0"
    snap = health.snapshot(include_optional_http=False)
    assert snap["ready"] is True
    assert snap["queue"]["mode"] == "inline"
    assert health.check_redis()["required"] is False
    assert health.check_postgres()["required"] is False

    os.environ["GEMINI_API_KEY"] = "dummy-for-config-test"
    providers = {x["provider"]: x for x in health.provider_configuration()}
    assert providers["gemini"]["configured"] is True
    assert "key" not in providers["gemini"]
    print("PRODUCTION HEALTH + READINESS OK ✅")
finally:
    os.environ.clear(); os.environ.update(old)
