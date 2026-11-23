"""
IncuBrix Prompt-Based Video Editing Engine
Mock Adapters for 100% Deterministic, Offline, Zero-API-Key Execution
"""

from __future__ import annotations

import copy
import re
from typing import Any, Dict, List, Optional, Tuple
from adapters.base import (
    DiarizationAdapter,
    IntentParserAdapter,
    SemanticSearchAdapter,
    STTVADAdapter,
)
from engine.models import CompiledTimeline, TranscriptIndex, WordToken


class MockSTTVADAdapter(STTVADAdapter):
    """
    Mock STT and VAD adapter providing deterministic word token sequences,
    silence detection, ±120ms boundary snapping, and low-confidence flagging.
    """

    def __init__(self, synthetic_words: Optional[List[WordToken]] = None):
        if synthetic_words is not None:
            self.synthetic_words = synthetic_words
        else:
            # Default realistic transcript (120s) with 3 pricing mentions, fillers, and pauses
            self.synthetic_words = [
                WordToken(word_id="w_0001", text="hello", source_start_ms=5000, source_end_ms=5500, speaker_id="speaker_0"),
                WordToken(word_id="w_0002", text="and", source_start_ms=5500, source_end_ms=5800, speaker_id="speaker_0"),
                WordToken(word_id="w_0003", text="start", source_start_ms=5800, source_end_ms=6400, speaker_id="speaker_0"),
                WordToken(word_id="w_0004", text="our", source_start_ms=6400, source_end_ms=6800, speaker_id="speaker_0"),
                WordToken(word_id="w_0005", text="video", source_start_ms=6800, source_end_ms=7500, speaker_id="speaker_0"),
                WordToken(word_id="w_0006", text="um", source_start_ms=15000, source_end_ms=15500, speaker_id="speaker_0", is_filler=True),
                WordToken(word_id="w_0017", text="welcome", source_start_ms=42000, source_end_ms=42500, speaker_id="speaker_0"),
                WordToken(word_id="w_0018", text="to", source_start_ms=42500, source_end_ms=42800, speaker_id="speaker_0"),
                WordToken(word_id="w_0019", text="the", source_start_ms=42800, source_end_ms=43100, speaker_id="speaker_0"),
                WordToken(word_id="w_0020", text="channel", source_start_ms=43100, source_end_ms=44000, speaker_id="speaker_0"),
                WordToken(word_id="w_0021", text="pause", source_start_ms=44500, source_end_ms=45000, speaker_id="speaker_0", is_protected_silence=True),
                WordToken(word_id="w_0022", text="afterpause", source_start_ms=47500, source_end_ms=48500, speaker_id="speaker_0"),
                WordToken(word_id="w_0023", text="beforegap", source_start_ms=49000, source_end_ms=50000, speaker_id="speaker_0"),
                WordToken(word_id="w_0024", text="aftergap", source_start_ms=52500, source_end_ms=53500, speaker_id="speaker_0"),
                WordToken(word_id="w_0007", text="the", source_start_ms=64500, source_end_ms=64900, speaker_id="speaker_0"),
                WordToken(word_id="w_0008", text="pricing", source_start_ms=65000, source_end_ms=65800, speaker_id="speaker_0"),
                WordToken(word_id="w_0009", text="our", source_start_ms=74500, source_end_ms=74900, speaker_id="speaker_0"),
                WordToken(word_id="w_0010", text="pricing", source_start_ms=75000, source_end_ms=75800, speaker_id="speaker_0"),
                WordToken(word_id="w_0011", text="tier", source_start_ms=75900, source_end_ms=76500, speaker_id="speaker_0"),
                WordToken(word_id="w_0012", text="uh", source_start_ms=76600, source_end_ms=77000, speaker_id="speaker_0", is_filler=True),
                WordToken(word_id="w_0013", text="final", source_start_ms=84500, source_end_ms=84900, speaker_id="speaker_0"),
                WordToken(word_id="w_0014", text="pricing", source_start_ms=85000, source_end_ms=85800, speaker_id="speaker_0"),
                WordToken(word_id="w_0025", text="goodbye", source_start_ms=115000, source_end_ms=116000, speaker_id="speaker_0"),
            ]

    def transcribe(
        self,
        audio_path: str,
        video_duration_ms: Optional[int] = None,
    ) -> Tuple[TranscriptIndex, List[str]]:
        warnings: List[str] = []
        words = copy.deepcopy(self.synthetic_words)

        # Flag low-confidence words (< 0.65) with warnings instead of blindly bleeping
        for w in words:
            if w.confidence < 0.65:
                warnings.append(
                    f"Low confidence ({w.confidence:.2f}) on word '{w.text}' ({w.word_id}) at {w.source_start_ms}ms."
                )

        total_dur = video_duration_ms or (words[-1].source_end_ms + 1000 if words else 60000)
        index = TranscriptIndex(source_duration_ms=total_dur, words=words)
        return index, warnings


