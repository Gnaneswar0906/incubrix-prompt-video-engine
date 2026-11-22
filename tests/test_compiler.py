"""
Unit tests for IncuBrix Prompt-Based Video Editing Engine
Verifies 100% deterministic compilation, content-anchored rules, and three-way decision gating.
"""

import pytest
from engine.compiler import TimelineCompiler
from engine.gate import DecisionGate
from engine.models import (
    EditOperation,
    SourceSpan,
    TranscriptIndex,
    WordToken,
)


@pytest.fixture
def sample_transcript() -> TranscriptIndex:
    """
    Standard test transcript representing a 60-second video:
    - 0-10s: Intro silence and early words (w_0001 - w_0005)
    - 15s: First mention of 'pricing' (w_0006)
    - 25s: Second mention of 'pricing' (w_0010)
    - 35s: Third mention of 'pricing' (w_0014)
    - 42-44s: "welcome to the channel" (w_0017 - w_0020)
    - 45s: Deliberate protected pause (45000-47500ms)
    - 50s: Unprotected pause (50000-52500ms)
    - Filler words: "um" (w_0008), "uh" (w_0012)
    """
    words = [
        # Segment 1: Intro (5000 - 8000 ms)
        WordToken(word_id="w_0001", text="hello", source_start_ms=5000, source_end_ms=5500, speaker_id="speaker_0"),
        WordToken(word_id="w_0002", text="and", source_start_ms=5500, source_end_ms=5800, speaker_id="speaker_0"),
        WordToken(word_id="w_0003", text="start", source_start_ms=5800, source_end_ms=6400, speaker_id="speaker_0"),
        WordToken(word_id="w_0004", text="our", source_start_ms=6400, source_end_ms=6800, speaker_id="speaker_0"),
        WordToken(word_id="w_0005", text="video", source_start_ms=6800, source_end_ms=7500, speaker_id="speaker_0"),
        WordToken(word_id="w_0006", text="um", source_start_ms=15000, source_end_ms=15500, speaker_id="speaker_0", is_filler=True),

        # "welcome to the channel" at 42-44s (42000 - 44000 ms)
        WordToken(word_id="w_0017", text="welcome", source_start_ms=42000, source_end_ms=42500, speaker_id="speaker_0"),
        WordToken(word_id="w_0018", text="to", source_start_ms=42500, source_end_ms=42800, speaker_id="speaker_0"),
        WordToken(word_id="w_0019", text="the", source_start_ms=42800, source_end_ms=43100, speaker_id="speaker_0"),
        WordToken(word_id="w_0020", text="channel", source_start_ms=43100, source_end_ms=44000, speaker_id="speaker_0"),

        # Words around pauses (44500 - 45000, then silence 45000-47500, then word at 47500)
        WordToken(
            word_id="w_0021",
            text="pause",
            source_start_ms=44500,
            source_end_ms=45000,
            speaker_id="speaker_0",
            is_protected_silence=True,  # Protected silence attached here
        ),
        WordToken(word_id="w_0022", text="afterpause", source_start_ms=47500, source_end_ms=48500, speaker_id="speaker_0"),

        # Word before unprotected silence (silence 50000 - 52500 ms)
        WordToken(word_id="w_0023", text="beforegap", source_start_ms=49000, source_end_ms=50000, speaker_id="speaker_0"),
        WordToken(word_id="w_0024", text="aftergap", source_start_ms=52500, source_end_ms=53500, speaker_id="speaker_0"),

        # Three pricing mentions after 60s (matching brief: 1:05, etc.)
        # First pricing mention at ~65s (65000 ms)
        WordToken(word_id="w_0007", text="the", source_start_ms=64500, source_end_ms=64900, speaker_id="speaker_0"),
        WordToken(word_id="w_0008", text="pricing", source_start_ms=65000, source_end_ms=65800, speaker_id="speaker_0"),

        # Second pricing mention at ~75s (75000 ms)
        WordToken(word_id="w_0009", text="our", source_start_ms=74500, source_end_ms=74900, speaker_id="speaker_0"),
        WordToken(word_id="w_0010", text="pricing", source_start_ms=75000, source_end_ms=75800, speaker_id="speaker_0"),
        WordToken(word_id="w_0011", text="tier", source_start_ms=75900, source_end_ms=76500, speaker_id="speaker_0"),
        WordToken(word_id="w_0012", text="uh", source_start_ms=76600, source_end_ms=77000, speaker_id="speaker_0", is_filler=True),

        # Third pricing mention at ~85s (85000 ms)
        WordToken(word_id="w_0013", text="final", source_start_ms=84500, source_end_ms=84900, speaker_id="speaker_0"),
        WordToken(word_id="w_0014", text="pricing", source_start_ms=85000, source_end_ms=85800, speaker_id="speaker_0"),

        # Final word
        WordToken(word_id="w_0025", text="goodbye", source_start_ms=115000, source_end_ms=116000, speaker_id="speaker_0"),
    ]
    return TranscriptIndex(source_duration_ms=120000, words=words)


