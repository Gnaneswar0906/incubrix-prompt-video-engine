"""
IncuBrix Prompt-Based Video Editing Engine
Media Intake & Inspection (ffprobe, VFR detection, CFR normalization, no-audio handling)
"""

from __future__ import annotations

import json
import logging
import os
import shutil
import subprocess
from typing import List, Optional
from pydantic import BaseModel, Field

logger = logging.getLogger("incubrix.media.intake")


class VideoMetadata(BaseModel):
    """
    Standard media metadata extracted from MP4 / MOV container.
    """
    duration_ms: int = Field(ge=0, description="Duration in integer milliseconds")
    duration_s: float = Field(ge=0.0, description="Duration in seconds")
    fps: float = Field(gt=0.0, description="Video frame rate")
    width: int = Field(ge=0, description="Horizontal frame resolution")
    height: int = Field(ge=0, description="Vertical frame resolution")
    video_codec: str = Field(default="h264")
    audio_codec: Optional[str] = None
    is_vfr: bool = Field(default=False, description="True if variable frame rate detected")
    has_audio: bool = Field(default=True, description="True if audio stream present")
    audio_sample_rate: Optional[int] = None
    audio_channels: Optional[int] = None
    warnings: List[str] = Field(default_factory=list)


def inspect_media(media_path: str) -> VideoMetadata:
    """
    Inspects MP4/MOV container using ffprobe.
    Extracts frame rate, duration, resolution, audio tracks, and flags VFR/no-audio.
    """
    if not os.path.exists(media_path):
        raise FileNotFoundError(f"Media file not found: {media_path}")

    ffprobe_cmd = [
        "ffprobe",
        "-v", "quiet",
        "-print_format", "json",
        "-show_format",
        "-show_streams",
        media_path,
    ]

    try:
        proc = subprocess.run(
            ffprobe_cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            check=True,
        )
        data = json.loads(proc.stdout)
    except Exception as e:
        logger.error(f"Failed to execute ffprobe on {media_path}: {e}")
        raise RuntimeError(f"ffprobe media inspection failed: {e}")

    format_info = data.get("format", {})
    streams = data.get("streams", [])

    video_stream = next((s for s in streams if s.get("codec_type") == "video"), None)
    audio_stream = next((s for s in streams if s.get("codec_type") == "audio"), None)

    if not video_stream:
        raise ValueError(f"No video stream found in {media_path}")

    # Parse duration
    dur_s = float(format_info.get("duration") or video_stream.get("duration") or 0.0)
    dur_ms = int(round(dur_s * 1000))

    # Parse resolution
    width = int(video_stream.get("width", 0))
    height = int(video_stream.get("height", 0))
    video_codec = video_stream.get("codec_name", "h264")

    # Parse frame rate
    r_fps_str = video_stream.get("r_frame_rate", "30/1")
    avg_fps_str = video_stream.get("avg_frame_rate", "30/1")

    def _eval_ratio(r_str: str) -> float:
        if "/" in r_str:
            num, den = r_str.split("/")
            return float(num) / float(den) if float(den) != 0 else 30.0
        return float(r_str)

    r_fps = _eval_ratio(r_fps_str)
    avg_fps = _eval_ratio(avg_fps_str)
    fps = round(avg_fps if avg_fps > 0 else (r_fps if r_fps > 0 else 30.0), 3)

    # Detect Variable Frame Rate (VFR)
    warnings: List[str] = []
    is_vfr = False
    if r_fps > 0 and avg_fps > 0:
        ratio_diff = abs(r_fps - avg_fps)
        if ratio_diff > 0.05 and (ratio_diff / avg_fps) > 0.01:
            is_vfr = True
            warnings.append(
                f"Variable Frame Rate (VFR) detected (r_fps={r_fps:.2f}, avg_fps={avg_fps:.2f}). Normalization recommended."
            )

    # Parse audio track
    has_audio = audio_stream is not None
    audio_codec = None
    audio_sample_rate = None
    audio_channels = None

    if has_audio:
        audio_codec = audio_stream.get("codec_name")
        sr_val = audio_stream.get("sample_rate")
        audio_sample_rate = int(sr_val) if sr_val else None
        audio_channels = audio_stream.get("channels")
    else:
        warnings.append(
            "Video contains no audio stream. Silent audio track will be synthesized if audio operations are applied."
        )

    return VideoMetadata(
        duration_ms=dur_ms,
        duration_s=dur_s,
        fps=fps,
        width=width,
        height=height,
        video_codec=video_codec,
        audio_codec=audio_codec,
        is_vfr=is_vfr,
        has_audio=has_audio,
        audio_sample_rate=audio_sample_rate,
        audio_channels=audio_channels,
        warnings=warnings,
    )


def get_best_video_encoder() -> Tuple[str, List[str]]:
    """Returns the best available video encoder and encoding quality options."""
    try:
        proc = subprocess.run(["ffmpeg", "-encoders"], capture_output=True, text=True)
        out = proc.stdout
        if "libopenh264" in out:
            return "libopenh264", ["-b:v", "2M"]
        if "h264_mf" in out:
            return "h264_mf", ["-b:v", "2M"]
        if "libx264" in out:
            return "libx264", ["-preset", "ultrafast", "-crf", "18"]
        if "mpeg4" in out:
            return "mpeg4", ["-qscale:v", "3"]
    except Exception:
        pass
    return "libopenh264", ["-b:v", "2M"]


def normalize_vfr_to_cfr(
    input_path: str,
    output_path: str,
    target_fps: float = 30.0,
) -> str:
    """
    Transcodes Variable Frame Rate (VFR) video into Constant Frame Rate (CFR)
    using frame-accurate FFmpeg timestamp resampling.
    """
    os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)
    meta = inspect_media(input_path)

    if not meta.is_vfr and abs(meta.fps - target_fps) < 0.01:
        # Already constant frame rate
        shutil.copy2(input_path, output_path)
        return output_path

    encoder, enc_opts = get_best_video_encoder()
    cmd = [
        "ffmpeg",
        "-y",
        "-i", input_path,
        "-vf", f"fps=fps={target_fps}",
        "-vsync", "cfr",
        "-c:v", encoder,
        *enc_opts,
    ]

    if meta.has_audio:
        cmd.extend(["-c:a", "aac", "-b:a", "192k"])
    else:
        cmd.extend(["-an"])

    cmd.append(output_path)

    try:
        subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True)
    except subprocess.CalledProcessError as e:
        logger.error(f"FFmpeg CFR normalization failed: {e.stderr.decode()}")
        raise RuntimeError(f"CFR normalization failed: {e.stderr.decode()}")

    return output_path


def ensure_audio_stream(
    input_path: str,
    output_path: str,
    duration_s: float,
) -> str:
    """
    If the video has no audio, synthesizes a synchronized silent audio track
    so filtergraph pipelines process audio/video synchronously without error.
    """
    meta = inspect_media(input_path)
    if meta.has_audio:
        return input_path

    os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)
    cmd = [
        "ffmpeg",
        "-y",
        "-i", input_path,
        "-f", "lavfi",
        "-t", str(duration_s),
        "-i", "anullsrc=channel_layout=stereo:sample_rate=44100",
        "-c:v", "copy",
        "-c:a", "aac",
        "-shortest",
        output_path,
    ]

    try:
        subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True)
    except subprocess.CalledProcessError as e:
        raise RuntimeError(f"Failed to generate synthetic silent audio: {e.stderr.decode()}")

    return output_path
