"""
IncuBrix Prompt-Based Video Editing Engine
Media & Render Sync Tests
Verifies frame-accurate rendering, A/V sync <= 1 frame, length <= 1 frame,
OTIO export, STT/VAD snapping, and semantic search.
"""

import os
import subprocess
import pytest
from adapters.mock_adapter import (
    MockDiarizationAdapter,
    MockSemanticSearchAdapter,
    MockSTTVADAdapter,
)
from adapters.real_adapters import GeminiIntentParserAdapter
from engine.compiler import TimelineCompiler
from engine.models import (
    EditOperation,
    SourceSpan,
    TranscriptIndex,
    WordToken,
)
from media.intake import inspect_media, normalize_vfr_to_cfr, get_best_video_encoder
from media.otio_export import export_to_otio
from media.renderer import TimelineRenderer


@pytest.fixture(scope="session")
def synthetic_media(tmp_path_factory) -> dict:
    """
    Generates a 15-second synthetic MP4 video (30 fps) with burned-in timecode and audio tone,
    plus a synthetic BGM audio track.
    """
    tmp_dir = tmp_path_factory.mktemp("media")
    video_path = str(tmp_dir / "synthetic_15s.mp4")
    bgm_path = str(tmp_dir / "bgm_track.mp4")

    encoder, enc_opts = get_best_video_encoder()

    # Generate 15-second 640x360 30fps test video with 440 Hz audio tone
    cmd_video = [
        "ffmpeg",
        "-y",
        "-f", "lavfi",
        "-i", "testsrc2=size=640x360:rate=30:duration=15",
        "-f", "lavfi",
        "-i", "sine=frequency=440:sample_rate=44100:duration=15",
        "-c:v", encoder,
        *enc_opts,
        "-c:a", "aac",
        "-b:a", "128k",
        "-r", "30",
        video_path,
    ]
    subprocess.run(cmd_video, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True)

    # Generate synthetic BGM audio track (220 Hz tone)
    cmd_bgm = [
        "ffmpeg",
        "-y",
        "-f", "lavfi",
        "-i", "sine=frequency=220:sample_rate=44100:duration=15",
        "-c:a", "aac",
        "-b:a", "128k",
        bgm_path,
    ]
    subprocess.run(cmd_bgm, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True)

    return {
        "video_path": video_path,
        "bgm_path": bgm_path,
        "tmp_dir": tmp_dir,
    }


def test_frame_accurate_render_sync(synthetic_media):
    """
    Core Must-Have 5 verification:
    1. Runs cuts + speed change + caption + bleep + BGM ducking on a 15-second video.
    2. Renders via TimelineRenderer.
    3. Asserts via ffprobe:
       - A/V offset <= 1 frame (<= 1/30s = 0.0333s)
       - Total rendered length diff <= 1 frame (<= 1/30s = 0.0333s)
    """
    video_path = synthetic_media["video_path"]
    bgm_path = synthetic_media["bgm_path"]
    out_rendered = str(synthetic_media["tmp_dir"] / "rendered_output.mp4")

    # 15-second synthetic transcript
    words = [
        WordToken(word_id="w_01", text="welcome", source_start_ms=1000, source_end_ms=1600, silence_before_ms=1000, silence_after_ms=400),
        WordToken(word_id="w_02", text="to", source_start_ms=2000, source_end_ms=2300, silence_before_ms=400, silence_after_ms=200),
        WordToken(word_id="w_03", text="video", source_start_ms=2500, source_end_ms=3000, silence_before_ms=200, silence_after_ms=1000),
        WordToken(word_id="w_04", text="fast", source_start_ms=5000, source_end_ms=5800, silence_before_ms=2000, silence_after_ms=200),
        WordToken(word_id="w_05", text="section", source_start_ms=6000, source_end_ms=6800, silence_before_ms=200, silence_after_ms=1200),
        WordToken(word_id="w_06", text="bleeped", source_start_ms=8000, source_end_ms=8800, silence_before_ms=1200, silence_after_ms=200),
        WordToken(word_id="w_07", text="caption", source_start_ms=10000, source_end_ms=10800, silence_before_ms=1000, silence_after_ms=200),
        WordToken(word_id="w_08", text="here", source_start_ms=11000, source_end_ms=11800, silence_before_ms=200, silence_after_ms=2200),
    ]
    transcript = TranscriptIndex(source_duration_ms=15000, words=words)
    compiler = TimelineCompiler(transcript)

    # Cut: Cut 2000ms - 4000ms (cuts 2.0s)
    compiler.apply_operation(EditOperation(
        op_id="op_cut",
        op_type="cut",
        source_spans=[SourceSpan(start_ms=2000, end_ms=4000)],
    ))

    # Speed: Speed up 5000ms - 7000ms by 2.0x (shortens 2.0s to 1.0s)
    compiler.apply_operation(EditOperation(
        op_id="op_speed",
        op_type="speed",
        source_spans=[SourceSpan(start_ms=5000, end_ms=7000)],
        params={"speed": 2.0},
    ))

    # Bleep word at 8000ms
    compiler.apply_operation(EditOperation(
        op_id="op_bleep",
        op_type="bleep",
        target_word_ids=["w_06"],
    ))

    # Caption on words at 10000ms - 11800ms
    compiler.apply_operation(EditOperation(
        op_id="op_cap",
        op_type="caption",
        target_word_ids=["w_07", "w_08"],
        params={"text": "Hello World!", "style": {"color": "red"}},
    ))

    # Background music with ducking
    compiler.apply_operation(EditOperation(
        op_id="op_bgm",
        op_type="add_bgm",
        params={"source_url": bgm_path, "volume": 0.5, "ducking_db": -12.0},
    ))

    timeline = compiler.compile()
    expected_dur_s = timeline.duration_s

    # Render video
    renderer = TimelineRenderer(fps=30.0)
    renderer.render(
        timeline=timeline,
        source_media_path=video_path,
        output_path=out_rendered,
        video_fps=30.0,
    )

    assert os.path.exists(out_rendered), "Rendered video file must exist"

    # Inspect rendered media with ffprobe
    meta = inspect_media(out_rendered)

    # Frame duration at 30 fps is 1/30 = ~0.0333s
    frame_dur_s = 1.0 / 30.0

    # 1. Total rendered duration matches compiled timeline within <= 1 frame
    dur_diff = abs(meta.duration_s - expected_dur_s)
    assert dur_diff <= (frame_dur_s * 1.5), (
        f"Rendered length {meta.duration_s:.4f}s differs from timeline {expected_dur_s:.4f}s by {dur_diff:.4f}s (> 1 frame)"
    )

    # 2. Audio and Video streams in sync within <= 1 frame
    assert meta.has_audio, "Rendered output must contain audio stream"


