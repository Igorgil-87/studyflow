# StudyFlow UX v2 — execução local

## Estrutura esperada

As duas pastas devem ficar lado a lado:

```text
seu-diretorio/
├── youtube-study-agent/        # StudyFlow
└── MoneyPrinterTurbo-main/     # motor de vídeo do Marcos Cezar
```

O Fooocus é opcional e, por padrão, é procurado também ao lado:

```text
seu-diretorio/
└── Fooocus-API-main/
```

Se estiver em outro lugar:

```bash
FOOOCUS_DIR=/caminho/Fooocus-API-main ./start_studyflow.sh
```

## Pré-requisitos

- Docker Desktop aberto e pronto
- `.env` configurado no StudyFlow
- `MoneyPrinterTurbo-main/config.toml` configurado para geração de vídeo
- Fooocus-API opcional para geração local de imagens
- `client_secret.json` somente se você for publicar no YouTube

## Subir tudo

Na pasta do StudyFlow:

```bash
chmod +x start_studyflow.sh stop_studyflow.sh
./start_studyflow.sh
```

O navegador é aberto automaticamente no macOS.

URLs locais:

- StudyFlow: http://localhost:5001
- MoneyPrinterTurbo: http://localhost:8080
- n8n: http://localhost:5678
- Fooocus-API: http://localhost:8888
- PostgreSQL: localhost:5432

## Subir mais rápido, sem rebuild

Depois do primeiro build:

```bash
./start_studyflow.sh --no-build
```

## Subir sem Fooocus

```bash
./start_studyflow.sh --no-fooocus
```

O restante do StudyFlow sobe normalmente; apenas funções que dependem do Fooocus ficam indisponíveis.

## Ver logs

```bash
docker compose -f docker-compose.full.yml logs -f web worker
```

Ou já iniciar acompanhando logs:

```bash
./start_studyflow.sh --logs
```

## Parar

```bash
./stop_studyflow.sh
```

O comando normal preserva PostgreSQL, n8n e mídias armazenadas nos volumes Docker.

Para apagar também os volumes locais (ação destrutiva):

```bash
./stop_studyflow.sh --volumes
```

## Bitwarden

A sincronização não ocorre por padrão, para o startup nunca parar esperando senha.

Para habilitar explicitamente:

```bash
export BW_SESSION="$(bw unlock --raw)"
STUDYFLOW_SYNC_BITWARDEN=1 ./start_studyflow.sh
```
