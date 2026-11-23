"""
IncuBrix Prompt-Based Video Editing Engine
Base Abstract Adapters for STT, VAD, Diarization, Semantic Search, and Intent Parsing
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional, Tuple
from engine.models import CompiledTimeline, TranscriptIndex, WordToken


class STTVADAdapter(ABC):
    """
    Abstract adapter for Speech-To-Text (STT) and Voice Activity Detection (VAD).
    Extracts word tokens with millisecond timestamps, confidence scores, and silence intervals.
    """

    @abstractmethod
    def transcribe(
        self,
        audio_path: str,
        video_duration_ms: Optional[int] = None,
    ) -> Tuple[TranscriptIndex, List[str]]:
        """
        Transcribes speech from audio media and detects silence intervals.
        Returns:
            (TranscriptIndex, warnings_list)
        """
        pass

    def snap_boundary_to_silence(
        self,
        target_ms: int,
        words: List[WordToken],
        max_window_ms: int = 120,
    ) -> int:
        """
        Snaps a cut boundary timestamp to the nearest silence interval within ±120 ms
        so zero spoken words are clipped.
        """
        best_ms = target_ms
        min_distance = max_window_ms + 1

        for w in words:
            # Check silence preceding the word
            if w.silence_before_ms > 40:
                dist = abs(w.source_start_ms - target_ms)
                if dist <= max_window_ms and dist < min_distance:
                    min_distance = dist
                    best_ms = w.source_start_ms

            # Check silence following the word
            if w.silence_after_ms > 40:
                dist = abs(w.source_end_ms - target_ms)
                if dist <= max_window_ms and dist < min_distance:
                    min_distance = dist
                    best_ms = w.source_end_ms

        return best_ms


class DiarizationAdapter(ABC):
    """
    Abstract adapter for speaker diarization and voice clustering.
    Identifies speakers, overlapping speech, and speaker-label swap anomalies.
    """

    @abstractmethod
    def diarize(
        self,
        audio_path: str,
        transcript: TranscriptIndex,
    ) -> Tuple[TranscriptIndex, List[str]]:
        """
        Enriches transcript words with speaker_id and detects audio anomalies.
        Returns:
            (Enriched TranscriptIndex, warnings_list)
        """
        pass


class SemanticSearchAdapter(ABC):
    """
    Abstract adapter for semantic embedding search across transcript text.
    Enables concept-based matching (e.g. 'pricing' -> 'cost', 'subscription').
    """

    @abstractmethod
    def find_semantic_matches(
        self,
        query: str,
        transcript: TranscriptIndex,
        similarity_threshold: float = 0.65,
    ) -> List[Dict[str, Any]]:
        """
        Searches transcript for semantic matches to query phrase.
        Returns list of matches:
            [{"word_ids": [...], "text": "...", "start_ms": int, "end_ms": int, "score": float, "display_option": str}]
        """
        pass


class IntentParserAdapter(ABC):
    """
    Abstract adapter for translating natural language user commands into structured
    editing operation intent dictionaries.
    Strict rule: Never lets an LLM directly calculate or mutate timeline state.
    """

    @abstractmethod
    def parse_intent(
        self,
        prompt: str,
        transcript: TranscriptIndex,
        current_timeline: CompiledTimeline,
    ) -> List[Dict[str, Any]]:
        """
        Parses text prompt into structured operation dicts conforming to timeline operations schema.
        """
        pass
