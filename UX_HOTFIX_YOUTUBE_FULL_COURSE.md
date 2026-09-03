# UX Hotfix — YouTube volta a gerar curso completo

Base: `youtube-study-agent(10).zip` enviado pelo usuário.

## Regra de produto corrigida

- **YouTube**: não passa pela tela `/curso2/<id>/revisar`. O pipeline existente termina a geração e entrega diretamente vídeo, aulas/cortes, flashcards, questões e roteiro na experiência original.
- **Meu material**: mantém o fluxo de plano/estrutura revisável em `/curso2/<id>/revisar`, pois esta revisão pertence ao caminho orientado por documento.

## Implementação

O handler SSE `complete` de `static/js/app.js` voltou ao comportamento anterior à UX Sprint 3: renderiza `quiz`, `roadmap`, `video_file` e `clips` localmente. O endpoint aditivo `/api/curso2/from-youtube/<job_id>` foi preservado no backend para compatibilidade, mas deixou de ser chamado por esta tela.

O harness original do YouTube continua sendo `dispatch -> pipelines.run_curso_pipeline -> SSE`, usando busca no YouTube, download paralelo, Whisper, LLM para quiz/flashcards/roadmap, segmentação das aulas e corte do vídeo.

## Não alterado

- APIs e contratos do pipeline YouTube.
- Fluxo de documento em `/api/curso2/criar`.
- Melhorias recentes do projeto fora deste fluxo.
- Salvamento do curso no catálogo.
