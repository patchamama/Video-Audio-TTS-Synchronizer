from pathlib import Path
import sys
from tempfile import TemporaryDirectory

sys.path.insert(0, str(Path(__file__).parent.parent))
from create_video_tts_from_srt import WEB_ASSET_NAMES, ensure_web_assets


def test_downloads_missing_web_assets():
    with TemporaryDirectory() as directory:
        requested = []
        def fetch(url):
            requested.append(url)
            return f'asset:{Path(url).name}'.encode()

        web_dir = ensure_web_assets(Path(directory) / 'web', fetch)

        assert web_dir == Path(directory) / 'web'
        assert requested == [
            f'https://raw.githubusercontent.com/patchamama/Video-Audio-TTS-Synchronizer/main/web/{name}'
            for name in WEB_ASSET_NAMES
        ]
        assert all((web_dir / name).read_bytes() == f'asset:{name}'.encode() for name in WEB_ASSET_NAMES)


def test_uses_minimal_fallback_when_web_download_fails():
    with TemporaryDirectory() as directory:
        def fail(_):
            raise OSError('offline')

        assert ensure_web_assets(Path(directory) / 'web', fail) is None

if __name__ == '__main__':
    test_downloads_missing_web_assets()
    test_uses_minimal_fallback_when_web_download_fails()
