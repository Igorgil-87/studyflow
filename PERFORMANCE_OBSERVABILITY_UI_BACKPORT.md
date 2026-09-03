# V50 — Observability UI Backport on V45

Base funcional/performance: V45.

Escopo deliberadamente restrito: trazer o formato mais recente do painel de performance/observabilidade sem alterar o pipeline de download, transcrição, highlights, corte ou verticalização.

Incluído:
- seletor de execução/job;
- visão da execução selecionada sem misturar vídeos diferentes;
- duração por etapa e por item;
- RAM/CPU/pico/memória livre;
- média histórica recolhida em progressive disclosure;
- execuções recentes;
- preset vertical e fast blur na configuração exibida;
- consultas read-only de observabilidade necessárias ao painel.

Não alterado:
- pipeline Youtuber da V45;
- workers;
- presets efetivos;
- lógica de corte;
- lógica de verticalização;
- Whisper;
- geração/publicação de clips.
