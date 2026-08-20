FROM python:3.12-slim

# Saída de print() sem buffer — sem isso, os logs de progresso do worker
# (download, transcrição, corte etc) ficam TODOS retidos e só aparecem
# de uma vez no fim do job, fazendo parecer que uma etapa travou quando
# na verdade só está com a saída represada. Isso também é o que permite
# medir com precisão onde o tempo de processamento está indo de verdade.
ENV PYTHONUNBUFFERED=1

# ffmpeg/ffprobe são exigidos por áudio/vídeo.
# Deno é o runtime JS recomendado pelo yt-dlp para resolver os desafios
# JavaScript atuais do YouTube (EJS). Mantemos uma versão mínima suportada
# fixa para builds reproduzíveis; yt-dlp[default] instala os scripts EJS.
ARG DENO_VERSION=2.3.0
RUN apt-get update \
    && apt-get install -y --no-install-recommends ffmpeg curl ca-certificates unzip \
    && rm -rf /var/lib/apt/lists/* \
    && curl -fsSL https://deno.land/install.sh | DENO_INSTALL=/usr/local sh -s v${DENO_VERSION} \
    && deno --version

WORKDIR /app

COPY requirements.txt .

# ENV (não só flag do comando) garante timeout maior em TODAS as fases do
# pip, incluindo resolução de metadados — não só o download em si.
ENV PIP_DEFAULT_TIMEOUT=180

# Retry no nível do SHELL, não só do pip: quando a conexão cai NO MEIO de
# um download grande (ex: av, ~33MB), o --retries do próprio pip às vezes
# não recupera bem porque o arquivo parcial fica "sujo" no cache. Rodar o
# comando de novo do zero (até 5x) é mais confiável nesse cenário.
#
# IMPORTANTE: o "exit 1" no final é o que faz o build FALHAR DE VERDADE se
# as 5 tentativas esgotarem sem sucesso. Sem isso, um `for` que termina sem
# `break` sai com código 0 mesmo se todas as tentativas falharam (o último
# comando executado é o `sleep`, que sempre "dá certo") — e o Docker segue
# como se o build tivesse funcionado, deixando o container sem as libs
# instaladas (foi exatamente isso que quebrou o "gunicorn: not found").
RUN success=0; \
    for i in 1 2 3 4 5; do \
        if pip install --no-cache-dir --default-timeout=180 --retries=3 -r requirements.txt; then \
            success=1; break; \
        fi; \
        echo "pip install falhou (tentativa $i/5) — tentando de novo em 5s..."; \
        sleep 5; \
    done; \
    if [ "$success" != "1" ]; then \
        echo "pip install falhou definitivamente após 5 tentativas — build abortado de propósito."; \
        exit 1; \
    fi

COPY . .

EXPOSE 5000

# Web stateless. SSE exige workers com threads (gthread), não sync puro.
# Override do comando no compose para o serviço worker.
CMD ["gunicorn", "--bind", "0.0.0.0:5000", \
     "--worker-class", "gthread", "--workers", "2", "--threads", "8", \
     "--timeout", "0", "app:app"]