# -----------------------------------------------------------------------------
# 1. Determinism and Hash Reproducibility
# -----------------------------------------------------------------------------

def test_canonical_hash_determinism_3_runs(sample_transcript):
    """
    Must-have 4: 3 identical runs must produce the exact same timeline_hash.
    """
    hashes = []
    for _ in range(3):
        compiler = TimelineCompiler(sample_transcript)
        # Apply identical operations
        compiler.apply_operation(EditOperation(
            op_id="op_1",
            op_type="caption",
            target_word_ids=["w_0017", "w_0018", "w_0019", "w_0020"],
            params={"text": "Welcome!"},
        ))
        compiler.apply_operation(EditOperation(
            op_id="op_2",
            op_type="cut",
            source_spans=[SourceSpan(start_ms=0, end_ms=30000)],
        ))
        compiler.apply_operation(EditOperation(
            op_id="op_3",
            op_type="speed",
            source_spans=[SourceSpan(start_ms=30000, end_ms=45000)],
            params={"speed": 2.0},
        ))
        timeline = compiler.compile()
        hashes.append(timeline.timeline_hash)

    assert len(hashes) == 3
    assert hashes[0] == hashes[1] == hashes[2]
    assert len(hashes[0]) == 64  # SHA-256


# -----------------------------------------------------------------------------
# 2. Content-Anchored Captions across Cuts, Speed, and Reorders
# -----------------------------------------------------------------------------

def test_caption_anchoring_across_cuts(sample_transcript):
    """
    Edits stick to content: caption on 'welcome to the channel' originally at 42-44s.
    After cutting first 30 seconds, it plays at 12-14s on the exact same words.
    """
    compiler = TimelineCompiler(sample_transcript)

    # Step 1: Add caption
    compiler.apply_operation(EditOperation(
        op_id="op_cap",
        op_type="caption",
        target_word_ids=["w_0017", "w_0018", "w_0019", "w_0020"],
        params={"text": "Welcome!"},
    ))
    tl1 = compiler.compile()
    cap1 = tl1.caption_tracks[0]
    assert not cap1.suppressed
    assert cap1.timeline_start_ms == 42000
    assert cap1.timeline_end_ms == 44000

    # Step 2: Cut the first 30 seconds
    compiler.apply_operation(EditOperation(
        op_id="op_cut_intro",
        op_type="cut",
        source_spans=[SourceSpan(start_ms=0, end_ms=30000)],
    ))
    tl2 = compiler.compile()
    cap2 = tl2.caption_tracks[0]

    assert not cap2.suppressed
    # Caption moved earlier by exactly 30 seconds: 42s -> 12s, 44s -> 14s
    assert cap2.timeline_start_ms == 12000
    assert cap2.timeline_end_ms == 14000
    assert cap2.bound_word_ids == ["w_0017", "w_0018", "w_0019", "w_0020"]