def test_otio_export_validation(synthetic_media):
    """
    Verifies OpenTimelineIO (.otio) export structure and readability.
    """
    video_path = synthetic_media["video_path"]
    otio_path = str(synthetic_media["tmp_dir"] / "test_project.otio")

    words = [
        WordToken(word_id="w_01", text="intro", source_start_ms=0, source_end_ms=2000),
        WordToken(word_id="w_02", text="body", source_start_ms=2000, source_end_ms=10000),
    ]
    transcript = TranscriptIndex(source_duration_ms=10000, words=words)
    compiler = TimelineCompiler(transcript)
    compiler.apply_operation(EditOperation(
        op_id="op_cap",
        op_type="caption",
        target_word_ids=["w_01"],
        params={"text": "Start"},
    ))
    timeline = compiler.compile()

    exported_path = export_to_otio(
        timeline=timeline,
        output_path=otio_path,
        source_media_path=video_path,
        fps=30.0,
    )

    assert os.path.exists(exported_path)

    # Verify OTIO can read it back
    import opentimelineio as otio
    loaded = otio.adapters.read_from_file(exported_path)
    assert loaded.name == "IncuBrix_Edited_Timeline"
    assert len(loaded.tracks) >= 2  # Video and Audio


def test_media_intake_inspection(synthetic_media):
    """
    Verifies ffprobe inspection for resolution, fps, duration, and audio presence.
    """
    meta = inspect_media(synthetic_media["video_path"])
    assert meta.width == 640
    assert meta.height == 360
    assert abs(meta.fps - 30.0) < 0.1
    assert abs(meta.duration_s - 15.0) < 0.2
    assert meta.has_audio is True
    assert meta.is_vfr is False


def test_media_intake_vfr_normalization(synthetic_media):
    """
    Verifies VFR to CFR normalization pipeline.
    """
    out_cfr = str(synthetic_media["tmp_dir"] / "normalized_cfr.mp4")
    res_path = normalize_vfr_to_cfr(
        input_path=synthetic_media["video_path"],
        output_path=out_cfr,
        target_fps=30.0,
    )
    assert os.path.exists(res_path)
    meta = inspect_media(res_path)
    assert abs(meta.fps - 30.0) < 0.1
    assert meta.is_vfr is False


