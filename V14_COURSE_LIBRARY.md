# V14 — Course Library + Flashcard polish

## Scope
Only the YouTube course result/library experience was changed. The working video generation pipeline was preserved.

## Changes
- More compact flashcards and extra spacing before questions.
- Explicit **Salvar curso** action after generation.
- Save dialog prefilled with title, YouTube channel (author), and YouTube thumbnail.
- Saved courses appear in **Catálogo** with cover and author.
- On save, the main video and lesson clips are copied into:
  `static/videos/saved_courses/<course_id>/...`
  which is already backed by the Docker named volume `videos_data`.
- Quiz and roadmap metadata are stored with the saved course.
- The previous automatic `curso_atual` write during quiz rendering was removed; saving is now an explicit user action.

## Regression protection
The following video pipeline files are unchanged from V13:
- `pipelines.py`
- `tools/video_splitter.py`
- `tools/video_downloader.py`
- `tools/audio_extractor.py`
