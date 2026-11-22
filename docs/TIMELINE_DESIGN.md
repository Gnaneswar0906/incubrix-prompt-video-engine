# IncuBrix Timeline Design: Content-Anchored Deterministic Architecture

## 1. The Clock-Position Failure Mode
Traditional timeline architectures record edit operations against wall-clock timestamps (e.g., `cut(00:30.000, 00:40.000)` or `add_caption("Welcome!", start=01:05.000, end=01:08.000)`). In conversational and multi-turn prompt-based video editing, this clock-position model immediately fails:
* **Clock Drift**: Cutting the first 30 seconds shifts all subsequent media earlier by 30 seconds. A caption placed at `01:05` will now render at `01:05` on completely different words than the creator intended.
* **Cascading Corruption**: When multiple cuts, reorders, and speed changes pile up, determining where an original phrase or pause landed requires reverse-simulating every past clock shift—an error-prone, brittle calculation.
* **Destructive Mutation**: Mutating timeline representations in-place prevents clean non-linear restorations, undo/redo trees, and frame-accurate caching.

## 2. Content-Anchored Design Principle
The IncuBrix Timeline Engine enforces the fundamental rule:
> **Edits belong to content, not to clock positions.**

Every input video is indexed into an immutable sequence of content tokens—`WordToken`s and inter-word silence intervals:
```json
{
  "word_id": "w_0042",
  "text": "welcome",
  "source_start_ms": 42100,
  "source_end_ms": 42650,
  "speaker_id": "speaker_0",
  "confidence": 0.98,
  "silence_before_ms": 150,
  "silence_after_ms": 50,
  "is_filler": false
}
```

Edit operations bind exclusively to immutable content identifiers (`target_word_ids`) or immutable source intervals (`source_spans`):
* A caption instruction ("Add caption 'Welcome!' when I say welcome to the channel") attaches to `bound_word_ids: ["w_0042", "w_0043", "w_0044", "w_0045"]`.
* A speed instruction ("Speed up the intro by 2x") targets the words and intervals in that section.
* A cut instruction marks specific `word_id`s as removed from the active playback sequence.

## 3. Pure Projection Compilation
The timeline is never modified destructively. Instead, the `TimelineCompiler` treats the source `TranscriptIndex` as an immutable base and applies the active edit operations in order to project a fresh `CompiledTimeline`.

```
[Untouched Source Media & TranscriptIndex]
                   │
                   ▼
       [Active Edit Operations]
      (cut, speed, mute, caption)
                   │
                   ▼
  [TimelineCompiler Pure Projection]
                   │
                   ├── Video Segments (source spans -> timeline spans)
                   ├── Audio Segments (mutes, bleeps, volume factors)
                   ├── Caption Tracks (anchored to remaining bound words)
                   └── BGM Ducking Envelope (volume dips during speech)
```

## 4. Invariant Rules and Behaviors

### 4.1. Caption Anchoring & Partial Cuts
Captions calculate their rendered `timeline_start_ms` and `timeline_end_ms` dynamically from the active timeline boundaries of their `bound_word_ids`:
* If an edit cuts media earlier in the timeline, the caption's timeline start shifts automatically while staying bound to its words.
* **Partial Cuts**: If a subset of words in a captioned phrase is removed, the remaining words preserve the caption with adjusted start/end times.
* **100% Word Suppression**: If all bound words of a caption are cut, the caption is automatically suppressed (`suppressed: true`), omitted from rendered output, and an explicit system warning is generated.
* **Restoration**: If the cut is later undone or restored via `restore_op(op_id)`, the bound words return to the active sequence, and the caption automatically reappears.

### 4.2. Sped-Up Captions (700 ms Human Readability Minimum)
When video segments are sped up (e.g., 2x or 4x), the duration of spoken words shrinks proportionally:
$$\text{duration}_{\text{timeline}} = \frac{\text{source\_end\_ms} - \text{source\_start\_ms}}{\text{speed}}$$
To ensure viewer readability, any caption whose visible timeline span drops below 700 ms is automatically extended to a minimum display duration of `700 ms` (clamped to timeline bounds).

### 4.3. Deliberate Pauses (`protected_silence`)
Silence removal instructions ("remove silences longer than 2 seconds") target natural pauses between speech. However, dramatic pauses or deliberate pauses flagged as `protected_silence: true` are immune to silence removal passes and survive intact.

### 4.4. Overlapping Speed Resolution Policy
When multiple operations specify speed changes over overlapping content spans, the engine applies a deterministic, documented resolution rule:
* **Default Policy (`latest_wins`)**: The most recently applied speed operation overrides prior speed values for overlapping words/spans.
* **Alternative Policy (`multiply`)**: Overlapping speeds multiply cumulatively ($\text{speed}_{\text{eff}} = \text{speed}_1 \times \text{speed}_2$), capped at the maximum allowed speed limit (8.0x).
The chosen policy is explicitly declared in `InstructionResponse.summary`.

### 4.5. Non-Destructive History: Undo, Redo & `restore_op(op_id)`
* **Linear Undo/Redo**: `undo()` marks the latest active operation as `undone` and pushes it to `redo_stack`. Applying any new edit clears the redo stack. `redo()` reactivates the latest undone operation.
* **Non-Linear Selective Restore (`restore_op`)**: When a user requests to restore an earlier edit (e.g., "put the intro back" while preserving a subsequent pricing cut and speedup), `restore_op(op_id)` selectively deactivates the earlier cut operation without unwinding or destroying later operations.

## 5. Canonical SHA-256 Timeline Hash
To guarantee absolute determinism (Must-have 4), the compiled timeline is serialized into a canonical JSON representation:
* All timestamps and durations are integer milliseconds.
* All floating-point values (speed, volume) are rounded to fixed precision.
* Keys are strictly alphabetized (`sort_keys=True`) with compact separators (`,`, `:`).
* The SHA-256 digest of this canonical payload forms the `timeline_hash`.
Three identical execution runs are mathematically guaranteed to yield identical hashes.