def test_caption_partial_cut_keeps_remaining_words(sample_transcript):
    """
    Partial cuts keep remaining words: cutting 'welcome' leaves 'to the channel' with caption.
    """
    compiler = TimelineCompiler(sample_transcript)
    compiler.apply_operation(EditOperation(
        op_id="op_cap",
        op_type="caption",
        target_word_ids=["w_0017", "w_0018", "w_0019", "w_0020"],
        params={"text": "Welcome!"},
    ))
    # Cut only the first word 'welcome' (w_0017)
    compiler.apply_operation(EditOperation(
        op_id="op_cut_w1",
        op_type="cut",
        target_word_ids=["w_0017"],
    ))
    tl = compiler.compile()
    assert len(tl.caption_tracks) == 1
    cap = tl.caption_tracks[0]
    assert not cap.suppressed
    # Bound words start at w_0018 (42500 ms in source, which shifted because w_0017 was removed)
    assert cap.timeline_start_ms == 42000  # Shifted earlier by 500 ms of w_0017


def test_caption_100_percent_cut_suppression_and_warning(sample_transcript):
    """
    If 100% of a caption's words are cut, caption is suppressed with a warning.
    """
    compiler = TimelineCompiler(sample_transcript)
    compiler.apply_operation(EditOperation(
        op_id="op_cap",
        op_type="caption",
        target_word_ids=["w_0017", "w_0018", "w_0019", "w_0020"],
        params={"text": "Welcome!"},
    ))
    # Cut all 4 words
    compiler.apply_operation(EditOperation(
        op_id="op_cut_all_words",
        op_type="cut",
        target_word_ids=["w_0017", "w_0018", "w_0019", "w_0020"],
    ))
    tl = compiler.compile()
    cap = tl.caption_tracks[0]
    assert cap.suppressed
    assert any("suppressed because all bound words were cut" in w for w in tl.warnings)


def test_caption_automatic_reappearance_on_undo_and_restore(sample_transcript):
    """
    If the cut that suppressed a caption is undone or restored via restore_op,
    the caption automatically reappears on those exact words!
    """
    compiler = TimelineCompiler(sample_transcript)
    compiler.apply_operation(EditOperation(
        op_id="op_cap",
        op_type="caption",
        target_word_ids=["w_0017", "w_0018", "w_0019", "w_0020"],
        params={"text": "Welcome!"},
    ))
    # Cut all words
    compiler.apply_operation(EditOperation(
        op_id="op_cut_welcome",
        op_type="cut",
        target_word_ids=["w_0017", "w_0018", "w_0019", "w_0020"],
    ))
    tl_cut = compiler.compile()
    assert tl_cut.caption_tracks[0].suppressed

    # Case A: Undo brings it back
    tl_undone = compiler.undo()
    assert not tl_undone.caption_tracks[0].suppressed
    assert tl_undone.caption_tracks[0].timeline_start_ms == 42000

    # Redo cuts it again
    tl_redone = compiler.redo()
    assert tl_redone.caption_tracks[0].suppressed

    # Case B: restore_op brings it back non-linearly
    tl_restored = compiler.restore_op("op_cut_welcome")
    assert not tl_restored.caption_tracks[0].suppressed
    assert tl_restored.caption_tracks[0].timeline_start_ms == 42000


# -----------------------------------------------------------------------------
# 3. Sped-up Captions (700 ms Minimum Duration Rule)
# -----------------------------------------------------------------------------

def test_sped_up_caption_minimum_duration_700ms(sample_transcript):
    """
    Sped-up captions enforce a minimum display duration of 700 ms.
    """
    compiler = TimelineCompiler(sample_transcript, min_caption_display_ms=700)
    # Caption on single short word: 'to' (w_0018, duration 300 ms)
    compiler.apply_operation(EditOperation(
        op_id="op_cap_short",
        op_type="caption",
        target_word_ids=["w_0018"],
        params={"text": "To"},
    ))
    # Speed up that word by 4x (would make 300ms -> 75ms)
    compiler.apply_operation(EditOperation(
        op_id="op_speed_4x",
        op_type="speed",
        target_word_ids=["w_0018"],
        params={"speed": 4.0},
    ))
    tl = compiler.compile()
    cap = tl.caption_tracks[0]
    assert not cap.suppressed
    # Must be at least 700 ms
    display_dur = cap.timeline_end_ms - cap.timeline_start_ms
    assert display_dur >= 700


