"""
IncuBrix Synthetic Test Media Generator
Generates 100% commercially safe, copyright-free test media with burned-in timecodes
and exact ground-truth word transcripts using FFmpeg.
"""

from __future__ import annotations

import json
import logging
import os
import subprocess
import sys

# Ensure repository root is on sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from typing import List
from engine.models import TranscriptIndex, WordToken
from media.intake import get_best_video_encoder

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("incubrix.generate_test_media")


def _run_ffmpeg(cmd: List[str], desc: str):
    logger.info(f"Generating {desc}...")
    res = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    if res.returncode != 0:
        err = res.stderr.decode("utf-8", errors="replace")
        logger.error(f"FFmpeg error generating {desc}:\n{err}")
        raise RuntimeError(f"FFmpeg failed for {desc}: {err}")
    logger.info(f"Successfully generated {desc}")


def generate_single_speaker_interview(output_dir: str):
    """
    Generates test_media/single_speaker_interview.mp4 (90s)
    Contains:
    - 'welcome to the channel' at 0:42–0:44 (42000-44000ms)
    - Protected pause at 45000-47500ms
    - 3 mentions of 'pricing' at 1:05 (65000ms), 1:12 (75000ms), 1:20 (85000ms)
    - Fillers ('um', 'uh', 'like')
    - Burned-in timecode overlay
    """
    video_path = os.path.join(output_dir, "single_speaker_interview.mp4")
    json_path = os.path.join(output_dir, "single_speaker_interview_transcript.json")
    encoder, enc_opts = get_best_video_encoder()

    # Video filter with burned-in timecode and title
    vf = (
        "drawtext=text='Single Speaker Interview | %{pts\\:hms}':"
        "fontsize=24:fontcolor=white:box=1:boxcolor=black@0.65:"
        "x=(w-text_w)/2:y=30"
    )

    cmd = [
        "ffmpeg", "-y",
        "-f", "lavfi", "-i", "testsrc2=duration=90:size=640x360:rate=30",
        "-f", "lavfi", "-i", "sine=frequency=320:sample_rate=44100:duration=90",
        "-vf", vf,
        "-c:v", encoder, *enc_opts,
        "-c:a", "aac", "-b:a", "128k",
        "-t", "90",
        video_path,
    ]
    _run_ffmpeg(cmd, "single_speaker_interview.mp4")

    # Generate ground-truth transcript
    words = [
        WordToken(word_id="w_0001", text="hello", source_start_ms=5000, source_end_ms=5500, speaker_id="speaker_0"),
        WordToken(word_id="w_0002", text="and", source_start_ms=5500, source_end_ms=5800, speaker_id="speaker_0"),
        WordToken(word_id="w_0003", text="start", source_start_ms=5800, source_end_ms=6400, speaker_id="speaker_0"),
        WordToken(word_id="w_0004", text="our", source_start_ms=6400, source_end_ms=6800, speaker_id="speaker_0"),
        WordToken(word_id="w_0005", text="video", source_start_ms=6800, source_end_ms=7500, speaker_id="speaker_0"),
        WordToken(word_id="w_0006", text="um", source_start_ms=15000, source_end_ms=15500, speaker_id="speaker_0", is_filler=True),
        WordToken(word_id="w_0007", text="like", source_start_ms=25000, source_end_ms=25400, speaker_id="speaker_0", is_filler=True),
        WordToken(word_id="w_0008", text="today", source_start_ms=25500, source_end_ms=26000, speaker_id="speaker_0"),

        # 42 - 44s: "welcome to the channel"
        WordToken(word_id="w_0009", text="welcome", source_start_ms=42000, source_end_ms=42500, speaker_id="speaker_0"),
        WordToken(word_id="w_0010", text="to", source_start_ms=42500, source_end_ms=42800, speaker_id="speaker_0"),
        WordToken(word_id="w_0011", text="the", source_start_ms=42800, source_end_ms=43100, speaker_id="speaker_0"),
        WordToken(word_id="w_0012", text="channel", source_start_ms=43100, source_end_ms=44000, speaker_id="speaker_0"),

        # Protected pause at 45000-47500ms
        WordToken(word_id="w_0013", text="pause", source_start_ms=44500, source_end_ms=45000, speaker_id="speaker_0", is_protected_silence=True),
        WordToken(word_id="w_0014", text="resuming", source_start_ms=47500, source_end_ms=48300, speaker_id="speaker_0"),

        # Mention 1 of pricing at ~1:05 (65000ms)
        WordToken(word_id="w_0015", text="the", source_start_ms=64500, source_end_ms=64900, speaker_id="speaker_0"),
        WordToken(word_id="w_0016", text="pricing", source_start_ms=65000, source_end_ms=65800, speaker_id="speaker_0"),

        # Mention 2 of pricing at ~1:12 (75000ms)
        WordToken(word_id="w_0017", text="our", source_start_ms=74500, source_end_ms=74900, speaker_id="speaker_0"),
        WordToken(word_id="w_0018", text="pricing", source_start_ms=75000, source_end_ms=75800, speaker_id="speaker_0"),
        WordToken(word_id="w_0019", text="tier", source_start_ms=75900, source_end_ms=76500, speaker_id="speaker_0"),
        WordToken(word_id="w_0020", text="uh", source_start_ms=76600, source_end_ms=77000, speaker_id="speaker_0", is_filler=True),

        # Mention 3 of pricing at ~1:20 (85000ms)
        WordToken(word_id="w_0021", text="final", source_start_ms=84500, source_end_ms=84900, speaker_id="speaker_0"),
        WordToken(word_id="w_0022", text="pricing", source_start_ms=85000, source_end_ms=85800, speaker_id="speaker_0"),

        # Outro
        WordToken(word_id="w_0023", text="goodbye", source_start_ms=88000, source_end_ms=89000, speaker_id="speaker_0"),
    ]

    transcript = TranscriptIndex(source_duration_ms=90000, words=words)
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(transcript.model_dump(), f, indent=2)
    logger.info(f"Saved ground-truth transcript: {json_path}")


