# Aplicar PO Token / HTTP 403 fix

Arquivos alterados nesta versão:

- `requirements.txt`
- `docker-compose.prod.yml`
- `.env.example`
- `.env.production.example`
- `tools/youtube_runtime.py`
- `tools/youtube_doctor.py`
- `tools/video_downloader.py`
- `tools/audio_extractor.py`
- `tools/yt_error_classifier.py`
- `tests/test_yt_error_classifier.py`
- `YOUTUBE_HETZNER_FIX.md`

Fluxo Git sugerido:

```bash
git switch main
git pull origin main
git switch -c fix/youtube-pot-403
```

Substitua os arquivos pelo conteúdo do ZIP e depois:

```bash
git status --short
git add requirements.txt docker-compose.prod.yml .env.example .env.production.example \
  tools/youtube_runtime.py tools/youtube_doctor.py tools/video_downloader.py \
  tools/audio_extractor.py tools/yt_error_classifier.py \
  tests/test_yt_error_classifier.py YOUTUBE_HETZNER_FIX.md APPLY_POT_FIX.md
git commit -m "fix: add YouTube PO token provider and 403 fallback"
git push -u origin fix/youtube-pot-403
```

Após PR, CI verde, merge e deploy:

```bash
cd /opt/studyflow/studyflow
docker compose -f docker-compose.prod.yml up -d --build --remove-orphans
docker compose -f docker-compose.prod.yml exec worker python -m tools.youtube_doctor
```