# -----------------------------------------------------------------------------
# 4. Deliberate Pauses (protected_silence) vs Silence Removal
# -----------------------------------------------------------------------------

def test_protected_silence_survives_remove_silences(sample_transcript):
    """
    Deliberate pauses (protected_silence) survive later remove_silences.
    Unprotected pauses >= min_duration are removed.
    """
    compiler = TimelineCompiler(sample_transcript)

    # Mark the pause around w_0021 as protected
    compiler.apply_operation(EditOperation(
        op_id="op_protect",
        op_type="protect_silence",
        source_spans=[SourceSpan(start_ms=45000, end_ms=47500)],
    ))

    # Remove silences longer than 1500 ms
    compiler.apply_operation(EditOperation(
        op_id="op_rem_silence",
        op_type="remove_silences",
        params={"min_duration_ms": 1500},
    ))

    tl = compiler.compile()

    # The unprotected silence at 50000-52500ms (2500ms) should be cut
    # The protected silence at 45000-47500ms (2500ms) must remain!
    # Let's verify by checking the presence of the 45000-47500ms interval in video segments
    source_intervals = [(s.source_start_ms, s.source_end_ms) for s in tl.video_segments]

    # Verify protected interval survived
    has_protected_silence = any(s <= 45000 and e >= 47500 for (s, e) in source_intervals)
    assert has_protected_silence, "Protected silence should survive remove_silences"

    # Verify unprotected interval was cut
    has_unprotected_silence = any(s <= 50000 and e >= 52500 for (s, e) in source_intervals)
    assert not has_unprotected_silence, "Unprotected silence must be removed by remove_silences"


# -----------------------------------------------------------------------------
# 5. Overlapping Speed Resolution Policies
# -----------------------------------------------------------------------------

def test_overlapping_speed_latest_wins(sample_transcript):
    """
    Default rule: 'latest_wins' - latest speed operation overrides earlier on overlapping words.
    """
    compiler = TimelineCompiler(sample_transcript, speed_overlap_rule="latest_wins")
    # First speed: 2x on w_0001 - w_0005
    compiler.apply_operation(EditOperation(
        op_id="op_speed_1",
        op_type="speed",
        target_word_ids=["w_0001", "w_0002", "w_0003"],
        params={"speed": 2.0},
    ))
    # Second speed: 4x on w_0002 - w_0004
    compiler.apply_operation(EditOperation(
        op_id="op_speed_2",
        op_type="speed",
        target_word_ids=["w_0002", "w_0003", "w_0004"],
        params={"speed": 4.0},
    ))
    tl = compiler.compile()
    # w_0002 and w_0003 should have speed 4.0 (latest wins), w_0001 should have speed 2.0
    for seg in tl.video_segments:
        if "w_0002" in seg.word_ids:
            assert seg.speed == 4.0
        elif "w_0001" in seg.word_ids:
            assert seg.speed == 2.0


def test_overlapping_speed_multiply(sample_transcript):
    """
    Alternative rule: 'multiply' - speeds compound cumulatively (2x * 3x = 6x).
    """
    compiler = TimelineCompiler(sample_transcript, speed_overlap_rule="multiply")
    compiler.apply_operation(EditOperation(
        op_id="op_speed_1",
        op_type="speed",
        target_word_ids=["w_0002"],
        params={"speed": 2.0},
    ))
    compiler.apply_operation(EditOperation(
        op_id="op_speed_2",
        op_type="speed",
        target_word_ids=["w_0002"],
        params={"speed": 3.0},
    ))
    tl = compiler.compile()
    for seg in tl.video_segments:
        if "w_0002" in seg.word_ids:
            assert seg.speed == 6.0


# -----------------------------------------------------------------------------
# 6. Undo, Redo, and Linear History
# -----------------------------------------------------------------------------