class MockDiarizationAdapter(DiarizationAdapter):
    """
    Mock speaker diarization adapter with overlapping-speech and speaker-swap anomaly detection.
    """

    def diarize(
        self,
        audio_path: str,
        transcript: TranscriptIndex,
    ) -> Tuple[TranscriptIndex, List[str]]:
        warnings: List[str] = []
        words = transcript.words

        # Check for overlapping speech: multiple words with different speakers overlapping temporally
        for i in range(len(words) - 1):
            w1 = words[i]
            w2 = words[i + 1]
            if w1.speaker_id and w2.speaker_id and w1.speaker_id != w2.speaker_id:
                # If they temporally overlap
                if max(w1.source_start_ms, w2.source_start_ms) < min(w1.source_end_ms, w2.source_end_ms):
                    warnings.append(
                        f"Overlapping speech detected between {w1.speaker_id} and {w2.speaker_id} at {w2.source_start_ms}ms."
                    )

        # Check for speaker-label swap anomaly (rapid 1-word alternating speaker labels)
        for i in range(len(words) - 2):
            w1, w2, w3 = words[i], words[i + 1], words[i + 2]
            if (
                w1.speaker_id
                and w2.speaker_id
                and w3.speaker_id
                and w1.speaker_id == w3.speaker_id
                and w1.speaker_id != w2.speaker_id
                and (w2.source_end_ms - w2.source_start_ms) < 350
            ):
                warnings.append(
                    f"Possible speaker-label swap anomaly detected at {w2.source_start_ms}ms (word '{w2.text}' isolated between '{w1.speaker_id}')."
                )

        return transcript, warnings


class MockSemanticSearchAdapter(SemanticSearchAdapter):
    """
    Mock semantic search adapter using synonym embeddings and character n-gram cosine matching.
    Matches queries like 'pricing' to 'cost', 'subscription', or 'tier'.
    """

    SYNONYM_CLUSTERS = {
        "pricing": {"cost", "subscription", "price", "prices", "rates", "fees", "fee", "tier", "charge"},
        "welcome": {"hello", "intro", "introduction", "beginning", "greetings"},
        "ending": {"goodbye", "outro", "conclusion", "finish", "thanks"},
        "boring": {"slow", "monotone", "dull", "filler"},
    }

    def find_semantic_matches(
        self,
        query: str,
        transcript: TranscriptIndex,
        similarity_threshold: float = 0.65,
    ) -> List[Dict[str, Any]]:
        norm_query = query.strip().lower()
        query_words = set(re.findall(r"\w+", norm_query))

        # Expand query words with synonym clusters
        expanded_targets = set(query_words)
        for q in query_words:
            for key, cluster in self.SYNONYM_CLUSTERS.items():
                if q == key or q in cluster:
                    expanded_targets.update(cluster)
                    expanded_targets.add(key)

        matches: List[Dict[str, Any]] = []

        # Find matching word spans in transcript
        for idx, w in enumerate(transcript.words):
            word_clean = re.sub(r"[^\w]", "", w.text.lower())
            score = 0.0

            if word_clean in query_words:
                score = 1.0
            elif word_clean in expanded_targets:
                score = 0.88
            elif any(t in word_clean or word_clean in t for t in query_words if len(t) >= 4):
                score = 0.72

            if score >= similarity_threshold:
                # Capture window of words around match for phrase context
                start_idx = max(0, idx - 1)
                end_idx = min(len(transcript.words), idx + 2)
                span_words = transcript.words[start_idx:end_idx]
                span_text = " ".join(sw.text for sw in span_words)
                clock_str = self._ms_to_clock(w.source_start_ms)

                matches.append({
                    "target_word_ids": [w.word_id],
                    "matched_text": span_text,
                    "keyword": w.text,
                    "start_ms": w.source_start_ms,
                    "end_ms": w.source_end_ms,
                    "score": score,
                    "display_option": f"{clock_str} (word {w.word_id}, '{span_text}', score: {score:.2f})",
                })

        return matches

    def _ms_to_clock(self, ms: int) -> str:
        total_sec = ms // 1000
        mins = total_sec // 60
        secs = total_sec % 60
        return f"{mins}:{secs:02d}"