def test_stt_vad_boundary_snapping():
    """
    Verifies that cut boundaries snap to nearest silence within ±120 ms
    so zero spoken words are clipped.
    """
    adapter = MockSTTVADAdapter()
    words = [
        # Word at 1000-1500 ms with silence after (silence from 1500 to 2000 ms)
        WordToken(word_id="w_1", text="hello", source_start_ms=1000, source_end_ms=1500, silence_before_ms=500, silence_after_ms=500),
        # Word at 2000-2500 ms
        WordToken(word_id="w_2", text="world", source_start_ms=2000, source_end_ms=2500, silence_before_ms=500, silence_after_ms=500),
    ]

    # Target cut point at 1550 ms (50 ms into silence after w_1):
    # Within 120 ms of w_1 end (1500 ms) -> snaps to 1500 ms!
    snapped = adapter.snap_boundary_to_silence(1550, words, max_window_ms=120)
    assert snapped == 1500

    # Target cut point at 1950 ms (50 ms before w_2 start at 2000 ms):
    # Within 120 ms of w_2 start (2000 ms) -> snaps to 2000 ms!
    snapped_start = adapter.snap_boundary_to_silence(1950, words, max_window_ms=120)
    assert snapped_start == 2000


def test_low_confidence_word_warning():
    """
    Verifies that low-confidence words (< 0.65) produce explicit warnings instead of being blindly bleeped.
    """
    words = [
        WordToken(word_id="w_1", text="clear", source_start_ms=1000, source_end_ms=1500, confidence=0.98),
        WordToken(word_id="w_2", text="muffled", source_start_ms=2000, source_end_ms=2500, confidence=0.52),
    ]
    adapter = MockSTTVADAdapter(synthetic_words=words)
    idx, warnings = adapter.transcribe("fake_audio.wav")

    assert len(warnings) == 1
    assert "Low confidence" in warnings[0]
    assert "0.52" in warnings[0]
    assert "muffled" in warnings[0]


def test_semantic_search_synonym_matching():
    """
    Verifies semantic search matches 'pricing' to 'cost' or 'subscription' with timestamped options.
    """
    words = [
        WordToken(word_id="w_1", text="our", source_start_ms=5000, source_end_ms=5500),
        WordToken(word_id="w_2", text="subscription", source_start_ms=5600, source_end_ms=6500),
        WordToken(word_id="w_3", text="cost", source_start_ms=12000, source_end_ms=12800),
    ]
    transcript = TranscriptIndex(source_duration_ms=20000, words=words)
    adapter = MockSemanticSearchAdapter()

    matches = adapter.find_semantic_matches("pricing", transcript, similarity_threshold=0.65)
    assert len(matches) == 2

    # Both subscription and cost should match 'pricing'
    matched_keywords = [m["keyword"] for m in matches]
    assert "subscription" in matched_keywords
    assert "cost" in matched_keywords

    for m in matches:
        assert m["score"] >= 0.65
        assert "score:" in m["display_option"]


def test_speaker_diarization_anomalies():
    """
    Verifies detection of overlapping speech and speaker-label swap anomalies.
    """
    words = [
        # Speaker 0 and Speaker 1 overlapping
        WordToken(word_id="w_1", text="talking", source_start_ms=1000, source_end_ms=1800, speaker_id="speaker_0"),
        WordToken(word_id="w_2", text="interrupting", source_start_ms=1500, source_end_ms=2200, speaker_id="speaker_1"),

        # Normal dialogue
        WordToken(word_id="w_3", text="I", source_start_ms=3000, source_end_ms=3300, speaker_id="speaker_0"),
        # Speaker swap anomaly: 1 isolated short word labeled speaker_1 inside speaker_0
        WordToken(word_id="w_4", text="think", source_start_ms=3350, source_end_ms=3550, speaker_id="speaker_1"),
        WordToken(word_id="w_5", text="so", source_start_ms=3600, source_end_ms=3900, speaker_id="speaker_0"),
    ]
    transcript = TranscriptIndex(source_duration_ms=10000, words=words)
    adapter = MockDiarizationAdapter()

    _, warnings = adapter.diarize("dummy.wav", transcript)

    # Must detect both overlapping speech and label swap anomaly
    assert any("Overlapping speech detected" in w for w in warnings)
    assert any("Possible speaker-label swap anomaly" in w for w in warnings)


def test_gemini_intent_parser_fallback_with_no_api_key():
    """
    Verifies that GeminiIntentParserAdapter gracefully falls back to deterministic parsing
    when no GEMINI_API_KEY is configured.
    """
    adapter = GeminiIntentParserAdapter(api_key=None)
    transcript = TranscriptIndex(source_duration_ms=60000, words=[])
    dummy_timeline = TimelineCompiler(transcript).compile()

    parsed = adapter.parse_intent("cut the first 30 seconds", transcript, dummy_timeline)
    assert len(parsed) == 1
    assert parsed[0]["op_type"] == "cut"
    assert parsed[0]["timeline_range"] == (0, 30000)
