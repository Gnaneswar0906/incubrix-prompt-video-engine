"""
IncuBrix CLI Session Runner
Executes scripted video editing sessions against the engine/API.
Produces results.json, final_timeline.json, final_timeline.otio, manifest.json, and rendered.mp4.
"""

from __future__ import annotations

import argparse
import copy
import datetime
import json
import logging
import os
import sys
import time
from typing import Any, Dict, List, Optional, Tuple
import yaml

# Ensure repository root is on sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from adapters.mock_adapter import MockSTTVADAdapter
from engine.compiler import TimelineCompiler
from engine.gate import DecisionGate
from engine.models import (
    CompiledTimeline,
    EditOperation,
    InstructionResponse,
    TranscriptIndex,
)
from media.intake import inspect_media
from media.otio_export import export_to_otio
from media.renderer import TimelineRenderer
from service.manifest import create_manifest

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("incubrix.session_runner")


def load_session_file(file_path: str) -> Dict[str, Any]:
    """Loads session file from YAML or JSON format."""
    if not os.path.exists(file_path):
        raise FileNotFoundError(f"Session file not found: {file_path}")

    with open(file_path, "r", encoding="utf-8") as f:
        content = f.read()

    try:
        data = yaml.safe_load(content)
        if isinstance(data, dict):
            return data
    except Exception:
        pass

    return json.loads(content)


def resolve_media_and_transcript(video_path: str) -> Tuple[str, TranscriptIndex]:
    """Resolves video path and associated ground-truth or transcribed index."""
    abs_path = os.path.abspath(video_path)
    if not os.path.exists(abs_path):
        # Look in test_media
        cand = os.path.abspath(os.path.join("test_media", os.path.basename(video_path)))
        if os.path.exists(cand):
            abs_path = cand

    base_without_ext = os.path.splitext(abs_path)[0]
    candidate_transcripts = [
        f"{base_without_ext}_transcript.json",
        f"{base_without_ext}.json",
    ]

    for c in candidate_transcripts:
        if os.path.exists(c):
            logger.info(f"Loaded ground-truth transcript from {c}")
            with open(c, "r", encoding="utf-8") as f:
                data = json.load(f)
            return abs_path, TranscriptIndex.model_validate(data)

    # Fallback to inspecting media and MockSTTVADAdapter
    dur_ms = 90000
    if os.path.exists(abs_path):
        try:
            meta = inspect_media(abs_path)
            dur_ms = meta.duration_ms
        except Exception:
            pass

    stt = MockSTTVADAdapter()
    transcript, _ = stt.transcribe(abs_path, video_duration_ms=dur_ms)
    return abs_path, transcript


