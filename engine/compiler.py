"""
IncuBrix Prompt-Based Video Editing Engine
Timeline Compiler

Compiles active content-anchored operations deterministically over an untouched TranscriptIndex
to produce a frame-accurate, hashable CompiledTimeline.
"""

from __future__ import annotations

import copy
import hashlib
import json
from typing import Any, Dict, List, Literal, Optional, Set, Tuple

from engine.models import (
    AudioSegment,
    BgmEnvelopePoint,
    BgmTrack,
    CaptionItem,
    CompiledTimeline,
    EditOperation,
    SourceSpan,
    TranscriptIndex,
    VideoSegment,
    WordToken,
)


class TimelineCompiler:
    """
    100% deterministic timeline compiler.
    Applies active edit operations in order onto the untouched TranscriptIndex
    to project the compiled timeline.
    """

    def __init__(
        self,
        transcript_index: TranscriptIndex,
        speed_overlap_rule: Literal["latest_wins", "multiply"] = "latest_wins",
        min_caption_display_ms: int = 700,
    ):
        self.transcript_index = transcript_index
        self.speed_overlap_rule = speed_overlap_rule
        self.min_caption_display_ms = min_caption_display_ms

        self.history: List[EditOperation] = []
        self.redo_stack: List[str] = []

        # Stored definitions for persistent tracks
        self.caption_defs: Dict[str, Dict[str, Any]] = {}
        self.bgm_defs: Dict[str, Dict[str, Any]] = {}

        # Cache of the latest compiled timeline
        self._latest_timeline: Optional[CompiledTimeline] = None

    # -------------------------------------------------------------------------
    # History & Operation Management
    # -------------------------------------------------------------------------

    def apply_operation(self, op: EditOperation) -> CompiledTimeline:
        """
        Applies a new editing operation.
        Adding a new active edit clears the redo stack.
        """
        if op.op_type == "undo":
            return self.undo()
        elif op.op_type == "redo":
            return self.redo()

        # Handle persistent metadata definitions
        if op.op_type == "caption":
            cap_id = op.params.get("caption_id") or f"cap_{len(self.caption_defs) + 1:03d}"
            self.caption_defs[cap_id] = {
                "caption_id": cap_id,
                "text": op.params.get("text", ""),
                "bound_word_ids": list(op.target_word_ids),
                "style": copy.deepcopy(op.params.get("style", {})),
                "created_by_op": op.op_id,
            }
        elif op.op_type == "style_caption":
            cap_id = op.params.get("caption_id")
            if not cap_id and self.caption_defs:
                # Target the latest caption if unspecified
                cap_id = list(self.caption_defs.keys())[-1]
            if cap_id and cap_id in self.caption_defs:
                self.caption_defs[cap_id]["style"].update(op.params.get("style", {}))
        elif op.op_type == "add_bgm":
            bgm_id = op.params.get("track_id") or f"bgm_{len(self.bgm_defs) + 1:03d}"
            self.bgm_defs[bgm_id] = {
                "track_id": bgm_id,
                "source_url": op.params.get("source_url", ""),
                "volume": float(op.params.get("volume", 1.0)),
                "ducking_db": float(op.params.get("ducking_db", -12.0)),
                "created_by_op": op.op_id,
            }

        op.status = "active"
        self.history.append(op)
        self.redo_stack.clear()
        return self.compile()

    def undo(self) -> CompiledTimeline:
        """
        Reverses the latest active operation in history and pushes it to redo_stack.
        """
        for op in reversed(self.history):
            if op.status == "active":
                op.status = "undone"
                self.redo_stack.append(op.op_id)
                break
        return self.compile()

    def redo(self) -> CompiledTimeline:
        """
        Re-activates the most recently undone operation from redo_stack.
        """
        if not self.redo_stack:
            return self.compile()

        op_id_to_redo = self.redo_stack.pop()
        for op in self.history:
            if op.op_id == op_id_to_redo:
                op.status = "active"
                break
        return self.compile()

    def restore_op(self, target_op_id: str) -> CompiledTimeline:
        """
        Selectively restores an earlier operation without losing subsequent edits.
        Recorded in history as an explicit restorative edit so that it can be undone.
        """
        restore_edit = EditOperation(
            op_id=f"restore_{target_op_id}_{len(self.history) + 1}",
            op_type="restore_op",
            params={"restore_op_id": target_op_id},
            status="active",
            created_at_step=len(self.history) + 1,
        )
        return self.apply_operation(restore_edit)

    # -------------------------------------------------------------------------
    # Core Deterministic Timeline Compilation
    # -------------------------------------------------------------------------

    def compile(self) -> CompiledTimeline:
        """
        Pure projection of the compiled timeline from untouched transcript and active ops.
        """
        warnings: List[str] = []
        active_op_ids: List[str] = [op.op_id for op in self.history if op.status == "active"]

        # Step 1: Build the atomic source units (words and pauses)
        units = self._build_source_atoms()

        # Step 2: Apply active operations in historical order
        units = self._apply_operations_to_atoms(units, warnings)

        # Step 3: Filter active units and compute timeline timestamps
        active_units = [u for u in units if not u["is_cut"]]

        current_timeline_ms = 0
        word_to_timeline_pos: Dict[str, Tuple[int, int]] = {}

        for u in active_units:
            src_dur = u["source_end_ms"] - u["source_start_ms"]
            speed = u["speed"]
            # Frame-accurate integer milliseconds
            tl_dur = int(round(src_dur / speed)) if speed > 0 else src_dur
            u["timeline_start_ms"] = current_timeline_ms
            u["timeline_end_ms"] = current_timeline_ms + tl_dur
            current_timeline_ms += tl_dur

            if u["word_id"]:
                word_to_timeline_pos[u["word_id"]] = (u["timeline_start_ms"], u["timeline_end_ms"])

        total_duration_ms = current_timeline_ms
        total_duration_s = round(total_duration_ms / 1000.0, 3)

        # Step 4: Assemble contiguous VideoSegments
        video_segments = self._assemble_video_segments(active_units)

        # Step 5: Assemble contiguous AudioSegments (handling mute and bleep)
        audio_segments = self._assemble_audio_segments(active_units)

        # Step 6: Assemble Caption Tracks with content-anchoring rules
        caption_tracks = self._assemble_caption_tracks(word_to_timeline_pos, total_duration_ms, warnings)

        # Step 7: Assemble BGM Tracks and ducking envelopes
        bgm_tracks = self._assemble_bgm_tracks(active_units, total_duration_ms)

        # Step 8: Compute canonical SHA-256 hash
        timeline_hash = self._compute_timeline_hash(
            total_duration_ms=total_duration_ms,
            video_segments=video_segments,
            audio_segments=audio_segments,
            caption_tracks=caption_tracks,
            bgm_tracks=bgm_tracks,
        )

        compiled = CompiledTimeline(
            duration_ms=total_duration_ms,
            duration_s=total_duration_s,
            video_segments=video_segments,
            audio_segments=audio_segments,
            caption_tracks=caption_tracks,
            bgm_tracks=bgm_tracks,
            timeline_hash=timeline_hash,
            active_operation_ids=active_op_ids,
            warnings=warnings,
        )

        self._latest_timeline = compiled
        return compiled

    # -------------------------------------------------------------------------
    # Internal Compilation Pipeline
    # -------------------------------------------------------------------------

    def _build_source_atoms(self) -> List[Dict[str, Any]]:
        """
        Divides the untouched source media into ordered atomic units of words and silences.
        """
        atoms: List[Dict[str, Any]] = []
        words = self.transcript_index.words
        total_dur = self.transcript_index.source_duration_ms
        curr_source_ms = 0

        for idx, w in enumerate(words):
            # Silence before word
            if w.source_start_ms > curr_source_ms:
                atoms.append({
                    "atom_id": f"silence_pre_{idx}",
                    "source_start_ms": curr_source_ms,
                    "source_end_ms": w.source_start_ms,
                    "word_id": None,
                    "speaker_id": None,
                    "is_filler": False,
                    "is_protected_silence": False,
                    "speed": 1.0,
                    "is_muted": False,
                    "is_bleeped": False,
                    "volume": 1.0,
                    "is_cut": False,
                })

            # Spoken word atom
            atoms.append({
                "atom_id": f"word_{w.word_id}",
                "source_start_ms": w.source_start_ms,
                "source_end_ms": w.source_end_ms,
                "word_id": w.word_id,
                "speaker_id": w.speaker_id,
                "is_filler": w.is_filler,
                "is_protected_silence": w.is_protected_silence,
                "speed": 1.0,
                "is_muted": False,
                "is_bleeped": False,
                "volume": 1.0,
                "is_cut": False,
            })
            curr_source_ms = w.source_end_ms

        # Silence after last word
        if curr_source_ms < total_dur:
            atoms.append({
                "atom_id": "silence_post_end",
                "source_start_ms": curr_source_ms,
                "source_end_ms": total_dur,
                "word_id": None,
                "speaker_id": None,
                "is_filler": False,
                "is_protected_silence": False,
                "speed": 1.0,
                "is_muted": False,
                "is_bleeped": False,
                "volume": 1.0,
                "is_cut": False,
            })

        return atoms

    def _split_atoms_at_points(
        self, atoms: List[Dict[str, Any]], split_points: Set[int]
    ) -> List[Dict[str, Any]]:
        """
        Splits silence atoms at exact span cut/edit boundaries so operations
        do not over-cut or under-cut adjacent intervals.
        """
        if not split_points:
            return atoms

        sorted_points = sorted(pt for pt in split_points if pt > 0)
        result: List[Dict[str, Any]] = []

        for atom in atoms:
            # We only split silence atoms (non-word intervals) to prevent word clipping
            if atom["word_id"] is not None:
                result.append(atom)
                continue

            start = atom["source_start_ms"]
            end = atom["source_end_ms"]
            pts = [p for p in sorted_points if start < p < end]

            if not pts:
                result.append(atom)
                continue

            # Split atom across all interior points
            curr_start = start
            for p in pts:
                sub_atom = copy.deepcopy(atom)
                sub_atom["source_start_ms"] = curr_start
                sub_atom["source_end_ms"] = p
                sub_atom["atom_id"] = f"{atom['atom_id']}_split_{p}"
                result.append(sub_atom)
                curr_start = p

            sub_atom = copy.deepcopy(atom)
            sub_atom["source_start_ms"] = curr_start
            sub_atom["source_end_ms"] = end
            sub_atom["atom_id"] = f"{atom['atom_id']}_split_end"
            result.append(sub_atom)

        return result

    def _apply_operations_to_atoms(
        self,
        atoms: List[Dict[str, Any]],
        warnings: List[str],
    ) -> List[Dict[str, Any]]:
        """
        Applies active operations in chronological order onto the atomic units.
        """
        active_ops = [op for op in self.history if op.status == "active"]

        # Check for active restore_op overrides
        restored_op_ids: Set[str] = set()
        for op in active_ops:
            if op.op_type == "restore_op":
                target_restore = op.params.get("restore_op_id")
                if target_restore:
                    restored_op_ids.add(target_restore)

        # Filter out operations that are actively restored/overridden
        effective_ops = [op for op in active_ops if op.op_id not in restored_op_ids and op.op_type != "restore_op"]

        # Collect all split points from effective operations
        split_points: Set[int] = set()
        for op in effective_ops:
            for span in op.source_spans:
                split_points.add(span.start_ms)
                split_points.add(span.end_ms)

        atoms = self._split_atoms_at_points(atoms, split_points)

        for op in effective_ops:
            op_type = op.op_type
            target_ids = set(op.target_word_ids)
            source_spans = op.source_spans

            if op_type == "cut":
                # Cut by word_ids
                if target_ids:
                    for atom in atoms:
                        if atom["word_id"] in target_ids:
                            atom["is_cut"] = True

                # Cut by source spans
                for span in source_spans:
                    for atom in atoms:
                        if atom["source_start_ms"] >= span.start_ms and atom["source_end_ms"] <= span.end_ms:
                            atom["is_cut"] = True
                        elif atom["word_id"] is not None:
                            # For words that straddle, cut only if center of word is inside span
                            atom_mid = (atom["source_start_ms"] + atom["source_end_ms"]) / 2
                            if span.start_ms <= atom_mid <= span.end_ms:
                                atom["is_cut"] = True

            elif op_type == "keep_only":
                keep_words = target_ids
                for atom in atoms:
                    should_keep = False
                    if atom["word_id"] and atom["word_id"] in keep_words:
                        should_keep = True
                    for span in source_spans:
                        if atom["source_start_ms"] >= span.start_ms and atom["source_end_ms"] <= span.end_ms:
                            should_keep = True
                    if not should_keep:
                        atom["is_cut"] = True

            elif op_type == "remove_fillers":
                for atom in atoms:
                    if atom["is_filler"]:
                        atom["is_cut"] = True

            elif op_type == "protect_silence":
                for span in source_spans:
                    for atom in atoms:
                        if atom["word_id"] is None:
                            if max(atom["source_start_ms"], span.start_ms) < min(atom["source_end_ms"], span.end_ms):
                                atom["is_protected_silence"] = True
                if target_ids:
                    for atom in atoms:
                        if atom["word_id"] in target_ids:
                            atom["is_protected_silence"] = True

            elif op_type == "remove_silences":
                min_silence_ms = op.params.get("min_duration_ms", 1000)
                for atom in atoms:
                    if atom["word_id"] is None and not atom["is_cut"]:
                        silence_dur = atom["source_end_ms"] - atom["source_start_ms"]
                        if silence_dur >= min_silence_ms:
                            if atom["is_protected_silence"]:
                                # Protected deliberate pauses survive!
                                continue
                            atom["is_cut"] = True

            elif op_type == "speed":
                factor = float(op.params.get("speed", 1.0))
                for atom in atoms:
                    in_target = False
                    if atom["word_id"] and atom["word_id"] in target_ids:
                        in_target = True
                    for span in source_spans:
                        if max(atom["source_start_ms"], span.start_ms) < min(atom["source_end_ms"], span.end_ms):
                            in_target = True

                    if in_target:
                        if self.speed_overlap_rule == "multiply":
                            atom["speed"] = min(8.0, round(atom["speed"] * factor, 4))
                        else:  # "latest_wins"
                            atom["speed"] = factor

            elif op_type == "mute":
                for atom in atoms:
                    if (atom["word_id"] and atom["word_id"] in target_ids) or any(
                        max(atom["source_start_ms"], span.start_ms) < min(atom["source_end_ms"], span.end_ms)
                        for span in source_spans
                    ):
                        atom["is_muted"] = True
                        atom["volume"] = 0.0

            elif op_type == "bleep":
                for atom in atoms:
                    if (atom["word_id"] and atom["word_id"] in target_ids) or any(
                        max(atom["source_start_ms"], span.start_ms) < min(atom["source_end_ms"], span.end_ms)
                        for span in source_spans
                    ):
                        atom["is_bleeped"] = True

            elif op_type == "reorder":
                # Handle section reordering via explicit block orders
                order = op.params.get("order")  # List of block index lists or word_id lists
                if order and isinstance(order, list):
                    reordered: List[Dict[str, Any]] = []
                    # Map word_id to atom
                    atom_by_word = {a["word_id"]: a for a in atoms if a["word_id"]}
                    non_reordered = [a for a in atoms if not a["word_id"]]
                    for block in order:
                        for wid in block:
                            if wid in atom_by_word:
                                reordered.append(atom_by_word[wid])
                    if reordered:
                        atoms = reordered + non_reordered

        return atoms

    def _assemble_video_segments(self, active_units: List[Dict[str, Any]]) -> List[VideoSegment]:
        """
        Merges contiguous active units into frame-accurate VideoSegments.
        """
        segments: List[VideoSegment] = []
        if not active_units:
            return segments

        curr_seg_start_src = active_units[0]["source_start_ms"]
        curr_seg_end_src = active_units[0]["source_end_ms"]
        curr_seg_start_tl = active_units[0]["timeline_start_ms"]
        curr_seg_end_tl = active_units[0]["timeline_end_ms"]
        curr_speed = active_units[0]["speed"]
        curr_words = [active_units[0]["word_id"]] if active_units[0]["word_id"] else []

        for u in active_units[1:]:
            # Check continuity: contiguous source, identical speed
            can_merge = (
                u["source_start_ms"] == curr_seg_end_src
                and abs(u["speed"] - curr_speed) < 1e-4
            )
            if can_merge:
                curr_seg_end_src = u["source_end_ms"]
                curr_seg_end_tl = u["timeline_end_ms"]
                if u["word_id"]:
                    curr_words.append(u["word_id"])
            else:
                segments.append(
                    VideoSegment(
                        segment_id=f"v_seg_{len(segments) + 1:03d}",
                        source_start_ms=curr_seg_start_src,
                        source_end_ms=curr_seg_end_src,
                        timeline_start_ms=curr_seg_start_tl,
                        timeline_end_ms=curr_seg_end_tl,
                        speed=round(curr_speed, 4),
                        word_ids=curr_words,
                    )
                )
                curr_seg_start_src = u["source_start_ms"]
                curr_seg_end_src = u["source_end_ms"]
                curr_seg_start_tl = u["timeline_start_ms"]
                curr_seg_end_tl = u["timeline_end_ms"]
                curr_speed = u["speed"]
                curr_words = [u["word_id"]] if u["word_id"] else []

        segments.append(
            VideoSegment(
                segment_id=f"v_seg_{len(segments) + 1:03d}",
                source_start_ms=curr_seg_start_src,
                source_end_ms=curr_seg_end_src,
                timeline_start_ms=curr_seg_start_tl,
                timeline_end_ms=curr_seg_end_tl,
                speed=round(curr_speed, 4),
                word_ids=curr_words,
            )
        )
        return segments

    def _assemble_audio_segments(self, active_units: List[Dict[str, Any]]) -> List[AudioSegment]:
        """
        Merges contiguous active units into frame-accurate AudioSegments,
        accounting for mute and bleep states.
        """
        segments: List[AudioSegment] = []
        if not active_units:
            return segments

        u0 = active_units[0]
        curr_seg_start_src = u0["source_start_ms"]
        curr_seg_end_src = u0["source_end_ms"]
        curr_seg_start_tl = u0["timeline_start_ms"]
        curr_seg_end_tl = u0["timeline_end_ms"]
        curr_speed = u0["speed"]
        curr_muted = u0["is_muted"]
        curr_bleeped = u0["is_bleeped"]
        curr_volume = u0["volume"]
        curr_words = [u0["word_id"]] if u0["word_id"] else []

        for u in active_units[1:]:
            can_merge = (
                u["source_start_ms"] == curr_seg_end_src
                and abs(u["speed"] - curr_speed) < 1e-4
                and u["is_muted"] == curr_muted
                and u["is_bleeped"] == curr_bleeped
                and abs(u["volume"] - curr_volume) < 1e-4
            )
            if can_merge:
                curr_seg_end_src = u["source_end_ms"]
                curr_seg_end_tl = u["timeline_end_ms"]
                if u["word_id"]:
                    curr_words.append(u["word_id"])
            else:
                segments.append(
                    AudioSegment(
                        segment_id=f"a_seg_{len(segments) + 1:03d}",
                        source_start_ms=curr_seg_start_src,
                        source_end_ms=curr_seg_end_src,
                        timeline_start_ms=curr_seg_start_tl,
                        timeline_end_ms=curr_seg_end_tl,
                        speed=round(curr_speed, 4),
                        is_muted=curr_muted,
                        is_bleeped=curr_bleeped,
                        volume=round(curr_volume, 4),
                        word_ids=curr_words,
                    )
                )
                curr_seg_start_src = u["source_start_ms"]
                curr_seg_end_src = u["source_end_ms"]
                curr_seg_start_tl = u["timeline_start_ms"]
                curr_seg_end_tl = u["timeline_end_ms"]
                curr_speed = u["speed"]
                curr_muted = u["is_muted"]
                curr_bleeped = u["is_bleeped"]
                curr_volume = u["volume"]
                curr_words = [u["word_id"]] if u["word_id"] else []

        segments.append(
            AudioSegment(
                segment_id=f"a_seg_{len(segments) + 1:03d}",
                source_start_ms=curr_seg_start_src,
                source_end_ms=curr_seg_end_src,
                timeline_start_ms=curr_seg_start_tl,
                timeline_end_ms=curr_seg_end_tl,
                speed=round(curr_speed, 4),
                is_muted=curr_muted,
                is_bleeped=curr_bleeped,
                volume=round(curr_volume, 4),
                word_ids=curr_words,
            )
        )
        return segments

    def _assemble_caption_tracks(
        self,
        word_to_timeline_pos: Dict[str, Tuple[int, int]],
        total_duration_ms: int,
        warnings: List[str],
    ) -> List[CaptionItem]:
        """
        Enforces content-anchoring rules for captions:
        1. Captions follow remaining bound words across cuts/speeds/reorders.
        2. If 100% of bound words are cut, caption is suppressed and warned.
        3. Sped-up or short captions enforce minimum readable duration of 700 ms.
        4. When cuts are undone or restored, suppressed captions automatically reappear.
        """
        caption_items: List[CaptionItem] = []

        for cap_id, defn in self.caption_defs.items():
            bound_words = defn["bound_word_ids"]
            active_bound_positions = [
                word_to_timeline_pos[wid]
                for wid in bound_words
                if wid in word_to_timeline_pos
            ]

            if not active_bound_positions:
                # 100% of bound words were cut -> Suppress caption with explicit warning
                warnings.append(
                    f"Caption '{defn['text']}' ({cap_id}) suppressed because all bound words were cut."
                )
                caption_items.append(
                    CaptionItem(
                        caption_id=cap_id,
                        text=defn["text"],
                        timeline_start_ms=0,
                        timeline_end_ms=0,
                        bound_word_ids=bound_words,
                        style=defn.get("style", {}),
                        suppressed=True,
                    )
                )
            else:
                # Partial cuts keep remaining words
                start_ms = min(pos[0] for pos in active_bound_positions)
                end_ms = max(pos[1] for pos in active_bound_positions)

                # Rule: Sped-up captions enforce minimum display duration of 700 ms
                if (end_ms - start_ms) < self.min_caption_display_ms:
                    end_ms = min(total_duration_ms, start_ms + self.min_caption_display_ms)

                caption_items.append(
                    CaptionItem(
                        caption_id=cap_id,
                        text=defn["text"],
                        timeline_start_ms=start_ms,
                        timeline_end_ms=end_ms,
                        bound_word_ids=bound_words,
                        style=defn.get("style", {}),
                        suppressed=False,
                    )
                )

        return caption_items

    def _assemble_bgm_tracks(
        self,
        active_units: List[Dict[str, Any]],
        total_duration_ms: int,
    ) -> List[BgmTrack]:
        """
        Generates background music tracks with dynamic ducking envelopes under speech.
        """
        bgm_tracks: List[BgmTrack] = []
        if not self.bgm_defs:
            return bgm_tracks

        for bgm_id, defn in self.bgm_defs.items():
            envelope: List[BgmEnvelopePoint] = []
            duck_db = defn.get("ducking_db", -12.0)

            # Build envelope keyframes:
            # During speech (active units with word_id): volume = duck_db
            # During silence (active units without word_id): volume = 0.0 dB
            last_vol: Optional[float] = None
            for u in active_units:
                has_speech = u["word_id"] is not None
                target_vol = duck_db if has_speech else 0.0
                if last_vol is None or abs(target_vol - last_vol) > 1e-4:
                    envelope.append(
                        BgmEnvelopePoint(
                            timeline_ms=u["timeline_start_ms"],
                            volume_db=round(target_vol, 2),
                        )
                    )
                    last_vol = target_vol

            if envelope and envelope[-1].timeline_ms < total_duration_ms:
                envelope.append(
                    BgmEnvelopePoint(
                        timeline_ms=total_duration_ms,
                        volume_db=envelope[-1].volume_db,
                    )
                )

            bgm_tracks.append(
                BgmTrack(
                    track_id=bgm_id,
                    source_url=defn["source_url"],
                    volume=defn["volume"],
                    ducking_envelope=envelope,
                )
            )

        return bgm_tracks

    def _compute_timeline_hash(
        self,
        total_duration_ms: int,
        video_segments: List[VideoSegment],
        audio_segments: List[AudioSegment],
        caption_tracks: List[CaptionItem],
        bgm_tracks: List[BgmTrack],
    ) -> str:
        """
        Computes canonical SHA-256 hash using sorted keys and integer milliseconds.
        Guarantees that 3 identical runs always yield the exact same hash.
        """
        canonical_state = {
            "duration_ms": int(total_duration_ms),
            "video_segments": [
                {
                    "segment_id": seg.segment_id,
                    "source_start_ms": int(seg.source_start_ms),
                    "source_end_ms": int(seg.source_end_ms),
                    "timeline_start_ms": int(seg.timeline_start_ms),
                    "timeline_end_ms": int(seg.timeline_end_ms),
                    "speed": round(float(seg.speed), 4),
                    "word_ids": list(seg.word_ids),
                }
                for seg in video_segments
            ],
            "audio_segments": [
                {
                    "segment_id": seg.segment_id,
                    "source_start_ms": int(seg.source_start_ms),
                    "source_end_ms": int(seg.source_end_ms),
                    "timeline_start_ms": int(seg.timeline_start_ms),
                    "timeline_end_ms": int(seg.timeline_end_ms),
                    "speed": round(float(seg.speed), 4),
                    "is_muted": bool(seg.is_muted),
                    "is_bleeped": bool(seg.is_bleeped),
                    "volume": round(float(seg.volume), 4),
                    "word_ids": list(seg.word_ids),
                }
                for seg in audio_segments
            ],
            "caption_tracks": [
                {
                    "caption_id": cap.caption_id,
                    "text": cap.text,
                    "timeline_start_ms": int(cap.timeline_start_ms),
                    "timeline_end_ms": int(cap.timeline_end_ms),
                    "bound_word_ids": list(cap.bound_word_ids),
                    "style": cap.style,
                    "suppressed": bool(cap.suppressed),
                }
                for cap in caption_tracks
            ],
            "bgm_tracks": [
                {
                    "track_id": bgm.track_id,
                    "source_url": bgm.source_url,
                    "volume": round(float(bgm.volume), 4),
                    "ducking_envelope": [
                        {
                            "timeline_ms": int(pt.timeline_ms),
                            "volume_db": round(float(pt.volume_db), 2),
                        }
                        for pt in bgm.ducking_envelope
                    ],
                }
                for bgm in bgm_tracks
            ],
        }

        canonical_json = json.dumps(canonical_state, sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(canonical_json.encode("utf-8")).hexdigest()
