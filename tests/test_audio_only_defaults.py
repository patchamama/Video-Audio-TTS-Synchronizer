from argparse import Namespace
import os
from pathlib import Path
import sys
from tempfile import TemporaryDirectory

sys.path.insert(0, str(Path(__file__).parent.parent))
from create_video_tts_from_srt import (
    MAX_TTS_RATE,
    AudioSegment,
    Subtitle,
    apply_audio_only_defaults,
    calculate_no_truncate_lag,
    calculate_required_video_padding,
    create_no_truncate_test_srt,
    create_fixed_rate_not_truncate_srt,
    get_no_truncate_rate_list,
    is_rate_optimization_enabled,
    plain_document_lines,
    generate_plain_document_audio,
    generate_api_audio,
    is_paid_tts_quota_error,
    resolve_video_path,
)


def test_srt_without_video_uses_matching_mp4_and_audio_only():
    args = Namespace(srt_file="media/video.srt", video=None, solo_audio=False)

    apply_audio_only_defaults(args)

    assert args.video == "media/video.mp4"
    assert args.solo_audio is True
    assert args.no_truncate is True


def test_explicit_video_and_mode_are_preserved():
    args = Namespace(srt_file="media/video.srt", video="other.mkv", solo_audio=False)

    apply_audio_only_defaults(args)

    assert args.video == "other.mkv"
    assert args.solo_audio is False


def test_audio_only_accepts_a_missing_video_as_an_output_name_base():
    video_path = resolve_video_path("media/video.mp4", allow_missing=True)

    assert video_path == Path("media/video.mp4")


def test_video_processing_rejects_a_missing_video():
    assert resolve_video_path("media/video.mp4") is None


def test_plain_document_lines_strip_markdown_without_timestamps():
    with TemporaryDirectory() as directory:
        document = Path(directory) / 'chapter.md'
        document.write_text('# Title\n\n- **Hello** [world](https://example.test)!\n\n```\nignored\n```\n', encoding='utf-8')

        assert plain_document_lines(document) == ['Title', 'Hello world!']


def test_plain_document_audio_uses_fixed_rate_and_generated_cues():
    import create_video_tts_from_srt as module
    original = module.generate_api_audio
    original_cwd = Path.cwd()
    captured = {}
    try:
        with TemporaryDirectory() as directory:
            root = Path(directory)
            document = root / 'chapter.txt'
            document.write_text('First sentence.\nSecond sentence.', encoding='utf-8')
            def fake_generate(payload, output_directory):
                captured.update(payload)
                audio = output_directory / 'generated_audio.wav'
                audio.write_bytes(b'fake wav')
                return audio, {'rate': payload['rate'], 'language': payload['lang'], 'tts_used': 'fake', 'duration': 2.0, 'cues': [
                    {'id': 1, 'start': 0.0, 'end': 1.0, 'text': 'First sentence.'},
                    {'id': 2, 'start': 1.0, 'end': 2.0, 'text': 'Second sentence.'},
                ]}
            module.generate_api_audio = fake_generate
            os.chdir(root)
            result = generate_plain_document_audio(document, Namespace(test=None, fix_rate_not_truncate=None, fix_rate_not_truncate_pause=1000, lang='en', tts='say', voice='Samantha'))
            assert captured['fixed_rate'] is True
            assert captured['rate'] == 200
            assert captured['text'] == 'First sentence.\nSecond sentence.'
            assert result['wav'].is_file()
            assert '00:00:00,000 --> 00:00:01,000' in result['srt'].read_text(encoding='utf-8')
    finally:
        os.chdir(original_cwd)
        module.generate_api_audio = original


def test_audio_generation_reuses_fragments_and_falls_back_after_paid_quota():
    import create_video_tts_from_srt as module
    original_engine = module.TTSEngine
    original_fallback = module.get_free_tts_fallback
    original_duration = module.get_audio_duration
    original_concat = module._concat_wav_files
    class FakeEngine:
        def __init__(self, language='es', tts_method=None, tts_voice=None):
            self.method, self.last_error, self.calls = tts_method, None, 0
        def generate_audio(self, _text, _rate, output):
            self.calls += 1
            if self.method == 'elevenlabs' and self.calls == 2:
                self.last_error = 'quota_exceeded'
                return False
            output.write_bytes(b'audio')
            return True
        def get_tts_name(self): return self.method
    try:
        module.TTSEngine = FakeEngine
        module.get_free_tts_fallback = lambda *_args, **_kwargs: FakeEngine(tts_method='say')
        module.get_audio_duration = lambda path: 1.0 if path.exists() else 0.0
        module._concat_wav_files = lambda _parts, output, **_kwargs: output.write_bytes(b'joined')
        with TemporaryDirectory() as directory:
            messages = []
            payload = {'text': 'uno\ndos\ntres', 'lang': 'es', 'tts': 'elevenlabs', 'rate': 200, 'fixed_rate': True, '_progress': messages.append}
            _audio, metadata = generate_api_audio(payload, Path(directory))
            assert is_paid_tts_quota_error('quota_exceeded')
            assert metadata['tts_used'] == 'elevenlabs → say'
            assert any('cuota de ElevenLabs agotada' in message for message in messages)
            messages.clear()
            generate_api_audio(payload, Path(directory))
            assert sum('reutilizando fragmento' in message for message in messages) == 3
    finally:
        module.TTSEngine = original_engine
        module.get_free_tts_fallback = original_fallback
        module.get_audio_duration = original_duration
        module._concat_wav_files = original_concat


