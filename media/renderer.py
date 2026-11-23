"""
IncuBrix Prompt-Based Video Editing Engine
Timeline Renderer (Single-Pass FFmpeg Filtergraph, Frame Quantization, Bleep Tone, Subtitles, BGM Ducking)
"""

from __future__ import annotations

import logging
import os
import subprocess
from typing import List, Optional, Tuple
from engine.models import CaptionItem, CompiledTimeline
from media.intake import inspect_media, get_best_video_encoder

logger = logging.getLogger("incubrix.media.renderer")


class TimelineRenderer:
    """
    Renders CompiledTimeline separately from untouched source media
    using a single-pass frame-accurate FFmpeg filtergraph.
    """

    def __init__(self, fps: float = 30.0):
        self.fps = fps

    def quantize_time_s(self, ms: int) -> float:
        """
        Quantizes millisecond timestamps to exact video frame ticks.
        round(ms * fps / 1000) / fps
        """
        frame_idx = round((ms * self.fps) / 1000.0)
        return frame_idx / self.fps

    def render(
        self,
        timeline: CompiledTimeline,
        source_media_path: str,
        output_path: str,
        video_fps: Optional[float] = None,
    ) -> str:
        """
        Builds single-pass filtergraph and executes FFmpeg to produce the final video.
        Guarantees A/V sync <= 1 frame and total length <= 1 frame.
        """
        fps = video_fps or self.fps
        os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)

        # Inspect source media to ensure audio is present
        meta = inspect_media(source_media_path)
        actual_fps = meta.fps or fps

        # Build FFmpeg command and filtergraph
        cmd, filtergraph, ass_path = self._build_ffmpeg_command(
            timeline=timeline,
            source_path=source_media_path,
            output_path=output_path,
            fps=actual_fps,
            has_source_audio=meta.has_audio,
        )

        logger.info(f"Rendering timeline to {output_path} with filtergraph:\n{filtergraph}")

        try:
            proc = subprocess.run(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                check=True,
            )
        except subprocess.CalledProcessError as e:
            logger.error(f"FFmpeg rendering failed: {e.stderr}")
            raise RuntimeError(f"FFmpeg render failed with exit code {e.returncode}:\n{e.stderr}")
        finally:
            # Clean up temporary subtitle file if created
            if ass_path and os.path.exists(ass_path):
                try:
                    os.remove(ass_path)
                except OSError:
                    pass

        return output_path

    # -------------------------------------------------------------------------
    # Filtergraph Construction
    # -------------------------------------------------------------------------

    def _build_ffmpeg_command(
        self,
        timeline: CompiledTimeline,
        source_path: str,
        output_path: str,
        fps: float,
        has_source_audio: bool,
    ) -> Tuple[List[str], str, Optional[str]]:
        """
        Constructs the complete FFmpeg command array and filter_complex string.
        """
        video_segs = timeline.video_segments
        audio_segs = timeline.audio_segments
        bgm_tracks = [t for t in timeline.bgm_tracks if os.path.exists(t.source_url)]

        inputs = ["-i", source_path]
        bgm_input_idx: Optional[int] = None

        if bgm_tracks:
            bgm_input_idx = 1
            inputs.extend(["-i", bgm_tracks[0].source_url])

        filters: List[str] = []

        # 1. Video Filter Segments (Trim + SetPTS)
        for idx, v_seg in enumerate(video_segs):
            s_s = self.quantize_time_s(v_seg.source_start_ms)
            e_s = self.quantize_time_s(v_seg.source_end_ms)
            speed = max(0.1, min(8.0, v_seg.speed))
            pts_mult = 1.0 / speed

            filters.append(
                f"[0:v]trim=start={s_s:.6f}:end={e_s:.6f},setpts=(PTS-STARTPTS)*{pts_mult:.6f}[v{idx}]"
            )

        # Concatenate video segments
        v_concat_inputs = "".join(f"[v{i}]" for i in range(len(video_segs)))
        filters.append(f"{v_concat_inputs}concat=n={len(video_segs)}:v=1:a=0[vcat]")
        v_final_label = "[vcat]"

        # 2. Subtitles Overlay (Burn-in styled ASS subtitles or drawtext)
        active_captions = [c for c in timeline.caption_tracks if not c.suppressed]
        ass_path = None

        if active_captions:
            ass_path = os.path.abspath(f"{output_path}.temp_subs.ass")
            self._write_ass_subtitle_file(active_captions, ass_path)
            # Use escaped ASS path for FFmpeg filter
            escaped_ass = ass_path.replace("\\", "/").replace(":", "\\:")
            filters.append(f"{v_final_label}ass='{escaped_ass}'[vsub]")
            v_final_label = "[vsub]"

        # 3. Audio Filter Segments (Trim + Speed + Mute + Bleep)
        if not has_source_audio:
            # Generate silent audio if source had no audio
            total_dur_s = timeline.duration_s
            filters.append(
                f"aevalsrc=0:d={total_dur_s:.6f}:s=44100[acat]"
            )
        else:
            for idx, a_seg in enumerate(audio_segs):
                s_s = self.quantize_time_s(a_seg.source_start_ms)
                e_s = self.quantize_time_s(a_seg.source_end_ms)
                dur_s = max(0.01, e_s - s_s)

                if a_seg.is_bleeped:
                    # Synthesize 1000 Hz sine wave bleep tone
                    filters.append(
                        f"sine=frequency=1000:duration={dur_s:.6f},asetpts=PTS-STARTPTS[a{idx}]"
                    )
                else:
                    audio_filters: List[str] = [f"atrim=start={s_s:.6f}:end={e_s:.6f}", "asetpts=PTS-STARTPTS"]

                    # Chain atempo filters cleanly for speed adjustments
                    speed = max(0.1, min(8.0, a_seg.speed))
                    if abs(speed - 1.0) > 1e-4:
                        audio_filters.append(self._build_atempo_chain(speed))

                    # Mute or volume scaling
                    if a_seg.is_muted:
                        audio_filters.append("volume=0.0")
                    elif abs(a_seg.volume - 1.0) > 1e-4:
                        audio_filters.append(f"volume={a_seg.volume:.4f}")

                    f_str = ",".join(audio_filters)
                    filters.append(f"[0:a]{f_str}[a{idx}]")

            # Concatenate audio segments
            a_concat_inputs = "".join(f"[a{i}]" for i in range(len(audio_segs)))
            filters.append(f"{a_concat_inputs}concat=n={len(audio_segs)}:v=0:a=1[acat]")

        a_final_label = "[acat]"

        # 4. Background Music (BGM) Sidechain Ducking
        if bgm_input_idx is not None and bgm_tracks:
            bgm = bgm_tracks[0]
            # Trim BGM to exact timeline length and apply volume + sidechain compression
            filters.append(
                f"[{bgm_input_idx}:a]atrim=0:{timeline.duration_s:.6f},asetpts=PTS-STARTPTS,volume={bgm.volume:.4f}[bgm_vol];"
                f"[bgm_vol][acat]sidechaincompress=threshold=0.15:ratio=4:attack=50:release=300[bgm_ducked];"
                f"[acat][bgm_ducked]amix=inputs=2:duration=first:dropout_transition=0[aout]"
            )
            a_final_label = "[aout]"

        full_filtergraph = ";\n".join(filters)

        encoder, enc_opts = get_best_video_encoder()
        cmd = [
            "ffmpeg",
            "-y",
            *inputs,
            "-filter_complex", full_filtergraph,
            "-map", v_final_label,
            "-map", a_final_label,
            "-c:v", encoder,
            *enc_opts,
            "-c:a", "aac",
            "-b:a", "192k",
            "-r", str(fps),
            "-t", f"{timeline.duration_s:.6f}",
            "-movflags", "+faststart",
            output_path,
        ]

        return cmd, full_filtergraph, ass_path

    # -------------------------------------------------------------------------
    # Helper Generators
    # -------------------------------------------------------------------------

    def _build_atempo_chain(self, speed: float) -> str:
        """
        Chains FFmpeg atempo filters (each within 0.5x to 2.0x) for any speed factor.
        Example: 4.0x -> atempo=2.0,atempo=2.0
        Example: 0.25x -> atempo=0.5,atempo=0.5
        """
        factors: List[float] = []
        rem = speed

        while rem > 2.0:
            factors.append(2.0)
            rem /= 2.0
        while rem < 0.5:
            factors.append(0.5)
            rem /= 0.5
        factors.append(round(rem, 4))

        return ",".join(f"atempo={f:.4f}" for f in factors)

    def _write_ass_subtitle_file(self, captions: List[CaptionItem], ass_path: str) -> None:
        """
        Generates an Advanced SubStation Alpha (.ass) subtitle file.
        Enforces font styling and colors cleanly.
        """
        header = """[Script Info]
ScriptType: v4.00+
PlayResX: 1920
PlayResY: 1080

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Default,Arial,48,&H00FFFFFF,&H000000FF,&H00000000,&H80000000,-1,0,0,0,100,100,0,0,1,3,2,2,40,40,60,1
Style: RedCaption,Arial,48,&H000000FF,&H000000FF,&H00000000,&H80000000,-1,0,0,0,100,100,0,0,1,3,2,2,40,40,60,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""
        events: List[str] = []
        for cap in captions:
            s_str = self._ms_to_ass_time(cap.timeline_start_ms)
            e_str = self._ms_to_ass_time(cap.timeline_end_ms)
            style_name = "RedCaption" if cap.style.get("color") == "red" else "Default"
            events.append(f"Dialogue: 0,{s_str},{e_str},{style_name},,0,0,0,,{cap.text}")

        with open(ass_path, "w", encoding="utf-8") as f:
            f.write(header + "\n".join(events) + "\n")

    def _ms_to_ass_time(self, ms: int) -> str:
        """Converts milliseconds to ASS timestamp format: H:MM:SS.cc"""
        total_cs = ms // 10
        cs = total_cs % 100
        total_s = total_cs // 100
        s = total_s % 60
        total_m = total_s // 60
        m = total_m % 60
        h = total_m // 60
        return f"{h}:{m:02d}:{s:02d}.{cs:02d}"