class MockIntentParserAdapter(IntentParserAdapter):
    """
    Mock intent parser implementing deterministic NLP extraction into structured operation dicts.
    """

    def parse_intent(
        self,
        prompt: str,
        transcript: TranscriptIndex,
        current_timeline: CompiledTimeline,
    ) -> List[Dict[str, Any]]:
        raw = prompt.strip().lower()

        # Undo / Redo
        if raw.startswith("undo"):
            return [{"op_type": "undo"}]
        if raw.startswith("redo"):
            return [{"op_type": "redo"}]

        # Cut range: "cut the first 30 seconds"
        m_cut_first = re.search(r"cut\s+the\s+first\s+(\d+)\s*(?:s|sec|seconds?)", raw)
        if m_cut_first:
            sec = int(m_cut_first.group(1))
            return [{
                "op_type": "cut",
                "timeline_range": (0, sec * 1000),
                "source_spans": [{"start_ms": 0, "end_ms": sec * 1000}],
            }]

        # Cut clock range: "remove 0:30-0:40"
        m_range = re.search(r"(?:remove|cut)\s+(\d+:\d+)\s*-\s*(\d+:\d+)", raw)
        if m_range:
            s_ms = self._clock_to_ms(m_range.group(1))
            e_ms = self._clock_to_ms(m_range.group(2))
            return [{
                "op_type": "cut",
                "timeline_range": (s_ms, e_ms),
                "source_spans": [{"start_ms": s_ms, "end_ms": e_ms}],
            }]

        # Speed up: "speed up from 1:00 to 1:30 by 2x"
        m_speed = re.search(r"speed\s+up(?:\s+from\s+(\d+:\d+)\s+to\s+(\d+:\d+))?\s+by\s+(\d+(?:\.\d+)?)x?", raw)
        if m_speed:
            factor = float(m_speed.group(3))
            res = {"op_type": "speed", "speed": factor, "params": {"speed": factor}}
            if m_speed.group(1) and m_speed.group(2):
                res["timeline_range"] = (self._clock_to_ms(m_speed.group(1)), self._clock_to_ms(m_speed.group(2)))
            return [res]

        # Caption: "add a caption 'Welcome!'"
        m_cap = re.search(r"add\s+a\s+caption\s+['\"]([^'\"]+)['\"](?:\s+when\s+I\s+say\s+(.+))?", raw)
        if m_cap:
            text = m_cap.group(1)
            trigger = m_cap.group(2) or text
            matches = transcript.find_phrases(trigger)
            target_ids = [w.word_id for w in matches[0]] if matches else []
            return [{
                "op_type": "caption",
                "text": text,
                "target_word_ids": target_ids,
                "params": {"text": text, "style": {}},
            }]

        # Style caption: "make that caption red"
        m_style = re.search(r"make\s+(?:that\s+caption|it)\s+(\w+)", raw)
        if m_style:
            color = m_style.group(1)
            return [{
                "op_type": "style_caption",
                "params": {"style": {"color": color}},
            }]

        # Remove fillers / silences
        if "filler" in raw:
            return [{"op_type": "remove_fillers"}]
        if "silence" in raw:
            return [{"op_type": "remove_silences", "params": {"min_duration_ms": 1500}}]

        return [{"op_type": "unknown", "raw_prompt": prompt}]

    def _clock_to_ms(self, clock_str: str) -> int:
        if ":" in clock_str:
            parts = clock_str.split(":")
            return int((int(parts[0]) * 60 + float(parts[1])) * 1000)
        return int(float(clock_str) * 1000)
