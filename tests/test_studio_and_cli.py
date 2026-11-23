"""
IncuBrix Studio UI, CLI Session Runner, and Test Media Integration Tests
Verifies:
- Web Studio UI serving at / and static assets (/static/styles.css, /static/app.js)
- Sample test media listing and existence of all synthetic test files
- 60-minute benchmark scale test (< 3s compilation on ~9,000 words)
- CLI session runner executing 8-step worked example end-to-end (YAML and JSON)
- Artifact generation: results.json, final_timeline.json, final_timeline.otio, manifest.json, rendered.mp4
"""

from __future__ import annotations

import json
import os
import time
import pytest
from fastapi.testclient import TestClient

from cli.session_runner import load_session_file, run_session
from engine.compiler import TimelineCompiler
from engine.models import TranscriptIndex
from service.app import app


@pytest.fixture
def client():
    return TestClient(app)


# -----------------------------------------------------------------------------
# 1. Studio UI & Static Asset Serving
# -----------------------------------------------------------------------------

def test_studio_root_serving(client):
    """GET / serves the dark-mode Web Studio index.html."""
    resp = client.get("/")
    assert resp.status_code == 200
    assert "IncuBrix Studio" in resp.text
    assert "<!DOCTYPE html>" in resp.text


def test_static_assets_serving(client):
    """CSS and JS static assets are served properly."""
    res_css = client.get("/static/styles.css")
    assert res_css.status_code == 200
    assert "dark-theme" in res_css.text

    res_js = client.get("/static/app.js")
    assert res_js.status_code == 200
    assert "initializeSession" in res_js.text


def test_samples_endpoint(client):
    """GET /api/v1/samples returns built-in test media list."""
    resp = client.get("/api/v1/samples")
    assert resp.status_code == 200
    data = resp.json()
    assert "samples" in data
    filenames = [s["filename"] for s in data["samples"]]
    assert "single_speaker_interview.mp4" in filenames
    assert "two_speaker_podcast.mp4" in filenames


# -----------------------------------------------------------------------------
# 2. Synthetic Test Media File Verification
# -----------------------------------------------------------------------------

def test_synthetic_test_media_files_exist():
    """Confirms all 4 synthetic videos and ground-truth transcripts exist."""
    required_files = [
        "test_media/single_speaker_interview.mp4",
        "test_media/single_speaker_interview_transcript.json",
        "test_media/two_speaker_podcast.mp4",
        "test_media/two_speaker_podcast_transcript.json",
        "test_media/vfr_phone_clip.mp4",
        "test_media/no_audio_clip.mp4",
        "test_media/benchmark_60min_transcript.json",
    ]
    for rf in required_files:
        assert os.path.exists(rf), f"Required synthetic media file missing: {rf}"


# -----------------------------------------------------------------------------
# 3. 60-Minute Benchmark Scale Test (< 3.0s)
# -----------------------------------------------------------------------------

def test_benchmark_60min_scale():
    """
    Asserts compiling a 60-minute timeline with ~9,000 words executes in < 3.0 seconds.
    """
    benchmark_path = os.path.abspath("test_media/benchmark_60min_transcript.json")
    with open(benchmark_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    transcript = TranscriptIndex.model_validate(data)
    assert len(transcript.words) >= 8000, f"Expected ~9,000 words, got {len(transcript.words)}"

    compiler = TimelineCompiler(transcript)

    start_time = time.time()
    compiled = compiler.compile()
    elapsed = time.time() - start_time

    assert elapsed < 3.0, f"Benchmark compilation took {elapsed:.3f}s (must be < 3.0s)"
    assert compiled.duration_ms == 3600000
    assert len(compiled.timeline_hash) == 64


# -----------------------------------------------------------------------------
# 4. CLI Session Runner End-to-End Execution (YAML & JSON)
# -----------------------------------------------------------------------------

def test_cli_session_runner_worked_example_yaml(tmp_path):
    """
    Executes the 8-step worked example through cli/session_runner.py on YAML format.
    Verifies all steps, clarification resolution, and artifact outputs.
    """
    yaml_file = os.path.abspath("examples/worked_example_session.yaml")
    out_dir = str(tmp_path / "yaml_run")

    session_data = load_session_file(yaml_file)
    results = run_session(session_data, output_dir=out_dir)

    assert results["total_steps"] == 7
    # Step 3 must be resolved with the scripted answer
    step3 = results["steps"][2]
    assert step3["status"] == "needs_clarification_resolved"
    assert step3["supplied_answer"] == "the second one"
    assert step3["final_status"] == "applied"

    # All 5 required artifacts must exist
    assert os.path.exists(os.path.join(out_dir, "results.json"))
    assert os.path.exists(os.path.join(out_dir, "final_timeline.json"))
    assert os.path.exists(os.path.join(out_dir, "final_timeline.otio"))
    assert os.path.exists(os.path.join(out_dir, "manifest.json"))
    assert os.path.exists(os.path.join(out_dir, "rendered.mp4"))

    # Final timeline duration check (90s video, 30s cut, 30s at 2x speed -> 45s)
    assert results["final_duration_s"] == 45.0
    assert len(results["final_timeline_hash"]) == 64


def test_cli_session_runner_worked_example_json(tmp_path):
    """
    Executes the worked example on JSON format and confirms identical deterministic hash.
    """
    json_file = os.path.abspath("examples/worked_example_session.json")
    out_dir = str(tmp_path / "json_run")

    session_data = load_session_file(json_file)
    results = run_session(session_data, output_dir=out_dir)

    assert results["final_duration_s"] == 45.0
    assert results["final_timeline_hash"] == "8fd0974be99db287748f759c15dd62b09c7a075a5937a5ba93dd78a0c78f838d"
