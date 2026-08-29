from pathlib import Path
import sys
from tempfile import TemporaryDirectory

sys.path.insert(0, str(Path(__file__).parent.parent))
from create_video_tts_from_srt import APP_VERSION, WEB_ASSET_NAMES, WEB_ASSETS_URLS, count_notes, fetch_web_asset, ensure_web_assets, get_available_tts, get_say_voices, remove_temp_directories


def test_app_version_uses_semver():
    import re
    assert re.fullmatch(r'\d+\.\d+\.\d+', APP_VERSION)


def test_count_notes_ignores_blank_lines():
    assert count_notes('Primera nota\n\n- [ ] Tarea\n') == 2


def test_remove_temp_directories_only_removes_directories_with_temp_prefix():
    with TemporaryDirectory() as directory:
        root = Path(directory)
        (root / 'temp_first').mkdir()
        (root / 'temp_second').mkdir()
        (root / 'temp_file').write_text('preservar', encoding='utf-8')
        (root / 'resultado.wav').write_text('preservar', encoding='utf-8')

        assert remove_temp_directories(root) == ['temp_first', 'temp_second']
        assert (root / 'temp_file').is_file()
        assert (root / 'resultado.wav').is_file()


def test_available_tts_has_unique_machine_readable_ids():
    engines = get_available_tts()
    assert len({engine['id'] for engine in engines}) == len(engines)
    assert all({'id', 'label', 'offline', 'languages'} <= engine.keys() for engine in engines)
    assert all(engine['languages'] == sorted(set(engine['languages'])) for engine in engines)


def test_installed_say_voices_have_language_metadata():
    assert all({'id', 'name', 'locale', 'language'} <= voice.keys() for voice in get_say_voices())


def test_frontend_filters_tts_using_selected_language():
    script = (Path(__file__).parent.parent / 'web' / 'app.js').read_text(encoding='utf-8')
    assert "engine.languages.includes(apiLang.value)" in script
    assert 'apiLang.onchange = renderTtsForLanguage' in script
    assert 'renderVoicesForTts' in script
    assert 'voice: apiVoice.value || undefined' in script
    assert "backendBase.value = location.origin" in script
    assert 'backendUrl(\'/run\')' in script
    assert 'refreshBackend();' in script
    assert 'function updateCliCommand()' in script
    assert "'--fix-rate-not-truncate'" in script
    assert 'function seekPlayerToCue(player, cue)' in script
    assert "addEventListener('loadedmetadata', seek" in script
    assert "backendUrl('/delete')" in script
    assert 'existingResults' in script
    assert "backendUrl(`/download?${query}`)" in script
    assert 'selectedResultUrls' in script
    assert "backendUrl('/notes')" in script
    assert 'setNotesCount' in script
    assert "backendUrl('/delete-temp-folders')" in script
    assert 'setFaviconProgress' in script
    assert 'favicon.href' in script


def test_minimal_view_is_served_by_backend_not_web_assets():
    source = (Path(__file__).parent.parent / 'create_video_tts_from_srt.py').read_text(encoding='utf-8')
    assert "if parsed.path == '/minimal':" in source
    assert "Location', '/web/index.html?mode=minimal" not in source
    assert 'id=minimalForm' in source
    assert "fetch('/run'" in source
    assert "fetch('/info')" in source
    assert "fetch('/files')" in source
    assert "fetch('/options')" in source
    assert "'/existing?name=" in source
    assert "'/delete-temp-folders'" in source
    assert "if parsed.path == '/download':" in source
    assert "if parsed.path == '/notes':" in source
    assert 'sync_notes_to_github' in source
    assert 'def remove_temp_directories' in source
    assert 'def set_terminal_progress' in source
    assert 'Video TTS · {percent}%' in source


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
