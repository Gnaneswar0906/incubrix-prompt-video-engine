"""
IncuBrix Prompt-Based Video Editing Engine
Data Models (Pydantic v2)
"""

from __future__ import annotations

import re
from typing import Any, Dict, List, Literal, Optional, Tuple
from pydantic import BaseModel, Field, field_validator, model_validator


class WordToken(BaseModel):
    """
    Immutable content atom representing a single spoken word and its audio/temporal features.
    """
    word_id: str = Field(description="Unique deterministic identifier, e.g. w_0001")
    text: str = Field(description="Normalized word text")
    source_start_ms: int = Field(ge=0, description="Start timestamp in source media (integer milliseconds)")
    source_end_ms: int = Field(ge=0, description="End timestamp in source media (integer milliseconds)")
    speaker_id: Optional[str] = Field(default="speaker_0", description="Speaker identifier from diarization")
    confidence: float = Field(default=1.0, ge=0.0, le=1.0, description="ASR transcription confidence score")
    silence_before_ms: int = Field(default=0, ge=0, description="Duration of preceding silence in ms")
    silence_after_ms: int = Field(default=0, ge=0, description="Duration of following silence in ms")
    is_filler: bool = Field(default=False, description="Flag indicating filler word (um, uh, like, etc.)")
    is_protected_silence: bool = Field(default=False, description="Deliberate pause attached to this token")

    @field_validator("source_end_ms")
    @classmethod
    def validate_duration(cls, v: int, info) -> int:
        start = info.data.get("source_start_ms")
        if start is not None and v < start:
            raise ValueError(f"source_end_ms ({v}) cannot be less than source_start_ms ({start})")
        return v


class SourceSpan(BaseModel):
    """
    Continuous temporal span in untouched source media coordinates.
    """
    start_ms: int = Field(ge=0, description="Source start in milliseconds")
    end_ms: int = Field(ge=0, description="Source end in milliseconds")

    @field_validator("end_ms")
    @classmethod
    def validate_span(cls, v: int, info) -> int:
        start = info.data.get("start_ms")
        if start is not None and v < start:
            raise ValueError(f"end_ms ({v}) must be greater than or equal to start_ms ({start})")
        return v


OpType = Literal[
    "cut",
    "keep_only",
    "reorder",
    "speed",
    "mute",
    "bleep",
    "caption",
    "auto_caption",
    "remove_fillers",
    "remove_silences",
    "add_bgm",
    "undo",
    "redo",
    "restore_op",
    "style_caption",
    "protect_silence",
]


class EditOperation(BaseModel):
    """
    Content-anchored edit operation attached to immutable word_ids or source spans.
    """
    op_id: str = Field(description="Unique operation ID, e.g. op_001")
    op_type: OpType = Field(description="Type of editing operation")
    target_word_ids: List[str] = Field(default_factory=list, description="Target word identifiers")
    source_spans: List[SourceSpan] = Field(default_factory=list, description="Target source time intervals")
    params: Dict[str, Any] = Field(default_factory=dict, description="Operation-specific parameters")
    status: Literal["active", "undone"] = Field(default="active", description="Status in edit history")
    created_at_step: int = Field(default=0, ge=0, description="Instruction step sequence number")


class VideoSegment(BaseModel):
    """
    Renderable video playback interval on the compiled timeline.
    """
    segment_id: str
    source_start_ms: int = Field(ge=0)
    source_end_ms: int = Field(ge=0)
    timeline_start_ms: int = Field(ge=0)
    timeline_end_ms: int = Field(ge=0)
    speed: float = Field(gt=0.0, le=8.0, default=1.0)
    word_ids: List[str] = Field(default_factory=list)


class AudioSegment(BaseModel):
    """
    Renderable audio playback interval on the compiled timeline.
    """
    segment_id: str
    source_start_ms: int = Field(ge=0)
    source_end_ms: int = Field(ge=0)
    timeline_start_ms: int = Field(ge=0)
    timeline_end_ms: int = Field(ge=0)
    speed: float = Field(gt=0.0, le=8.0, default=1.0)
    is_muted: bool = False
    is_bleeped: bool = False
    volume: float = Field(ge=0.0, default=1.0)
    word_ids: List[str] = Field(default_factory=list)


class CaptionItem(BaseModel):
    """
    Caption item bound to immutable word_ids.
    """
    caption_id: str
    text: str
    timeline_start_ms: int = Field(ge=0)
    timeline_end_ms: int = Field(ge=0)
    bound_word_ids: List[str]
    style: Dict[str, Any] = Field(default_factory=dict)
    suppressed: bool = False