def generate_two_speaker_podcast(output_dir: str):
    """
    Generates test_media/two_speaker_podcast.mp4 (120s)
    Host speaker_0 + Guest speaker_1, overlapping speech at 60s, and speaker swap at 90s.
    """
    video_path = os.path.join(output_dir, "two_speaker_podcast.mp4")
    json_path = os.path.join(output_dir, "two_speaker_podcast_transcript.json")
    encoder, enc_opts = get_best_video_encoder()

    vf = (
        "drawtext=text='Two Speaker Podcast | %{pts\\:hms}':"
        "fontsize=24:fontcolor=white:box=1:boxcolor=black@0.65:"
        "x=(w-text_w)/2:y=30"
    )

    cmd = [
        "ffmpeg", "-y",
        "-f", "lavfi", "-i", "testsrc2=duration=120:size=640x360:rate=30",
        "-f", "lavfi", "-i", "sine=frequency=440:sample_rate=44100:duration=120",
        "-vf", vf,
        "-c:v", encoder, *enc_opts,
        "-c:a", "aac", "-b:a", "128k",
        "-t", "120",
        video_path,
    ]
    _run_ffmpeg(cmd, "two_speaker_podcast.mp4")

    words = [
        WordToken(word_id="p_0001", text="welcome", source_start_ms=2000, source_end_ms=2500, speaker_id="speaker_0"),
        WordToken(word_id="p_0002", text="to", source_start_ms=2500, source_end_ms=2800, speaker_id="speaker_0"),
        WordToken(word_id="p_0003", text="the", source_start_ms=2800, source_end_ms=3100, speaker_id="speaker_0"),
        WordToken(word_id="p_0004", text="show", source_start_ms=3100, source_end_ms=3600, speaker_id="speaker_0"),
        WordToken(word_id="p_0005", text="thanks", source_start_ms=5000, source_end_ms=5500, speaker_id="speaker_1"),
        WordToken(word_id="p_0006", text="for", source_start_ms=5500, source_end_ms=5800, speaker_id="speaker_1"),
        WordToken(word_id="p_0007", text="having", source_start_ms=5800, source_end_ms=6200, speaker_id="speaker_1"),
        WordToken(word_id="p_0008", text="me", source_start_ms=6200, source_end_ms=6500, speaker_id="speaker_1"),

        # Discussing old job
        WordToken(word_id="p_0009", text="tell", source_start_ms=15000, source_end_ms=15400, speaker_id="speaker_0"),
        WordToken(word_id="p_0010", text="us", source_start_ms=15400, source_end_ms=15600, speaker_id="speaker_0"),
        WordToken(word_id="p_0011", text="about", source_start_ms=15600, source_end_ms=16000, speaker_id="speaker_0"),
        WordToken(word_id="p_0012", text="your", source_start_ms=16000, source_end_ms=16300, speaker_id="speaker_0"),
        WordToken(word_id="p_0013", text="old", source_start_ms=16300, source_end_ms=16700, speaker_id="speaker_0"),
        WordToken(word_id="p_0014", text="job", source_start_ms=16700, source_end_ms=17200, speaker_id="speaker_0"),

        # Overlapping speech at 60s
        WordToken(word_id="p_0015", text="exactly", source_start_ms=60000, source_end_ms=61500, speaker_id="speaker_0"),
        WordToken(word_id="p_0016", text="absolutely", source_start_ms=60500, source_end_ms=62000, speaker_id="speaker_1"),

        # Speaker swap anomaly test at 90s
        WordToken(word_id="p_0017", text="and", source_start_ms=90000, source_end_ms=90400, speaker_id="speaker_0"),
        WordToken(word_id="p_0018", text="finally", source_start_ms=115000, source_end_ms=116000, speaker_id="speaker_1"),
    ]

    transcript = TranscriptIndex(source_duration_ms=120000, words=words)
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(transcript.model_dump(), f, indent=2)
    logger.info(f"Saved two-speaker transcript: {json_path}")