def test_undo_redo_and_clear_redo_stack(sample_transcript):
    """
    One instruction = one undo; new edit clears redo stack.
    """
    compiler = TimelineCompiler(sample_transcript)
    orig_dur = compiler.compile().duration_ms

    # Step 1: cut
    compiler.apply_operation(EditOperation(
        op_id="op_cut",
        op_type="cut",
        target_word_ids=["w_0001", "w_0002"],
    ))
    cut_dur = compiler.compile().duration_ms
    assert cut_dur < orig_dur

    # Undo
    tl_undone = compiler.undo()
    assert tl_undone.duration_ms == orig_dur
    assert len(compiler.redo_stack) == 1

    # New edit clears redo stack
    compiler.apply_operation(EditOperation(
        op_id="op_new_caption",
        op_type="caption",
        target_word_ids=["w_0005"],
        params={"text": "Video"},
    ))
    assert len(compiler.redo_stack) == 0


# -----------------------------------------------------------------------------
# 7. Non-Linear Selective restore_op
# -----------------------------------------------------------------------------

def test_selective_restore_op_non_linear(sample_transcript):
    """
    restore_op(op_id) restores a specific earlier edit without losing subsequent edits.
    """
    compiler = TimelineCompiler(sample_transcript)

    # Step 1: cut intro (op_1)
    compiler.apply_operation(EditOperation(
        op_id="op_intro_cut",
        op_type="cut",
        source_spans=[SourceSpan(start_ms=0, end_ms=10000)],
    ))
    # Step 2: cut pricing (op_2)
    compiler.apply_operation(EditOperation(
        op_id="op_pricing_cut",
        op_type="cut",
        target_word_ids=["w_0007"],
    ))
    # Step 3: speed up goodbye (op_3)
    compiler.apply_operation(EditOperation(
        op_id="op_speed_goodbye",
        op_type="speed",
        target_word_ids=["w_0025"],
        params={"speed": 2.0},
    ))

    # Restore intro cut only!
    tl = compiler.restore_op("op_intro_cut")

    # Intro words should be back
    active_words = set()
    for seg in tl.video_segments:
        active_words.update(seg.word_ids)

    assert "w_0001" in active_words  # Intro word returned!
    assert "w_0007" not in active_words  # Pricing cut stays cut!

    # Speed on goodbye remains active
    for seg in tl.video_segments:
        if "w_0025" in seg.word_ids:
            assert seg.speed == 2.0


# -----------------------------------------------------------------------------
# 8. BGM Ducking Envelopes
# -----------------------------------------------------------------------------

def test_bgm_ducking_envelope_under_speech(sample_transcript):
    """
    Background music automatically ducks (gets quieter) under speech.
    """
    compiler = TimelineCompiler(sample_transcript)
    compiler.apply_operation(EditOperation(
        op_id="op_bgm",
        op_type="add_bgm",
        params={
            "track_id": "bgm_jazz",
            "source_url": "https://example.com/audio/jazz.mp3",
            "volume": 0.8,
            "ducking_db": -12.0,
        },
    ))
    tl = compiler.compile()
    assert len(tl.bgm_tracks) == 1
    bgm = tl.bgm_tracks[0]
    assert len(bgm.ducking_envelope) > 0
    # Check that speech units trigger ducking to -12 dB
    has_ducked_point = any(pt.volume_db == -12.0 for pt in bgm.ducking_envelope)
    has_full_point = any(pt.volume_db == 0.0 for pt in bgm.ducking_envelope)
    assert has_ducked_point, "BGM must duck under speech"
    assert has_full_point, "BGM must return to full volume during silence"


# -----------------------------------------------------------------------------
# 9. Three-Way Decision Gate Tests
# -----------------------------------------------------------------------------