class BgmEnvelopePoint(BaseModel):
    """
    Single volume envelope keyframe for ducking background music.
    """
    timeline_ms: int = Field(ge=0)
    volume_db: float


class BgmTrack(BaseModel):
    """
    Background music track with dynamic speech ducking envelope.
    """
    track_id: str
    source_url: str
    volume: float = Field(ge=0.0, default=1.0)
    ducking_envelope: List[BgmEnvelopePoint] = Field(default_factory=list)


class CompiledTimeline(BaseModel):
    """
    Deterministic projected state of the edited timeline.
    """
    duration_ms: int = Field(ge=0)
    duration_s: float = Field(ge=0.0)
    video_segments: List[VideoSegment] = Field(default_factory=list)
    audio_segments: List[AudioSegment] = Field(default_factory=list)
    caption_tracks: List[CaptionItem] = Field(default_factory=list)
    bgm_tracks: List[BgmTrack] = Field(default_factory=list)
    timeline_hash: str = Field(description="Canonical SHA-256 hash")
    active_operation_ids: List[str] = Field(default_factory=list)
    warnings: List[str] = Field(default_factory=list)


class InstructionResponse(BaseModel):
    """
    Deterministic standard response returned for every editing instruction.
    """
    status: Literal["applied", "needs_clarification", "rejected"]
    operations: List[EditOperation] = Field(default_factory=list)
    summary: Dict[str, Any] = Field(
        default_factory=dict,
        description="Must include before/after duration, what moved, and time_policy: 'current_timeline_time'",
    )
    question: Optional[str] = None
    options: List[str] = Field(default_factory=list)
    warnings: List[str] = Field(default_factory=list)
    timeline_hash: Optional[str] = None
    duration_s: float = Field(default=0.0, ge=0.0)

    @model_validator(mode="after")
    def ensure_time_policy(self) -> InstructionResponse:
        if self.status == "applied":
            if "time_policy" not in self.summary:
                self.summary["time_policy"] = "current_timeline_time"
        return self


class TranscriptIndex(BaseModel):
    """
    Immutable indexed representation of the original video's speech and temporal tokens.
    """
    source_duration_ms: int = Field(ge=0)
    words: List[WordToken] = Field(default_factory=list)

    def get_word(self, word_id: str) -> Optional[WordToken]:
        for w in self.words:
            if w.word_id == word_id:
                return w
        return None

    def words_in_range(self, start_ms: int, end_ms: int) -> List[WordToken]:
        """Returns words whose temporal bounds intersect [start_ms, end_ms]."""
        matches = []
        for w in self.words:
            if max(w.source_start_ms, start_ms) < min(w.source_end_ms, end_ms):
                matches.append(w)
        return matches

    def find_phrases(self, pattern: str) -> List[List[WordToken]]:
        """
        Case-insensitive phrase search returning token lists for each occurrence.
        """
        norm_pat = re.sub(r"[^\w\s]", "", pattern.strip().lower())
        pat_words = norm_pat.split()
        if not pat_words:
            return []

        results: List[List[WordToken]] = []
        n = len(pat_words)
        total = len(self.words)

        for i in range(total - n + 1):
            sub = self.words[i : i + n]
            cleaned_sub = [re.sub(r"[^\w\s]", "", w.text.strip().lower()) for w in sub]
            if cleaned_sub == pat_words:
                results.append(sub)

        return results

    def find_fillers(self) -> List[WordToken]:
        """Returns all tokens flagged as filler words."""
        return [w for w in self.words if w.is_filler]

    def snap_to_silence(self, start_ms: int, end_ms: int, window_ms: int = 300) -> Tuple[int, int]:
        """
        Imperfect data defense: snap cut boundaries to adjacent silence so words are not clipped.
        """
        snapped_start = start_ms
        snapped_end = end_ms

        # Check word boundaries near start
        for w in self.words:
            if abs(w.source_start_ms - start_ms) <= window_ms and w.silence_before_ms > 50:
                snapped_start = w.source_start_ms
                break

        # Check word boundaries near end
        for w in self.words:
            if abs(w.source_end_ms - end_ms) <= window_ms and w.silence_after_ms > 50:
                snapped_end = w.source_end_ms
                break

        return snapped_start, snapped_end