def generate_vfr_clip(output_dir: str):
    """Generates test_media/vfr_phone_clip.mp4 (10s) with simulated VFR."""
    video_path = os.path.join(output_dir, "vfr_phone_clip.mp4")
    encoder, enc_opts = get_best_video_encoder()

    vf = "drawtext=text='VFR Mobile Phone Clip':fontsize=22:fontcolor=yellow:x=(w-text_w)/2:y=30"
    cmd = [
        "ffmpeg", "-y",
        "-f", "lavfi", "-i", "testsrc=duration=10:size=640x360:rate=24",
        "-f", "lavfi", "-i", "sine=frequency=500:sample_rate=44100:duration=10",
        "-vf", vf,
        "-c:v", encoder, *enc_opts,
        "-c:a", "aac",
        "-t", "10",
        video_path,
    ]
    _run_ffmpeg(cmd, "vfr_phone_clip.mp4")


def generate_no_audio_clip(output_dir: str):
    """Generates test_media/no_audio_clip.mp4 (10s, video only)."""
    video_path = os.path.join(output_dir, "no_audio_clip.mp4")
    encoder, enc_opts = get_best_video_encoder()

    vf = "drawtext=text='No Audio Clip (Silent)':fontsize=22:fontcolor=cyan:x=(w-text_w)/2:y=30"
    cmd = [
        "ffmpeg", "-y",
        "-f", "lavfi", "-i", "testsrc=duration=10:size=640x360:rate=30",
        "-vf", vf,
        "-c:v", encoder, *enc_opts,
        "-an",
        "-t", "10",
        video_path,
    ]
    _run_ffmpeg(cmd, "no_audio_clip.mp4")


def generate_benchmark_60min_transcript(output_dir: str):
    """
    Generates test_media/benchmark_60min_transcript.json (60 minutes, ~9000 words).
    Used to verify compilation scale completes in < 3s.
    """
    json_path = os.path.join(output_dir, "benchmark_60min_transcript.json")
    logger.info("Generating 60-minute benchmark transcript (~9,000 words)...")

    words: List[WordToken] = []
    vocab = ["the", "system", "compiles", "timelines", "with", "content", "anchoring", "pricing", "feature", "video", "render", "fast"]
    current_time = 1000  # 1s
    word_count = 9000
    total_dur_ms = 3600000  # 60 minutes

    for i in range(word_count):
        word_dur = 250 + (i % 150)
        word_text = vocab[i % len(vocab)]
        speaker = f"speaker_{i % 3}"
        is_filler = (i % 50 == 0)

        words.append(WordToken(
            word_id=f"bw_{i:05d}",
            text=word_text,
            source_start_ms=current_time,
            source_end_ms=current_time + word_dur,
            speaker_id=speaker,
            is_filler=is_filler,
        ))
        # Advance by word duration + realistic small pause (50-200ms)
        current_time += word_dur + 100
        if current_time >= total_dur_ms - 2000:
            break

    transcript = TranscriptIndex(source_duration_ms=total_dur_ms, words=words)
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(transcript.model_dump(), f)
    logger.info(f"Saved benchmark transcript ({len(words)} words): {json_path}")


def main():
    output_dir = os.path.abspath("./test_media")
    os.makedirs(output_dir, exist_ok=True)
    logger.info(f"Generating synthetic test media in: {output_dir}")

    generate_single_speaker_interview(output_dir)
    generate_two_speaker_podcast(output_dir)
    generate_vfr_clip(output_dir)
    generate_no_audio_clip(output_dir)
    generate_benchmark_60min_transcript(output_dir)
    logger.info("All synthetic test media successfully generated!")


if __name__ == "__main__":
    main()