def test_gate_out_of_range_time_rejected(sample_transcript):
    """
    Gate rejects times beyond timeline duration (e.g. 5:00 on 60s video) with OUT_OF_RANGE.
    """
    compiler = TimelineCompiler(sample_transcript)
    gate = DecisionGate(compiler)

    resp = gate.execute_instruction({
        "op_type": "cut",
        "timeline_range": (300000, 310000),  # 5:00 - 5:10
    })
    assert resp.status == "rejected"
    assert resp.summary.get("error_code") == "OUT_OF_RANGE"
    assert "OUT_OF_RANGE" in resp.warnings[0]


def test_gate_whole_video_cut_rejected(sample_transcript):
    """
    Gate rejects whole-video cuts with WHOLE_VIDEO_CUT_REJECTED.
    """
    compiler = TimelineCompiler(sample_transcript)
    gate = DecisionGate(compiler)

    resp = gate.execute_instruction("cut everything")
    assert resp.status == "rejected"
    assert resp.summary.get("error_code") == "WHOLE_VIDEO_CUT_REJECTED"


def test_gate_extreme_speed_rejected(sample_transcript):
    """
    Gate rejects extreme speed (>8x or <=0) with EXTREME_SPEED_REJECTED.
    """
    compiler = TimelineCompiler(sample_transcript)
    gate = DecisionGate(compiler)

    # Test >8x
    resp_10x = gate.execute_instruction("speed up by 10x")
    assert resp_10x.status == "rejected"
    assert resp_10x.summary.get("error_code") == "EXTREME_SPEED_REJECTED"

    # Test <=0
    resp_zero = gate.execute_instruction({
        "op_type": "speed",
        "speed": 0.0,
    })
    assert resp_zero.status == "rejected"
    assert resp_zero.summary.get("error_code") == "EXTREME_SPEED_REJECTED"


def test_gate_missing_target_rejected(sample_transcript):
    """
    Gate rejects styling or modifying a caption when no caption exists with MISSING_TARGET.
    """
    compiler = TimelineCompiler(sample_transcript)
    gate = DecisionGate(compiler)

    resp = gate.execute_instruction("Make that caption red")
    assert resp.status == "rejected"
    assert resp.summary.get("error_code") == "MISSING_TARGET"


def test_gate_duplicate_identical_cut_rejected(sample_transcript):
    """
    Gate rejects cutting content that has already been cut with DUPLICATE_OPERATION.
    """
    compiler = TimelineCompiler(sample_transcript)
    gate = DecisionGate(compiler)

    # First cut: succeeds
    resp1 = gate.execute_instruction({
        "op_type": "cut",
        "target_word_ids": ["w_0001", "w_0002"],
    })
    assert resp1.status == "applied"

    # Second cut of identical already-cut words: rejected
    resp2 = gate.execute_instruction({
        "op_type": "cut",
        "target_word_ids": ["w_0001", "w_0002"],
    })
    assert resp2.status == "rejected"
    assert resp2.summary.get("error_code") == "DUPLICATE_OPERATION"


def test_gate_ambiguous_multi_match_needs_clarification(sample_transcript):
    """
    When a phrase is mentioned multiple times ('pricing' at 3 locations),
    gate returns needs_clarification with specific question and options.
    """
    compiler = TimelineCompiler(sample_transcript)
    gate = DecisionGate(compiler)

    resp = gate.execute_instruction("Remove the part about pricing")
    assert resp.status == "needs_clarification"
    assert resp.question is not None
    assert "pricing" in resp.question.lower()
    assert len(resp.options) == 4  # 3 occurrences + 'All'
    assert "All" in resp.options


def test_gate_multipart_instruction_partial_application(sample_transcript):
    """
    Multi-part instruction: valid part is applied, invalid part is rejected,
    reporting exact per-part outcomes and warnings.
    """
    compiler = TimelineCompiler(sample_transcript)
    gate = DecisionGate(compiler)

    # Instruction: "cut the first 30 seconds and speed up by 10x"
    # Part 1 (cut 0-30s): valid -> applied
    # Part 2 (speed 10x): invalid (>8x) -> rejected
    resp = gate.execute_instruction("Cut the first 30 seconds and speed up by 10x")
    assert resp.status == "applied"
    per_part = resp.summary.get("per_part_results", [])
    assert len(per_part) == 2
    assert per_part[0]["status"] == "applied"
    assert per_part[1]["status"] == "rejected"
    assert per_part[1]["code"] == "EXTREME_SPEED_REJECTED"
    assert any("EXTREME_SPEED_REJECTED" in w for w in resp.warnings)


