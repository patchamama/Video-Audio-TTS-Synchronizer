from pathlib import Path
import sys
from tempfile import TemporaryDirectory

sys.path.insert(0, str(Path(__file__).parent.parent))
from create_video_tts_from_srt import APP_VERSION, WEB_ASSET_NAMES, WEB_ASSETS_URLS, fetch_web_asset, ensure_web_assets


def test_app_version_uses_semver():
    import re
    assert re.fullmatch(r'\d+\.\d+\.\d+', APP_VERSION)


def test_private_asset_fetch_uses_github_token(monkeypatch=None):
    # La prueba evita red: intercepta urlopen y comprueba el header construido.
    import create_video_tts_from_srt as module
    captured = {}
    class Response:
        def read(self): return b'asset'
    original = module.urlopen
    original_token = module.os.environ.get('GITHUB_TOKEN')
    try:
        module.os.environ['GITHUB_TOKEN'] = 'test-token'
        module.urlopen = lambda request, timeout: captured.update(request=request, timeout=timeout) or Response()
        assert fetch_web_asset('https://example.test/web/index.html') == b'asset'
        assert captured['request'].get_header('Authorization') == 'Bearer test-token'
        assert captured['request'].get_header('User-agent') == 'Video-Audio-TTS-Synchronizer'
    finally:
        module.urlopen = original
        if original_token is None: module.os.environ.pop('GITHUB_TOKEN', None)
        else: module.os.environ['GITHUB_TOKEN'] = original_token


def test_downloads_missing_web_assets():
    with TemporaryDirectory() as directory:
        requested = []
        def fetch(url):
            requested.append(url)
            return f'asset:{Path(url).name}'.encode()

        web_dir = ensure_web_assets(Path(directory) / 'web', fetch)

        assert web_dir == Path(directory) / 'web'
        assert requested == [
            f'{WEB_ASSETS_URLS[0]}{name}'
            for name in WEB_ASSET_NAMES
        ]
        assert all((web_dir / name).read_bytes() == f'asset:{name}'.encode() for name in WEB_ASSET_NAMES)


def test_downloads_from_published_branch_when_main_lacks_assets():
    with TemporaryDirectory() as directory:
        requested = []
        def fetch(url):
            requested.append(url)
            if url.startswith(WEB_ASSETS_URLS[0]):
                raise OSError('404')
            return f'fallback:{Path(url).name}'.encode()

        web_dir = ensure_web_assets(Path(directory) / 'web', fetch)

        assert web_dir is not None
        assert any(url.startswith(WEB_ASSETS_URLS[1]) for url in requested)
        assert (web_dir / 'index.html').read_bytes() == b'fallback:index.html'


def test_uses_minimal_fallback_when_web_download_fails():
    with TemporaryDirectory() as directory:
        def fail(_):
            raise OSError('offline')

        assert ensure_web_assets(Path(directory) / 'web', fail) is None

if __name__ == '__main__':
    test_private_asset_fetch_uses_github_token()
    test_downloads_missing_web_assets()
    test_uses_minimal_fallback_when_web_download_fails()
    test_downloads_from_published_branch_when_main_lacks_assets()
