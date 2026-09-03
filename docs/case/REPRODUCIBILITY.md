# Reprodutibilidade

## Pré-requisitos
Docker + Docker Compose. Para execução fora de containers, Python e as dependências de `requirements.txt`.

## Setup
```bash
cp .env.example .env
docker compose -f docker-compose.full.yml up -d --build
python scripts/verify_reproducibility.py
python scripts/verify_case_coverage.py
```

## Verificação
```bash
curl http://localhost:5001/healthz
curl -i http://localhost:5001/readyz
```

Configure providers por variáveis de ambiente. Chaves nunca devem ser adicionadas ao frontend ou commitadas. Em produção, use secrets/volumes e `SESSION_COOKIE_SECURE=1` atrás de HTTPS.

## Modos
`RUN_MODE=inline`: desenvolvimento simples. `RUN_MODE=redis`: web desacoplado de workers via Redis/RQ, recomendado para demonstração de arquitetura escalável.