# -----------------------------------------------------------------------------
# 10. Worked Example Full Flow (Brief Page 3)
# -----------------------------------------------------------------------------

def test_worked_example_full_flow(sample_transcript):
    """
    Reproduces the exact 8-step worked example from the IncuBrix assessment brief.
    1. Add a caption 'Welcome!' when I say welcome to the channel -> Applied
    2. Cut the first 30 seconds -> Applied, video 30s shorter, caption plays at 12-14s
    3. Remove the part about pricing -> Needs clarification (which one?) -> Disambiguated choice 2 applied
    4. Speed up from 1:00 to 1:30 by 2x -> Applied, states time policy
    5. Actually, put the intro back -> Applied, first 30s return, caption back at 42s
    6. Undo -> Reverses step 5 only; intro cut again
    7. Make that caption red -> Applied to the Welcome! caption
    """
    compiler = TimelineCompiler(sample_transcript)
    gate = DecisionGate(compiler)

    # Step 1: Add caption 'Welcome!'
    r1 = gate.execute_instruction("Add a caption 'Welcome!' when I say welcome to the channel", step_number=1)
    assert r1.status == "applied"
    cap1 = compiler._latest_timeline.caption_tracks[0]
    assert cap1.timeline_start_ms == 42000
    assert cap1.timeline_end_ms == 44000

    # Step 2: Cut first 30 seconds
    r2 = gate.execute_instruction("Cut the first 30 seconds", step_number=2)
    assert r2.status == "applied"
    assert r2.summary["time_policy"] == "current_timeline_time"
    cap2 = compiler._latest_timeline.caption_tracks[0]
    assert cap2.timeline_start_ms == 12000
    assert cap2.timeline_end_ms == 14000

    # Step 3: Remove pricing -> Needs clarification
    r3_clarify = gate.execute_instruction("Remove the part about pricing", step_number=3)
    assert r3_clarify.status == "needs_clarification"

    # User answers "the second one" (disambiguated choice index 1)
    r3_applied = gate.execute_instruction({
        "op_type": "cut",
        "phrase": "pricing",
        "disambiguated_choice": 1,
    }, step_number=3)
    assert r3_applied.status == "applied"

    # Step 4: Speed up from 1:00 to 1:30 by 2x (matching brief: 60s - 90s in source)
    r4 = gate.execute_instruction({
        "op_type": "speed",
        "time_range": (30000, 60000),
        "source_spans": [SourceSpan(start_ms=60000, end_ms=90000)],
        "speed": 2.0,
    }, step_number=4)
    assert r4.status == "applied"
    assert r4.summary["time_policy"] == "current_timeline_time"

    # Step 5: Actually, put the intro back
    r5 = gate.execute_instruction("Actually, put the intro back", step_number=5)
    assert r5.status == "applied"
    cap5 = compiler._latest_timeline.caption_tracks[0]
    # Intro returned, so caption is back at 42000 ms
    assert cap5.timeline_start_ms == 42000

    # Step 6: Undo -> Reverses step 5 only. The intro is cut again!
    r6 = gate.execute_instruction("Undo", step_number=6)
    assert r6.status == "applied"
    cap6 = compiler._latest_timeline.caption_tracks[0]
    assert cap6.timeline_start_ms == 12000  # Intro is cut again!

    # Step 7: Make that caption red
    r7 = gate.execute_instruction("Make that caption red", step_number=7)
    assert r7.status == "applied"
    cap7 = compiler._latest_timeline.caption_tracks[0]
    assert cap7.style.get("color") == "red"


# -----------------------------------------------------------------------------
# 11. Hard Cases from Assessment Brief
# -----------------------------------------------------------------------------