def run_session(
    session_data: Dict[str, Any],
    output_dir: str = "./data/session_outputs",
    fps: float = 30.0,
) -> Dict[str, Any]:
    """
    Executes a session definition:
    1. Resolves video and ground-truth transcript
    2. Runs steps sequentially through DecisionGate
    3. Handles needs_clarification with scripted answers
    4. Renders final MP4 video and exports .otio
    5. Saves all artifacts into output_dir
    """
    os.makedirs(output_dir, exist_ok=True)
    video_ref = session_data.get("video") or session_data.get("video_url") or "test_media/single_speaker_interview.mp4"
    logger.info(f"Starting session for video: {video_ref}")

    video_path, transcript = resolve_media_and_transcript(video_ref)
    compiler = TimelineCompiler(transcript)
    gate = DecisionGate(compiler)

    steps = session_data.get("steps", [])
    step_results: List[Dict[str, Any]] = []

    for idx, step in enumerate(steps):
        say_text = step.get("say", "") if isinstance(step, dict) else str(step)
        scripted_answer = step.get("answer") if isinstance(step, dict) else None
        step_num = idx + 1

        logger.info(f"--- Step {step_num}: \"{say_text}\" ---")

        # Execute instruction
        resp = gate.execute_instruction(say_text, step_number=step_num)
        logger.info(f"Result: {resp.status.upper()}")

        # Auto-handle disambiguation if needs_clarification
        if resp.status == "needs_clarification":
            logger.info(f"Clarification Question: {resp.question}")
            logger.info(f"Options: {resp.options}")

            answer = scripted_answer or "the second one"
            logger.info(f"Supplying answer: \"{answer}\"")

            # Map choice string into choice index
            choice_idx = 0
            if "second" in answer.lower() or "2" in answer:
                choice_idx = 1
            elif "third" in answer.lower() or "3" in answer:
                choice_idx = 2

            clarify_payload = {
                "op_type": "cut",
                "phrase": say_text,
                "disambiguated_choice": choice_idx,
            }
            resp_after = gate.execute_instruction(clarify_payload, step_number=step_num)
            logger.info(f"Clarification Result: {resp_after.status.upper()}")

            step_results.append({
                "step": step_num,
                "instruction": say_text,
                "status": "needs_clarification_resolved",
                "question": resp.question,
                "options": resp.options,
                "supplied_answer": answer,
                "final_status": resp_after.status,
                "summary": resp_after.summary,
                "timeline_hash": resp_after.timeline_hash,
                "duration_s": resp_after.duration_s,
                "warnings": resp_after.warnings,
            })
        else:
            step_results.append({
                "step": step_num,
                "instruction": say_text,
                "status": resp.status,
                "summary": resp.summary,
                "timeline_hash": resp.timeline_hash,
                "duration_s": resp.duration_s,
                "warnings": resp.warnings,
            })

    # Compile final state
    final_timeline = compiler.compile()
    logger.info(f"Final timeline compiled: duration={final_timeline.duration_s}s, hash={final_timeline.timeline_hash}")

    # File paths
    out_timeline_json = os.path.join(output_dir, "final_timeline.json")
    out_otio_path = os.path.join(output_dir, "final_timeline.otio")
    out_manifest_json = os.path.join(output_dir, "manifest.json")
    out_results_json = os.path.join(output_dir, "results.json")
    out_rendered_mp4 = os.path.join(output_dir, "rendered.mp4")

    # 1. Save final_timeline.json
    with open(out_timeline_json, "w", encoding="utf-8") as f:
        json.dump(final_timeline.model_dump(), f, indent=2)

    # 2. Export OTIO
    export_to_otio(final_timeline, out_otio_path, media_reference_path=video_path, fps=fps)

    # 3. Render MP4
    if os.path.exists(video_path):
        renderer = TimelineRenderer(fps=fps)
        renderer.render(final_timeline, video_path, out_rendered_mp4)
    else:
        with open(out_rendered_mp4, "wb") as f:
            f.write(b"mock_mp4_rendered_content")

    # 4. Create manifest
    manifest = create_manifest(
        session_id=f"cli_ses_{int(time.time())}",
        job_id=f"job_cli_{int(time.time())}",
        job_type="cli_session",
        status="succeeded",
        duration_ms=final_timeline.duration_ms,
        settings={"fps": fps, "duration_s": final_timeline.duration_s},
        warnings=final_timeline.warnings,
    )
    with open(out_manifest_json, "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2)

    # 5. Save results.json
    results_payload = {
        "timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "video": video_path,
        "total_steps": len(steps),
        "steps": step_results,
        "final_timeline_hash": final_timeline.timeline_hash,
        "final_duration_s": final_timeline.duration_s,
        "artifacts": {
            "results_json": out_results_json,
            "final_timeline_json": out_timeline_json,
            "final_timeline_otio": out_otio_path,
            "manifest_json": out_manifest_json,
            "rendered_mp4": out_rendered_mp4,
        },
    }
    with open(out_results_json, "w", encoding="utf-8") as f:
        json.dump(results_payload, f, indent=2)

    logger.info(f"Session execution completed! All artifacts written to: {output_dir}")
    return results_payload


def main():
    parser = argparse.ArgumentParser(description="IncuBrix CLI Session Runner")
    parser.add_argument("session_file", nargs="?", default="examples/worked_example_session.yaml", help="Path to YAML or JSON session file")
    parser.add_argument("--output-dir", "-o", default="./data/session_outputs", help="Output directory for generated artifacts")
    parser.add_argument("--fps", type=float, default=30.0, help="Video frame rate for rendering")
    args = parser.parse_args()

    data = load_session_file(args.session_file)
    run_session(data, output_dir=args.output_dir, fps=args.fps)


if __name__ == "__main__":
    main()
