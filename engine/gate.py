"""
IncuBrix Prompt-Based Video Editing Engine
Deterministic Three-Way Decision Gate

Evaluates incoming edit instructions and operations against strict invariants, returning
exactly one of three deterministic states: 'applied', 'needs_clarification', or 'rejected'.
"""

from __future__ import annotations

import re
from typing import Any, Dict, List, Optional, Tuple, Union
from engine.compiler import TimelineCompiler
from engine.models import (
    CompiledTimeline,
    EditOperation,
    InstructionResponse,
    SourceSpan,
    WordToken,
)


class DecisionGate:
    """
    Deterministic Three-Way Decision Gate.
    Guarantees safe, reversible edits and never guesses on ambiguous or destructive commands.
    """

    def __init__(self, compiler: TimelineCompiler):
        self.compiler = compiler

    # -------------------------------------------------------------------------
    # Public Entry Point
    # -------------------------------------------------------------------------

    def execute_instruction(
        self,
        instruction: Union[str, Dict[str, Any], EditOperation, List[EditOperation], List[Dict[str, Any]]],
        step_number: int = 1,
    ) -> InstructionResponse:
        """
        Validates and processes instructions, returning an InstructionResponse.
        Supports single operations, multi-part instructions, and plain text intents.
        """
        # Ensure compiler has compiled at least once
        current_timeline = self.compiler._latest_timeline or self.compiler.compile()
        before_dur_ms = current_timeline.duration_ms

        # Normalize instruction into a list of parsed part dictionaries
        parts = self._normalize_to_parts(instruction, step_number)

        # Multi-match clarification check (e.g., phrase mentioned multiple times)
        clarification = self._check_clarification_needs(parts, current_timeline)
        if clarification:
            return clarification

        # Process parts: validate each part
        applied_ops: List[EditOperation] = []
        warnings: List[str] = []
        per_part_results: List[Dict[str, Any]] = []
        all_rejected = True
        primary_reject_code: Optional[str] = None
        primary_reject_msg: Optional[str] = None

        for idx, part in enumerate(parts):
            validation_error = self._validate_part(part, current_timeline)
            part_num = idx + 1

            if validation_error:
                code, msg = validation_error
                if primary_reject_code is None:
                    primary_reject_code = code
                    primary_reject_msg = msg
                per_part_results.append({
                    "part": part_num,
                    "status": "rejected",
                    "code": code,
                    "message": msg,
                })
                warnings.append(f"Part {part_num} rejected: {msg} ({code})")
            else:
                # Valid part -> build EditOperation and apply
                op = self._build_operation(part, step_number)
                new_timeline = self.compiler.apply_operation(op)
                applied_ops.append(op)
                all_rejected = False
                per_part_results.append({
                    "part": part_num,
                    "status": "applied",
                    "op_id": op.op_id,
                    "op_type": op.op_type,
                })
                # Add any compiler-level warnings (e.g. caption suppression)
                for w in new_timeline.warnings:
                    if w not in warnings:
                        warnings.append(w)
                current_timeline = new_timeline

        # Determine overall response status
        if all_rejected:
            return InstructionResponse(
                status="rejected",
                operations=[],
                summary={
                    "error_code": primary_reject_code or "INSTRUCTION_REJECTED",
                    "message": primary_reject_msg or "Instruction could not be applied.",
                    "per_part_results": per_part_results,
                    "time_policy": "current_timeline_time",
                },
                warnings=warnings,
                timeline_hash=current_timeline.timeline_hash,
                duration_s=current_timeline.duration_s,
            )

        # Successfully applied (all or valid parts of multi-part)
        after_dur_ms = current_timeline.duration_ms
        what_moved = self._describe_changes(before_dur_ms, after_dur_ms, applied_ops)

        summary: Dict[str, Any] = {
            "before_duration_ms": before_dur_ms,
            "after_duration_ms": after_dur_ms,
            "before_duration_s": round(before_dur_ms / 1000.0, 3),
            "after_duration_s": round(after_dur_ms / 1000.0, 3),
            "what_moved": what_moved,
            "time_policy": "current_timeline_time",
            "per_part_results": per_part_results,
        }

        return InstructionResponse(
            status="applied",
            operations=applied_ops,
            summary=summary,
            warnings=warnings,
            timeline_hash=current_timeline.timeline_hash,
            duration_s=current_timeline.duration_s,
        )

    # -------------------------------------------------------------------------
    # Validation Rules
    # -------------------------------------------------------------------------

    def _validate_part(
        self,
        part: Dict[str, Any],
        current_timeline: CompiledTimeline,
    ) -> Optional[Tuple[str, str]]:
        """
        Validates a single instruction part against all domain rules.
        Returns None if valid, or (ERROR_CODE, message) if rejected.
        """
        op_type = part.get("op_type")

        # 1. Extreme Speed Check (>8x or <=0)
        if op_type == "speed":
            speed_val = part.get("speed")
            if speed_val is None and "params" in part:
                speed_val = part["params"].get("speed")
            if speed_val is None:
                return "INVALID_PARAMS", "Speed operation missing speed factor."
            try:
                speed_float = float(speed_val)
            except (ValueError, TypeError):
                return "INVALID_PARAMS", f"Invalid speed value: {speed_val}"

            if speed_float <= 0.0 or speed_float > 8.0:
                return (
                    "EXTREME_SPEED_REJECTED",
                    f"Speed factor {speed_float}x is out of valid range (must be > 0 and <= 8.0x).",
                )

        # 2. Out-of-Range Times
        timeline_dur = current_timeline.duration_ms
        time_range = part.get("timeline_range") or part.get("time_range")
        if time_range:
            start_ms, end_ms = time_range
            if start_ms > timeline_dur or end_ms > timeline_dur or start_ms < 0:
                return (
                    "OUT_OF_RANGE",
                    f"Requested range [{start_ms}ms, {end_ms}ms] exceeds current timeline duration of {timeline_dur}ms.",
                )
            if start_ms >= end_ms:
                return (
                    "OUT_OF_RANGE",
                    f"Start time ({start_ms}ms) must be strictly less than end time ({end_ms}ms).",
                )

        # Out-of-range for single timestamp (e.g. 'caption at 5:00')
        target_time_ms = part.get("target_time_ms")
        if target_time_ms is not None:
            if target_time_ms > timeline_dur or target_time_ms < 0:
                return (
                    "OUT_OF_RANGE",
                    f"Requested timestamp {target_time_ms}ms exceeds current timeline duration of {timeline_dur}ms.",
                )

        # 3. Whole-Video Cut Check
        if op_type in ("cut", "keep_only"):
            if self._would_cut_whole_video(part, current_timeline):
                return (
                    "WHOLE_VIDEO_CUT_REJECTED",
                    "Cannot cut entire video: an edit must leave at least one segment.",
                )

        # 4. Missing Targets Check
        if op_type == "style_caption":
            # Modifying caption when none exist
            active_captions = [c for c in current_timeline.caption_tracks if not c.suppressed]
            if not active_captions:
                return (
                    "MISSING_TARGET",
                    "No active caption exists to modify. Add a caption first.",
                )

        # 5. Duplicate Identical Cuts Check
        if op_type == "cut":
            if self._is_duplicate_cut(part, current_timeline):
                return (
                    "DUPLICATE_OPERATION",
                    "Target content has already been removed in an earlier operation.",
                )

        return None

    def _check_clarification_needs(
        self,
        parts: List[Dict[str, Any]],
        current_timeline: CompiledTimeline,
    ) -> Optional[InstructionResponse]:
        """
        Detects ambiguous multi-match queries and returns needs_clarification.
        """
        for part in parts:
            query_phrase = part.get("phrase")
            if not query_phrase and "query" in part:
                query_phrase = part["query"]

            if query_phrase:
                matches = self.compiler.transcript_index.find_phrases(query_phrase)
                # Filter to matches that are still active on the current timeline
                active_matches = []
                active_word_ids = set()
                for seg in current_timeline.video_segments:
                    active_word_ids.update(seg.word_ids)

                for match in matches:
                    if any(w.word_id in active_word_ids for w in match):
                        active_matches.append(match)

                if len(active_matches) > 1 and not part.get("disambiguated_choice"):
                    # Ambiguous query found! Formulate specific question and timestamped options
                    options = []
                    timestamps_str = []
                    for idx, match in enumerate(active_matches):
                        # Find timeline position of this match
                        first_w = match[0]
                        last_w = match[-1]
                        tl_pos = self._find_word_timeline_pos(first_w.word_id, current_timeline)
                        pos_str = self._ms_to_clock(tl_pos[0]) if tl_pos else f"{first_w.source_start_ms}ms"
                        timestamps_str.append(pos_str)
                        options.append(f"{pos_str} (words {first_w.word_id}-{last_w.word_id})")
                    options.append("All")

                    time_list = ", ".join(timestamps_str[:-1]) + f" and {timestamps_str[-1]}"
                    question = f"'{query_phrase.capitalize()}' is mentioned at {time_list} - which one, or all?"

                    return InstructionResponse(
                        status="needs_clarification",
                        operations=[],
                        summary={
                            "reason": "ambiguous_multi_match",
                            "match_count": len(active_matches),
                            "time_policy": "current_timeline_time",
                        },
                        question=question,
                        options=options,
                        warnings=[],
                        timeline_hash=current_timeline.timeline_hash,
                        duration_s=current_timeline.duration_s,
                    )

        return None

    # -------------------------------------------------------------------------
    # Helper Invariant Checks
    # -------------------------------------------------------------------------

    def _would_cut_whole_video(
        self,
        part: Dict[str, Any],
        current_timeline: CompiledTimeline,
    ) -> bool:
        """Checks if the proposed cut would reduce timeline duration to 0."""
        time_range = part.get("timeline_range") or part.get("time_range")
        if time_range:
            start_ms, end_ms = time_range
            if start_ms <= 0 and end_ms >= current_timeline.duration_ms:
                return True

        target_ids = part.get("target_word_ids")
        if target_ids:
            all_active_words = set()
            for seg in current_timeline.video_segments:
                all_active_words.update(seg.word_ids)
            if all_active_words and set(target_ids) >= all_active_words:
                return True

        if part.get("cut_all"):
            return True

        return False

    def _is_duplicate_cut(
        self,
        part: Dict[str, Any],
        current_timeline: CompiledTimeline,
    ) -> bool:
        """Checks if target words/spans are already completely absent."""
        target_ids = part.get("target_word_ids")
        if target_ids:
            all_active_words = set()
            for seg in current_timeline.video_segments:
                all_active_words.update(seg.word_ids)
            # If none of the target words are currently active, it's a duplicate cut
            if not any(wid in all_active_words for wid in target_ids):
                return True

        time_range = part.get("timeline_range") or part.get("time_range")
        if time_range:
            start_ms, end_ms = time_range
            # Check if this range has already been cut or matches previous cut op exactly
            for op in self.compiler.history:
                if op.status == "active" and op.op_type == "cut":
                    for span in op.source_spans:
                        if abs(span.start_ms - start_ms) < 50 and abs(span.end_ms - end_ms) < 50:
                            return True

        return False

    # -------------------------------------------------------------------------
    # Parser and Operation Builders
    # -------------------------------------------------------------------------

    def _normalize_to_parts(
        self,
        instruction: Union[str, Dict[str, Any], EditOperation, List[EditOperation], List[Dict[str, Any]]],
        step_number: int,
    ) -> List[Dict[str, Any]]:
        """Parses various instruction input formats into a list of structured part dicts."""
        if isinstance(instruction, list):
            parts = []
            for item in instruction:
                parts.extend(self._normalize_to_parts(item, step_number))
            return parts

        if isinstance(instruction, EditOperation):
            return [{
                "op_type": instruction.op_type,
                "target_word_ids": instruction.target_word_ids,
                "source_spans": instruction.source_spans,
                "params": instruction.params,
                "speed": instruction.params.get("speed"),
            }]

        if isinstance(instruction, dict):
            # Check if it has multiple sub-parts
            if "parts" in instruction:
                return instruction["parts"]
            return [instruction]

        if isinstance(instruction, str):
            return self._parse_text_instruction(instruction, step_number)

        return []

    def _parse_text_instruction(self, text: str, step_number: int) -> List[Dict[str, Any]]:
        """
        Deterministic regex/rule-based parser for user instructions.
        Handles single and multi-part ('and', 'then') instructions.
        """
        raw = text.strip()

        # Handle undo/redo/render
        if re.match(r"^undo\b", raw, re.IGNORECASE):
            return [{"op_type": "undo"}]
        if re.match(r"^redo\b", raw, re.IGNORECASE):
            return [{"op_type": "redo"}]

        # Split multi-part sentences joined by " and " or " then "
        # Avoid splitting inside quoted phrases
        clauses = re.split(r"\s+(?:and|then)\s+(?=(?:[^']*'[^']*')*[^']*$)", raw, flags=re.IGNORECASE)
        if len(clauses) > 1:
            parts = []
            for clause in clauses:
                parts.extend(self._parse_text_instruction(clause, step_number))
            return parts

        # Parse individual clause
        # 1. Caption: Add a caption 'Welcome!' when I say welcome to the channel
        cap_match = re.search(r"add\s+(?:a\s+)?caption\s+['\"]([^'\"]+)['\"](?:\s+when\s+I\s+say\s+(.+))?", raw, re.IGNORECASE)
        if cap_match:
            cap_text = cap_match.group(1)
            trigger_phrase = cap_match.group(2) or cap_text
            # Look up trigger words in transcript
            matches = self.compiler.transcript_index.find_phrases(trigger_phrase)
            target_ids = [w.word_id for w in matches[0]] if matches else []
            return [{
                "op_type": "caption",
                "text": cap_text,
                "target_word_ids": target_ids,
                "params": {"text": cap_text, "style": {}},
            }]

        # 2. Style caption: Make that caption red / make it bigger
        style_match = re.search(r"make\s+(?:that\s+caption|it)\s+(\w+)", raw, re.IGNORECASE)
        if style_match:
            modifier = style_match.group(1).lower()
            style_param = {"color": modifier} if modifier in ("red", "blue", "green", "yellow", "white", "black") else {"size": modifier}
            return [{
                "op_type": "style_caption",
                "params": {"style": style_param},
            }]

        # 3. Add caption at timestamp: Add a caption at 5:00
        cap_at_match = re.search(r"add\s+(?:a\s+)?caption\s+(?:at\s+)?(\d+:\d+|\d+\s*s)", raw, re.IGNORECASE)
        if cap_at_match:
            t_ms = self._clock_to_ms(cap_at_match.group(1))
            return [{
                "op_type": "caption",
                "target_time_ms": t_ms,
                "text": "Caption",
                "params": {"text": "Caption"},
            }]

        # 4. Cut initial duration: Cut the first 30 seconds
        cut_first_match = re.search(r"cut\s+the\s+first\s+(\d+)\s*(?:s|sec|seconds?)", raw, re.IGNORECASE)
        if cut_first_match:
            sec = int(cut_first_match.group(1))
            return [{
                "op_type": "cut",
                "timeline_range": (0, sec * 1000),
                "source_spans": [SourceSpan(start_ms=0, end_ms=sec * 1000)],
            }]

        # 5. Cut last duration: Cut the last 10 seconds / remove the last 10 seconds
        cut_last_match = re.search(r"(?:cut|remove)\s+(?:the\s+)?last\s+(\d+)\s*(?:s|sec|seconds?)", raw, re.IGNORECASE)
        if cut_last_match:
            sec = int(cut_last_match.group(1))
            dur_ms = self.compiler._latest_timeline.duration_ms if self.compiler._latest_timeline else self.compiler.transcript_index.source_duration_ms
            start_ms = max(0, dur_ms - sec * 1000)
            return [{
                "op_type": "cut",
                "timeline_range": (start_ms, dur_ms),
                "source_spans": [SourceSpan(start_ms=start_ms, end_ms=dur_ms)],
            }]

        # 6. Cut clock range: Remove 0:30-0:40 or cut from 0:30 to 0:40
        cut_range_match = re.search(r"(?:remove|cut)(?:\s+from)?\s+(\d+:\d+|\d+)\s*(?:-|to)\s*(\d+:\d+|\d+)", raw, re.IGNORECASE)
        if cut_range_match:
            s_str, e_str = cut_range_match.groups()
            s_ms = self._clock_to_ms(s_str)
            e_ms = self._clock_to_ms(e_str)
            return [{
                "op_type": "cut",
                "timeline_range": (s_ms, e_ms),
                "source_spans": [SourceSpan(start_ms=s_ms, end_ms=e_ms)],
            }]

        # 7. Remove everything after phrase: Remove everything after I say thanks
        after_phrase_match = re.search(r"(?:remove|cut)\s+everything\s+after\s+(?:I\s+say\s+)?['\"]?([^'\"]+)['\"]?$", raw, re.IGNORECASE)
        if after_phrase_match:
            phrase = after_phrase_match.group(1).strip()
            return [{
                "op_type": "cut",
                "phrase": phrase,
                "cut_after_phrase": True,
            }]

        # 4. Remove part about phrase: Remove the part about pricing
        remove_phrase_match = re.search(r"(?:remove|cut)\s+(?:the\s+part\s+about\s+)?['\"]?([^'\"]+)['\"]?$", raw, re.IGNORECASE)
        if remove_phrase_match and not any(kw in raw.lower() for kw in ["filler", "silence", "everything"]):
            phrase = remove_phrase_match.group(1).strip()
            return [{
                "op_type": "cut",
                "phrase": phrase,
            }]

        # 5. Speed up from X to Y by Zx
        speed_match = re.search(r"speed\s+up(?:\s+from\s+(\d+:\d+|\d+)\s+to\s+(\d+:\d+|\d+))?\s+by\s+(\d+(?:\.\d+)?)x?", raw, re.IGNORECASE)
        if speed_match:
            start_str, end_str, factor_str = speed_match.groups()
            factor = float(factor_str)
            if start_str and end_str:
                s_ms = self._clock_to_ms(start_str)
                e_ms = self._clock_to_ms(end_str)
                return [{
                    "op_type": "speed",
                    "timeline_range": (s_ms, e_ms),
                    "source_spans": [SourceSpan(start_ms=s_ms, end_ms=e_ms)],
                    "speed": factor,
                    "params": {"speed": factor},
                }]
            else:
                return [{
                    "op_type": "speed",
                    "speed": factor,
                    "params": {"speed": factor},
                }]

        # 6. Restore / Put back: Actually, put the intro back
        if re.search(r"put\s+(?:the\s+)?intro\s+back", raw, re.IGNORECASE):
            # Target the intro cut operation
            for op in reversed(self.compiler.history):
                if op.status == "active" and op.op_type == "cut":
                    # Check if it was cutting at 0ms
                    if any(span.start_ms == 0 for span in op.source_spans):
                        return [{
                            "op_type": "restore_op",
                            "params": {"restore_op_id": op.op_id},
                            "restore_op_id": op.op_id,
                        }]
            return [{"op_type": "restore_op", "params": {"restore_op_id": "intro_cut"}}]

        # 7. Remove fillers: Remove filler words
        if "filler" in raw.lower():
            return [{"op_type": "remove_fillers"}]

        # 8. Remove silences: Remove silences longer than N seconds
        silence_match = re.search(r"remove\s+silences?(?:\s+longer\s+than\s+(\d+)\s*s)?", raw, re.IGNORECASE)
        if silence_match:
            min_sec = int(silence_match.group(1)) if silence_match.group(1) else 1
            return [{
                "op_type": "remove_silences",
                "params": {"min_duration_ms": min_sec * 1000},
            }]

        # 9. Cut everything / whole video
        if "cut everything" in raw.lower():
            return [{
                "op_type": "cut",
                "cut_all": True,
            }]

        # Fallback default
        return [{"op_type": "unknown", "raw_text": raw}]

    def _build_operation(self, part: Dict[str, Any], step_number: int) -> EditOperation:
        """Converts a validated part dictionary into an executable EditOperation."""
        op_type = part.get("op_type", "unknown")
        op_id = part.get("op_id") or f"op_{op_type}_{step_number}_{len(self.compiler.history) + 1}"

        target_word_ids = list(part.get("target_word_ids", []))
        source_spans = list(part.get("source_spans", []))
        params = dict(part.get("params", {}))

        # If a phrase was targeted and matched
        if part.get("phrase") and not target_word_ids:
            matches = self.compiler.transcript_index.find_phrases(part["phrase"])
            choice_idx = part.get("disambiguated_choice", 0)
            if matches:
                target_match = matches[min(choice_idx, len(matches) - 1)]
                target_word_ids = [w.word_id for w in target_match]

        if "speed" in part and "speed" not in params:
            params["speed"] = part["speed"]

        if "text" in part and "text" not in params:
            params["text"] = part["text"]

        return EditOperation(
            op_id=op_id,
            op_type=op_type,
            target_word_ids=target_word_ids,
            source_spans=source_spans,
            params=params,
            status="active",
            created_at_step=step_number,
        )

    # -------------------------------------------------------------------------
    # Utility Methods
    # -------------------------------------------------------------------------

    def _find_word_timeline_pos(
        self,
        word_id: str,
        timeline: CompiledTimeline,
    ) -> Optional[Tuple[int, int]]:
        """Finds timeline [start_ms, end_ms] of a word in the current timeline."""
        for seg in timeline.video_segments:
            if word_id in seg.word_ids:
                return (seg.timeline_start_ms, seg.timeline_end_ms)
        return None

    def _clock_to_ms(self, clock_str: str) -> int:
        """Converts '1:30', '80 seconds', 'a minute twenty', or '90' to integer milliseconds."""
        ms = self._parse_natural_time(clock_str)
        return ms if ms is not None else 0

    def _parse_natural_time(self, time_str: str) -> Optional[int]:
        """Parses flexible natural time expressions into milliseconds."""
        s = time_str.strip().lower()
        if ":" in s:
            parts = s.split(":")
            mins = int(parts[0])
            secs = float(parts[1])
            return int((mins * 60 + secs) * 1000)

        # "a minute twenty", "1 minute 20 seconds", "two minutes"
        if "minute" in s:
            m_match = re.search(
                r"(?:(\d+)|a)\s*minute(?:s)?(?:\s+(?:and\s+)?(\d+|twenty|thirty|forty|fifty|ten|fifteen))?",
                s,
            )
            if m_match:
                mins = int(m_match.group(1)) if m_match.group(1) else 1
                word_to_num = {"ten": 10, "fifteen": 15, "twenty": 20, "thirty": 30, "forty": 40, "fifty": 50}
                sec_raw = m_match.group(2)
                secs = 0
                if sec_raw:
                    secs = int(sec_raw) if sec_raw.isdigit() else word_to_num.get(sec_raw, 0)
                return int((mins * 60 + secs) * 1000)

        # "80 seconds", "80s", or plain number
        sec_match = re.search(r"(\d+(?:\.\d+)?)\s*(?:s|sec|seconds?)?", s)
        if sec_match:
            return int(float(sec_match.group(1)) * 1000)

        return None

    def _ms_to_clock(self, ms: int) -> str:
        """Converts milliseconds to MM:SS or M:SS clock string."""
        total_sec = ms // 1000
        mins = total_sec // 60
        secs = total_sec % 60
        return f"{mins}:{secs:02d}"

    def _describe_changes(
        self,
        before_ms: int,
        after_ms: int,
        operations: List[EditOperation],
    ) -> str:
        """Generates a human-readable explanation of timeline mutations."""
        diff_ms = after_ms - before_ms
        op_types = ", ".join(op.op_type for op in operations)
        if diff_ms < 0:
            return f"Applied {op_types}. Timeline shortened by {abs(diff_ms)} ms ({before_ms} ms -> {after_ms} ms)."
        elif diff_ms > 0:
            return f"Applied {op_types}. Timeline extended by {diff_ms} ms ({before_ms} ms -> {after_ms} ms)."
        return f"Applied {op_types}. Timeline duration unchanged ({after_ms} ms)."