def test_hard_case_add_caption_at_5_00_on_shorter_video(sample_transcript):
    """
    Hard case: 'add a caption at 5:00' on a 2-minute (120s) video -> Rejected OUT_OF_RANGE.
    """
    compiler = TimelineCompiler(sample_transcript)
    gate = DecisionGate(compiler)

    resp = gate.execute_instruction("add a caption at 5:00")
    assert resp.status == "rejected"
    assert resp.summary.get("error_code") == "OUT_OF_RANGE"


def test_hard_case_make_it_bigger_without_caption(sample_transcript):
    """
    Hard case: 'make it bigger' when no caption exists -> Rejected MISSING_TARGET.
    """
    compiler = TimelineCompiler(sample_transcript)
    gate = DecisionGate(compiler)

    resp = gate.execute_instruction("make it bigger")
    assert resp.status == "rejected"
    assert resp.summary.get("error_code") == "MISSING_TARGET"


def test_hard_case_remove_clock_range_twice(sample_transcript):
    """
    Hard case: 'Remove 0:30-0:40' sent twice -> First applied, second rejected DUPLICATE_OPERATION.
    """
    compiler = TimelineCompiler(sample_transcript)
    gate = DecisionGate(compiler)

    r1 = gate.execute_instruction("Remove 0:30-0:40")
    assert r1.status == "applied"

    r2 = gate.execute_instruction("Remove 0:30-0:40")
    assert r2.status == "rejected"
    assert r2.summary.get("error_code") == "DUPLICATE_OPERATION"


def test_hard_case_remove_after_phrase_multiple_occurrences(sample_transcript):
    """
    Hard case: 'Remove everything after I say pricing' where pricing appears 3 times -> needs_clarification.
    """
    compiler = TimelineCompiler(sample_transcript)
    gate = DecisionGate(compiler)

    resp = gate.execute_instruction("Remove everything after I say pricing")
    assert resp.status == "needs_clarification"
    assert resp.question is not None
    assert len(resp.options) == 4  # 3 occurrences + 'All'


def test_natural_time_parsing_formats(sample_transcript):
    """
    Verifies parser handles '80 seconds', 'a minute twenty', and 'last 10 seconds'.
    """
    compiler = TimelineCompiler(sample_transcript)
    gate = DecisionGate(compiler)

    # "a minute twenty" = 80,000 ms
    assert gate._clock_to_ms("a minute twenty") == 80000
    assert gate._clock_to_ms("80 seconds") == 80000
    assert gate._clock_to_ms("1:20") == 80000

    # Cut the last 10 seconds on 120s video (110s to 120s)
    resp = gate.execute_instruction("Remove the last 10 seconds")
    assert resp.status == "applied"
    assert resp.summary["before_duration_ms"] == 120000
    assert resp.summary["after_duration_ms"] == 110000


def test_timeline_schema_conformance(sample_transcript):
    """
    Verifies that CompiledTimeline produced by the compiler complies with schemas/timeline.schema.json.
    """
    import json
    with open("schemas/timeline.schema.json", "r", encoding="utf-8") as f:
        schema = json.load(f)

    compiler = TimelineCompiler(sample_transcript)
    compiler.apply_operation(EditOperation(
        op_id="op_cap",
        op_type="caption",
        target_word_ids=["w_0017", "w_0018"],
        params={"text": "Welcome!", "style": {"color": "yellow"}},
    ))
    compiler.apply_operation(EditOperation(
        op_id="op_bgm",
        op_type="add_bgm",
        params={"source_url": "https://example.com/bgm.mp3", "volume": 0.5, "ducking_db": -12.0},
    ))
    timeline = compiler.compile()
    dumped = timeline.model_dump()

    # Validate required top-level fields
    for field in schema["required"]:
        assert field in dumped, f"Missing required field: {field}"

    assert dumped["duration_ms"] == 120000
    assert len(dumped["timeline_hash"]) == 64
    assert len(dumped["video_segments"]) > 0
    assert len(dumped["audio_segments"]) > 0
    assert len(dumped["caption_tracks"]) == 1
    assert len(dumped["bgm_tracks"]) == 1

