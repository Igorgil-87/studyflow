# Course Recovery v6 — rollback funcional seguro

Esta versão parte do P5 Home Redesign v4 (última versão antes do hotfix que alterou o comportamento dos cursos) e aplica somente dois reparos pontuais.

## 1. Fluxo YouTube legado preservado

Os seguintes arquivos foram mantidos sem alteração em relação ao v4/original funcional:

- `pipelines.py`
- `tools/video_splitter.py`
- `tools/audio_extractor.py`
- `tools/video_downloader.py`
- `static/js/app.js`

Isto preserva o fluxo comprovado:

YouTube -> áudio -> vídeo local -> Whisper -> quiz -> roteiro -> segmentação -> corte -> clips -> player em `Aulas`.

A única mudança relacionada ao YouTube está em `tools/youtube_search.py`: a BUSCA de metadados roda sem cookies de navegador. Busca pública não precisa do perfil Chrome e, dentro do Docker, evita o erro `/root/.config/google-chrome`.

Downloads continuam usando exatamente o fallback anterior e o splitter não foi alterado.

## 2. Meu Material / Course Engine

O comportamento de geração NÃO foi automatizado nem reescrito.

Foi corrigido somente o contrato das rotas `manifesto` e `aprovar`: depois de salvar/aprovar, elas retornam o registro persistido completo, no mesmo formato do GET do curso. Isso impede a tela vazia após `Aprovar e continuar` sem mudar o restante do fluxo.

## Validação local

Depois de trocar os arquivos:

```bash
./stop_studyflow.sh
docker compose -f docker-compose.full.yml build web worker
./start_studyflow.sh --no-build
```

Faça hard refresh depois do rebuild.
