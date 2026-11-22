# IncuBrix Prompt-Based Video Editing Engine (Core Foundation)

A production-grade, 100% deterministic, content-anchored video editing engine built for Python 3.11+.

> **Core Philosophy**: Edits attach to **immutable content tokens (`word_id`s and source spans)** rather than clock positions. Compiling timelines is pure deterministic projection code—no LLM directly touches or mutates timeline state.

---

## 1. Architectural Highlights

* **Content-Anchored Editing**: Every word and pause is an immutable token (`WordToken`, e.g., `w_0001`). Edits bind to `target_word_ids` or `source_spans`.
* **Zero Clock Drift**: Because edits anchor to content identifiers, earlier cuts or speed changes never displace downstream captions, mutes, or bleeps.
* **Deterministic Decision Gate**: Implements a strict Three-Way Decision Gate returning `applied`, `needs_clarification`, or `rejected`. Never guesses on destructive commands.
* **Granular Reversibility**: Linear undo/redo stack (`one instruction = one undo; new edit clears redo`) plus non-linear selective restoration (`restore_op(op_id)`).
* **Canonical SHA-256 Hashing**: Millisecond-accurate integer representations with sorted keys guarantee 100% identical hashes across runs.

---

## 2. Invariant Rules and Behaviors

| Feature / Rule | Specification & Behavior |
| :--- | :--- |
| **Caption Anchoring** | Captions dynamically bind to their `bound_word_ids`. Start/end timeline bounds update seamlessly across cuts, reorders, and speed changes. |
| **Partial Cuts** | When a subset of words in a captioned phrase is cut, the remaining words retain the caption. |
| **Total Cut Suppression** | If 100% of a caption's bound words are cut, the caption is suppressed (`suppressed: true`) and a system warning is emitted. |
| **Automatic Reappearance** | When a cut that suppressed a caption is undone or restored via `restore_op(op_id)`, the caption automatically reappears on the original words. |
| **Sped-Up Captions** | Any caption whose display duration compresses below 700 ms is automatically padded to enforce a **minimum display duration of 700 ms**. |
| **Protected Pauses** | Deliberate pauses flagged as `protected_silence: true` survive subsequent `remove_silences` operations. |
| **Overlapping Speeds** | Documented resolution rule: Default is **`latest_wins`** (the most recent speed instruction overrides earlier values on overlapping spans). Configurable to **`multiply`** (speeds compound, capped at 8.0x). |

---

## 3. Decision Gate Error Codes

All errors follow standard Integration Standard JSON format:
```json
{
  "error": {
    "code": "OUT_OF_RANGE",
    "message": "Requested timestamp 300000ms exceeds current timeline duration of 120000ms.",
    "retryable": false,
    "details": {}
  }
}
```

Standard UPPER_SNAKE_CASE error codes:
* `OUT_OF_RANGE`: Timestamp or range lies outside the current timeline bounds.
* `WHOLE_VIDEO_CUT_REJECTED`: Instruction would reduce the timeline duration to 0 ms.
* `EXTREME_SPEED_REJECTED`: Speed factor $\le 0.0$ or $> 8.0\text{x}$.
* `MISSING_TARGET`: Instruction references an element (e.g. caption) that does not exist.
* `DUPLICATE_OPERATION`: Instruction attempts to cut content that has already been removed.
* `AMBIGUOUS_QUERY`: Targeted phrase matches multiple timeline locations without disambiguation.
* `INVALID_PARAMS`: Missing or malformed parameters.

---

## 4. Setup in Under 10 Commands

```bash
# 1. Clone or navigate to the repository
cd incubrix-engine

# 2. Create Python virtual environment
python -m venv .venv

# 3. Activate virtual environment (Windows PowerShell)
.venv\Scripts\Activate.ps1
# On Linux/macOS: source .venv/bin/activate

# 4. Install dependencies
python -m pip install -r requirements.txt

# 5. Run test suite
python -m pytest tests/test_compiler.py -v
```

---

## 5. Repository Structure

```
├── schemas/
│   └── timeline.schema.json      # JSON Schema Draft 2020-12
├── docs/
│   └── TIMELINE_DESIGN.md        # 1-page technical content-anchoring specification
├── engine/
│   ├── __init__.py               # Engine exports
│   ├── models.py                 # Pydantic v2 data models
│   ├── compiler.py               # Deterministic TimelineCompiler
│   └── gate.py                   # Three-Way Decision Gate
├── tests/
│   ├── __init__.py
│   └── test_compiler.py          # 26 comprehensive pytest unit tests (100% pass)
├── README.md
├── SOURCES.md
└── AI_USE.md
```