def test_no_truncate_mode_uses_max_rate_until_it_recovers_sync():
    lag = calculate_no_truncate_lag(0.0, audio_duration=4.0, available_time=3.0)
    assert lag == 1.0
    assert get_no_truncate_rate_list(180, is_behind=True, fixed_rate=None) == [MAX_TTS_RATE]
    assert get_no_truncate_rate_list(180, is_behind=False, fixed_rate=200) == [200, MAX_TTS_RATE]

    lag = calculate_no_truncate_lag(lag, audio_duration=1.0, available_time=2.0)
    assert lag == 0.0


def test_no_truncate_mode_only_extends_video_when_audio_is_longer():
    assert calculate_required_video_padding(10.0, 12.5) == 2.5
    assert calculate_required_video_padding(12.5, 10.0) == 0.0


def test_no_truncate_test_srt_uses_actual_audio_timing_and_offset():
    subtitle = Subtitle(1, "1", "00:00:01,000", "00:00:02,000", 1.0, 2.0, 1.0, "Hola")
    segment = AudioSegment(1, Path("audio.wav"), 240, timing_offset=1.25)

    with TemporaryDirectory() as directory:
        output = create_no_truncate_test_srt(
            Path(directory) / "original.srt", [subtitle], {1: segment},
            duration_getter=lambda _: 3.0,
        )

        assert output.name == "original-to-test.srt"
        assert output.read_text(encoding="utf-8") == (
            "1\n00:00:02,250 --> 00:00:05,250\n(1.250s) Hola\n\n"
        )


def test_no_truncate_test_srt_omits_a_zero_offset_prefix():
    subtitle = Subtitle(1, "1", "00:00:01,000", "00:00:02,000", 1.0, 2.0, 1.0, "Hola")
    segment = AudioSegment(1, Path("audio.wav"), 180, timing_offset=0.0)

    with TemporaryDirectory() as directory:
        output = create_no_truncate_test_srt(
            Path(directory) / "original.srt", [subtitle], {1: segment},
            duration_getter=lambda _: 1.0,
        )

        assert "(0.000s)" not in output.read_text(encoding="utf-8")
        assert output.read_text(encoding="utf-8").endswith("Hola\n\n")


def test_rate_optimization_requires_an_explicit_flag():
    assert is_rate_optimization_enabled(Namespace()) is False
    assert is_rate_optimization_enabled(Namespace(optimize_rate=True, fix_rate=None, fix_rate_not_truncate=None, no_truncate=False)) is True
    assert is_rate_optimization_enabled(Namespace(optimize_rate=True, fix_rate=200, fix_rate_not_truncate=None, no_truncate=False)) is False


def test_fixed_rate_not_truncate_srt_ignores_original_timeline():
    subtitles = [
        Subtitle(1, "1", "00:01:00,000", "00:01:01,000", 60.0, 61.0, 1.0, "Primero."),
        Subtitle(2, "2", "00:05:00,000", "00:05:01,000", 300.0, 301.0, 1.0, "Segundo."),
    ]
    segments = {1: AudioSegment(1, Path("one.wav"), 200), 2: AudioSegment(2, Path("two.wav"), 200)}
    durations = {"one.wav": 1.25, "two.wav": 2.5}
    with TemporaryDirectory() as directory:
        output = create_fixed_rate_not_truncate_srt(
            Path(directory) / "original.srt", subtitles, segments, 200, pause_ms=1000,
            duration_getter=lambda path: durations[path.name],
        )
        assert output.name == "original-fixed-rate-200.srt"
        assert output.read_text(encoding="utf-8") == (
            "1\n00:00:00,000 --> 00:00:01,250\nPrimero.\n\n"
            "2\n00:00:02,250 --> 00:00:04,750\nSegundo.\n\n"
        )


if __name__ == "__main__":
    test_srt_without_video_uses_matching_mp4_and_audio_only()
    test_explicit_video_and_mode_are_preserved()
    test_audio_only_accepts_a_missing_video_as_an_output_name_base()
    test_video_processing_rejects_a_missing_video()
    test_no_truncate_mode_uses_max_rate_until_it_recovers_sync()
    test_no_truncate_mode_only_extends_video_when_audio_is_longer()
    test_no_truncate_test_srt_uses_actual_audio_timing_and_offset()
    test_no_truncate_test_srt_omits_a_zero_offset_prefix()
    test_fixed_rate_not_truncate_srt_ignores_original_timeline()
    test_rate_optimization_requires_an_explicit_flag()
