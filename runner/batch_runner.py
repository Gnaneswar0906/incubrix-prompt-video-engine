"""
IncuBrix Batch Script Runner (Integration Standard Point 10)
Runs scripted editing sessions against the HTTP API service and aggregates results.
"""

from __future__ import annotations

import argparse
import datetime
import json
import logging
import os
import sys
import time
from typing import Any, Dict, List, Optional, Tuple
import urllib.error
import urllib.parse
import urllib.request

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("incubrix.batch_runner")


def _http_request(url: str, method: str = "GET", data: Optional[Dict[str, Any]] = None, headers: Optional[Dict[str, str]] = None) -> Tuple[int, Dict[str, Any]]:
    req_headers = {"User-Agent": "IncuBrix-BatchRunner/1.0", **(headers or {})}
    req_body = None

    if data is not None:
        if "Content-Type" not in req_headers:
            req_headers["Content-Type"] = "application/json"
            req_body = json.dumps(data).encode("utf-8")
        else:
            req_body = urllib.parse.urlencode(data).encode("utf-8")

    req = urllib.request.Request(url, data=req_body, headers=req_headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            status_code = resp.status
            content = resp.read().decode("utf-8")
            return status_code, json.loads(content) if content else {}
    except urllib.error.HTTPError as err:
        content = err.read().decode("utf-8")
        try:
            parsed = json.loads(content)
        except Exception:
            parsed = {"raw": content}
        return err.code, parsed


def poll_job(base_url: str, job_id: str, timeout_s: int = 120, interval_s: float = 0.5) -> Dict[str, Any]:
    """Polls a job until succeeded or failed."""
    start = time.time()
    url = f"{base_url}/api/v1/jobs/{job_id}"
    while time.time() - start < timeout_s:
        status_code, job = _http_request(url, method="GET")
        if status_code == 200:
            job_status = job.get("status")
            if job_status in ("succeeded", "failed"):
                return job
        time.sleep(interval_s)
    raise TimeoutError(f"Job {job_id} did not complete within {timeout_s}s")


def run_session_script(base_url: str, script: Dict[str, Any], output_dir: str) -> Dict[str, Any]:
    """
    Executes a single session script:
    1. Create session (intake)
    2. Wait for intake completion
    3. Apply sequence of instructions
    4. Render output
    5. Save artifacts to output_dir
    """
    session_title = script.get("title", "unnamed_session")
    logger.info(f"--- Running Session: {session_title} ---")

    # 1. Intake
    create_url = f"{base_url}/api/v1/sessions"
    video_url = script.get("video_url", "https://example.com/demo.mp4")
    intake_data = {"video_url": video_url}
    
    status_code, intake_resp = _http_request(
        create_url,
        method="POST",
        data=intake_data,
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )
    if status_code != 202:
        raise RuntimeError(f"Intake failed: {intake_resp}")

    session_id = intake_resp["session_id"]
    job_id = intake_resp["job_id"]
    logger.info(f"Session created: {session_id}, waiting for intake job {job_id}...")

    intake_result = poll_job(base_url, job_id)
    if intake_result.get("status") != "succeeded":
        raise RuntimeError(f"Intake job failed: {intake_result}")

    # 2. Instructions
    instructions = script.get("instructions", [])
    instruction_results = []
    for idx, inst in enumerate(instructions):
        inst_text = inst if isinstance(inst, str) else inst.get("say", "")
        answer = inst.get("answer") if isinstance(inst, dict) else None

        inst_url = f"{base_url}/api/v1/sessions/{session_id}/instructions"
        payload = {"say": inst_text}
        if answer:
            payload["answer"] = answer

        st, inst_resp = _http_request(inst_url, method="POST", data=payload)
        logger.info(f"Step {idx+1}: '{inst_text}' -> {inst_resp.get('status')}")
        instruction_results.append({"instruction": inst_text, "response": inst_resp})

    # 3. Render
    render_url = f"{base_url}/api/v1/sessions/{session_id}/render"
    st, render_resp = _http_request(render_url, method="POST", data={})
    if st != 202:
        raise RuntimeError(f"Render submission failed: {render_resp}")

    render_job_id = render_resp["job_id"]
    logger.info(f"Render job submitted: {render_job_id}, waiting for completion...")
    render_result = poll_job(base_url, render_job_id)

    # 4. Fetch final timeline
    tl_url = f"{base_url}/api/v1/sessions/{session_id}/timeline"
    st, timeline = _http_request(tl_url, method="GET")

    # 5. Save outputs
    session_out_dir = os.path.join(output_dir, session_id)
    os.makedirs(session_out_dir, exist_ok=True)

    with open(os.path.join(session_out_dir, "timeline.json"), "w") as f:
        json.dump(timeline, f, indent=2)

    with open(os.path.join(session_out_dir, "manifest.json"), "w") as f:
        json.dump(render_result.get("manifest", {}), f, indent=2)

    with open(os.path.join(session_out_dir, "summary.json"), "w") as f:
        summary_data = {
            "session_id": session_id,
            "title": session_title,
            "status": render_result.get("status"),
            "duration_s": timeline.get("duration_s"),
            "timeline_hash": timeline.get("timeline_hash"),
            "instructions": instruction_results,
            "result_links": render_result.get("result_links", {}),
        }
        json.dump(summary_data, f, indent=2)

    logger.info(f"Session {session_id} completed successfully. Hash: {timeline.get('timeline_hash')}")
    return summary_data


def run_batch(input_path: str, base_url: str = "http://localhost:8000", output_dir: str = "./data/batch_outputs") -> Dict[str, Any]:
    os.makedirs(output_dir, exist_ok=True)
    with open(input_path, "r", encoding="utf-8") as f:
        scripts = json.load(f)

    if isinstance(scripts, dict):
        scripts = [scripts]

    overall_results = []
    for s in scripts:
        res = run_session_script(base_url, s, output_dir)
        overall_results.append(res)

    batch_summary = {
        "batch_timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "total_sessions": len(overall_results),
        "results": overall_results,
    }

    summary_file = os.path.join(output_dir, "results.json")
    with open(summary_file, "w", encoding="utf-8") as f:
        json.dump(batch_summary, f, indent=2)

    logger.info(f"Batch completed. Results saved to {summary_file}")
    return batch_summary


def main():
    parser = argparse.ArgumentParser(description="IncuBrix Batch Script Runner")
    parser.add_argument("--input", "-i", required=True, help="Path to input scripts JSON file")
    parser.add_argument("--api-url", default="http://localhost:8000", help="Base URL of IncuBrix API")
    parser.add_argument("--output-dir", "-o", default="./data/batch_outputs", help="Output directory")
    args = parser.parse_args()

    run_batch(args.input, base_url=args.api_url, output_dir=args.output_dir)


if __name__ == "__main__":
    main()
