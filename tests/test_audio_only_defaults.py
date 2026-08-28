from argparse import Namespace
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
    get_no_truncate_rate_list,
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


if __name__ == "__main__":
    test_srt_without_video_uses_matching_mp4_and_audio_only()
    test_explicit_video_and_mode_are_preserved()
    test_audio_only_accepts_a_missing_video_as_an_output_name_base()
    test_video_processing_rejects_a_missing_video()
    test_no_truncate_mode_uses_max_rate_until_it_recovers_sync()
    test_no_truncate_mode_only_extends_video_when_audio_is_longer()
    test_no_truncate_test_srt_uses_actual_audio_timing_and_offset()
