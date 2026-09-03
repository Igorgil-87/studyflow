from pathlib import Path

def main():
    p=Path('pipelines.py').read_text()
    assert 'CLIP_PIPELINE_WORKERS", "1"' in p
    assert 'WHISPER_RELEASE_AFTER_TRANSCRIBE' in p
    t=Path('tools/transcriber.py').read_text()
    for x in ['whisper_model_load','whisper_inference','whisper_serialize']:
        assert x in t
    s=Path('tools/video_splitter.py').read_text()
    assert '_smart_copy' not in s
    assert 'stable_reencode_v49' in s
    assert 'cut_mode' in s and 'cut_item' in s
    e=Path('.env.example').read_text()
    assert 'CLIP_PIPELINE_WORKERS=1' in e
    assert 'SMART_CUT=0' in e
    assert 'WHISPER_RELEASE_AFTER_TRANSCRIBE=0' in e
    print('PERFORMANCE WHISPER + STABLE CUT V49 OK')
if __name__ == '__main__': main()
