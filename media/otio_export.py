"""
IncuBrix Prompt-Based Video Editing Engine
OpenTimelineIO (.otio) Export
Enables exporting CompiledTimeline to professional NLEs (Premiere, Resolve, Final Cut Pro)
"""

from __future__ import annotations

import json
import logging
import os
from typing import Optional
from engine.models import CompiledTimeline

logger = logging.getLogger("incubrix.media.otio_export")


def export_to_otio(
    timeline: CompiledTimeline,
    output_path: str,
    source_media_path: Optional[str] = None,
    fps: float = 30.0,
) -> str:
    """
    Exports CompiledTimeline into a standardized OpenTimelineIO (.otio) project file.
    Includes Video Track, Audio Track, BGM Track, and Caption Markers.
    """
    os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)
    media_url = source_media_path or "source_video.mp4"

    try:
        import opentimelineio as otio
    except ImportError:
        logger.warning("opentimelineio package not installed; generating canonical OTIO JSON representation.")
        return _export_otio_json_fallback(timeline, output_path, media_url, fps)

    otio_timeline = otio.schema.Timeline(
        name="IncuBrix_Edited_Timeline",
        global_start_time=otio.opentime.RationalTime(0, fps),
    )

    # 1. Video Track
    video_track = otio.schema.Track(
        name="Video Track",
        kind=otio.schema.TrackKind.Video,
    )

    for seg in timeline.video_segments:
        start_frame = round((seg.source_start_ms * fps) / 1000.0)
        dur_frames = max(1, round(((seg.source_end_ms - seg.source_start_ms) * fps) / 1000.0))

        source_range = otio.opentime.TimeRange(
            start_time=otio.opentime.RationalTime(start_frame, fps),
            duration=otio.opentime.RationalTime(dur_frames, fps),
        )

        clip = otio.schema.Clip(
            name=seg.segment_id,
            media_reference=otio.schema.ExternalReference(target_url=media_url),
            source_range=source_range,
        )
        video_track.append(clip)

    otio_timeline.tracks.append(video_track)

    # 2. Audio Track
    audio_track = otio.schema.Track(
        name="Audio Track",
        kind=otio.schema.TrackKind.Audio,
    )

    for seg in timeline.audio_segments:
        start_frame = round((seg.source_start_ms * fps) / 1000.0)
        dur_frames = max(1, round(((seg.source_end_ms - seg.source_start_ms) * fps) / 1000.0))

        source_range = otio.opentime.TimeRange(
            start_time=otio.opentime.RationalTime(start_frame, fps),
            duration=otio.opentime.RationalTime(dur_frames, fps),
        )

        clip = otio.schema.Clip(
            name=seg.segment_id,
            media_reference=otio.schema.ExternalReference(target_url=media_url),
            source_range=source_range,
        )

        if seg.is_bleeped:
            clip.markers.append(
                otio.schema.Marker(
                    name="Bleep",
                    marked_range=otio.opentime.TimeRange(
                        start_time=otio.opentime.RationalTime(0, fps),
                        duration=otio.opentime.RationalTime(dur_frames, fps),
                    ),
                    color=otio.schema.MarkerColor.RED,
                )
            )
        elif seg.is_muted:
            clip.markers.append(
                otio.schema.Marker(
                    name="Mute",
                    marked_range=otio.opentime.TimeRange(
                        start_time=otio.opentime.RationalTime(0, fps),
                        duration=otio.opentime.RationalTime(dur_frames, fps),
                    ),
                    color=otio.schema.MarkerColor.BLACK,
                )
            )

        audio_track.append(clip)

    otio_timeline.tracks.append(audio_track)

    # 3. Background Music (BGM) Track
    if timeline.bgm_tracks:
        bgm_track = otio.schema.Track(
            name="BGM Track",
            kind=otio.schema.TrackKind.Audio,
        )
        for bgm in timeline.bgm_tracks:
            dur_frames = round((timeline.duration_ms * fps) / 1000.0)
            bgm_clip = otio.schema.Clip(
                name=bgm.track_id,
                media_reference=otio.schema.ExternalReference(target_url=bgm.source_url),
                source_range=otio.opentime.TimeRange(
                    start_time=otio.opentime.RationalTime(0, fps),
                    duration=otio.opentime.RationalTime(dur_frames, fps),
                ),
            )
            bgm_track.append(bgm_clip)
        otio_timeline.tracks.append(bgm_track)

    # 4. Caption Markers
    for cap in timeline.caption_tracks:
        if not cap.suppressed:
            start_frame = round((cap.timeline_start_ms * fps) / 1000.0)
            dur_frames = max(1, round(((cap.timeline_end_ms - cap.timeline_start_ms) * fps) / 1000.0))
            marker = otio.schema.Marker(
                name=f"Caption: {cap.text}",
                marked_range=otio.opentime.TimeRange(
                    start_time=otio.opentime.RationalTime(start_frame, fps),
                    duration=otio.opentime.RationalTime(dur_frames, fps),
                ),
                color=otio.schema.MarkerColor.YELLOW,
            )
            video_track.markers.append(marker)

    otio.adapters.write_to_file(otio_timeline, output_path)
    logger.info(f"Successfully exported OpenTimelineIO project to {output_path}")
    return output_path


def _export_otio_json_fallback(
    timeline: CompiledTimeline,
    output_path: str,
    media_url: str,
    fps: float,
) -> str:
    """
    Fallback JSON exporter conforming to OTIO schema 1.0 when opentimelineio is not installed.
    """
    data = {
        "OTIO_SCHEMA": "Timeline.1",
        "name": "IncuBrix_Edited_Timeline",
        "global_start_time": {"value": 0, "rate": fps},
        "metadata": {
            "incubrix_timeline_hash": timeline.timeline_hash,
            "duration_ms": timeline.duration_ms,
        },
        "tracks": {
            "OTIO_SCHEMA": "Stack.1",
            "children": [
                {
                    "OTIO_SCHEMA": "Track.1",
                    "name": "Video Track",
                    "kind": "Video",
                    "children": [
                        {
                            "OTIO_SCHEMA": "Clip.1",
                            "name": seg.segment_id,
                            "source_range": {
                                "start_time": {"value": round((seg.source_start_ms * fps) / 1000.0), "rate": fps},
                                "duration": {"value": max(1, round(((seg.source_end_ms - seg.source_start_ms) * fps) / 1000.0)), "rate": fps},
                            },
                        }
                        for seg in timeline.video_segments
                    ],
                },
                {
                    "OTIO_SCHEMA": "Track.1",
                    "name": "Audio Track",
                    "kind": "Audio",
                    "children": [
                        {
                            "OTIO_SCHEMA": "Clip.1",
                            "name": seg.segment_id,
                            "source_range": {
                                "start_time": {"value": round((seg.source_start_ms * fps) / 1000.0), "rate": fps},
                                "duration": {"value": max(1, round(((seg.source_end_ms - seg.source_start_ms) * fps) / 1000.0)), "rate": fps},
                            },
                        }
                        for seg in timeline.audio_segments
                    ],
                },
            ],
        },
    }

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)

    return output_path
