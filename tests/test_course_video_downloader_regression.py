import importlib.util
import sys
import types
from pathlib import Path

# Stubs mínimos: o ambiente de validação deste artefato não tem yt-dlp/langchain,
# mas queremos testar a nossa lógica de seleção/normalização sem rede.
yt_dlp = types.ModuleType('yt_dlp')
class DummyYDL:
    def __init__(self, opts): self.opts = opts
    def __enter__(self): return self
    def __exit__(self, *args): pass
    def download(self, urls): return None
yt_dlp.YoutubeDL = DummyYDL
sys.modules['yt_dlp'] = yt_dlp

lc = types.ModuleType('langchain_core')
lct = types.ModuleType('langchain_core.tools')
class BaseTool:
    def __init__(self, **kwargs):
        for k, v in kwargs.items(): setattr(self, k, v)
lct.BaseTool = BaseTool
sys.modules['langchain_core'] = lc
sys.modules['langchain_core.tools'] = lct

tools_pkg = types.ModuleType('tools')
tools_pkg.__path__ = []
sys.modules['tools'] = tools_pkg
runtime = types.ModuleType('tools.youtube_runtime')
def common_ydl_opts(**kwargs):
    out = {}
    if kwargs.get('cookies_browser'):
        out['cookiesfrombrowser'] = (kwargs['cookies_browser'],)
    if kwargs.get('cookies_file'):
        out['cookiefile'] = kwargs['cookies_file']
    return out
runtime.common_ydl_opts = common_ydl_opts
sys.modules['tools.youtube_runtime'] = runtime
classifier = types.ModuleType('tools.yt_error_classifier')
classifier.classify_download_error = lambda x: 'ERRO: ' + str(x)
sys.modules['tools.yt_error_classifier'] = classifier

spec = importlib.util.spec_from_file_location('video_downloader_under_test', Path('tools/video_downloader.py'))
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)
VideoDownloaderTool = mod.VideoDownloaderTool


def test_video_downloader_returns_static_relative_mp4(tmp_path, monkeypatch):
    tool = VideoDownloaderTool(output_dir=str(tmp_path))

    def fake_try(url, opts):
        target = Path(opts['outtmpl'].replace('%(ext)s', 'mp4'))
        target.write_bytes(b'0' * 4096)
        return None

    monkeypatch.setattr(tool, '_try_download', fake_try)
    result = tool._run('https://youtube.test/video', job_id='abc')
    assert result == 'videos/current_video_abc.mp4'
    assert (tmp_path / 'current_video_abc.mp4').exists()


def test_browser_cookies_are_not_used_inside_container(tmp_path, monkeypatch):
    tool = VideoDownloaderTool(output_dir=str(tmp_path), cookies_browser='chrome')
    seen = []
    monkeypatch.setattr(tool, '_inside_container', lambda: True)

    def fake_try(url, opts):
        seen.append(opts)
        target = Path(opts['outtmpl'].replace('%(ext)s', 'mp4'))
        target.write_bytes(b'0' * 4096)
        return None

    monkeypatch.setattr(tool, '_try_download', fake_try)
    result = tool._run('https://youtube.test/video', job_id='docker')
    assert result.endswith('current_video_docker.mp4')
    assert seen
    assert all('cookiesfrombrowser' not in opts for opts in seen)


def test_merged_stream_fallback_is_configured():
    source = Path('tools/video_downloader.py').read_text(encoding='utf-8')
    assert 'bestvideo[height<=720]' in source
    assert 'bestaudio' in source
    assert 'merge_output_format' in source
    assert 'libx264' in source


def test_pipeline_contract_still_exposes_video_and_clips():
    source = Path('pipelines.py').read_text(encoding='utf-8')
    assert '"video_file": (jobs.get(job_id) or {}).get("video_file")' in source
    assert '"clips": clips_result' in source
    assert 'jobs.set(job_id, "video_file", video_rel)' in source
    assert 'jobs.set(job_id, "clips", clips_result)' in source
