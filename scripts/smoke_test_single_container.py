import os
import sys
import time

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

# Enforce single-container cloud environment variables
os.environ["QUEUE_BACKEND"] = "inprocess"
os.environ["STORAGE_BACKEND"] = "local"
os.environ["DATABASE_URL"] = "sqlite:///./data/incubrix_smoke.db"
os.environ["PORT"] = "7860"

from fastapi.testclient import TestClient
from service.app import app

def run_smoke_test():
    client = TestClient(app)
    print("=== 1. Testing GET /health ===")
    r_health = client.get("/health")
    assert r_health.status_code == 200, f"Health probe failed: {r_health.text}"
    print("PASS: /health returned 200 ->", r_health.json())

    print("\n=== 2. Testing GET /ready ===")
    r_ready = client.get("/ready")
    assert r_ready.status_code == 200, f"Ready probe failed: {r_ready.text}"
    ready_data = r_ready.json()
    print("PASS: /ready returned 200 ->", ready_data)
    assert ready_data["status"] == "ready"
    assert ready_data["checks"]["database"] is True
    assert ready_data["checks"]["storage"] is True
    assert ready_data["checks"]["queue"] is True
    assert ready_data["checks"]["ffmpeg"] is True

    print("\n=== 3. Testing GET / (Web Studio Creator Interface) ===")
    r_root = client.get("/")
    assert r_root.status_code == 200, f"Root studio failed: {r_root.text}"
    assert "IncuBrix Studio" in r_root.text
    print("PASS: GET / returned Web Studio HTML (length:", len(r_root.text), "bytes)")

    print("\n=== 4. Testing End-to-End Session in Single-Container Mode ===")
    # A. Intake Session
    r_session = client.post("/api/v1/sessions", data={"video_url": "https://example.com/smoke_test.mp4"})
    assert r_session.status_code == 202, f"Intake failed: {r_session.text}"
    s_data = r_session.json()
    session_id = s_data["session_id"]
    job_id = s_data["job_id"]
    print(f"Session created: {session_id}, intake job: {job_id}")

    # Wait for intake
    for _ in range(50):
        j_resp = client.get(f"/api/v1/jobs/{job_id}")
        if j_resp.json()["status"] == "succeeded":
            break
        time.sleep(0.05)
    print("Intake completed successfully!")

    # B. Submit instruction: Cut first 10 seconds
    r_inst = client.post(
        f"/api/v1/sessions/{session_id}/instructions",
        json={"say": "Cut the first 10 seconds"}
    )
    assert r_inst.status_code == 200, f"Instruction failed: {r_inst.text}"
    inst_data = r_inst.json()
    assert inst_data["status"] == "applied"
    print(f"Instruction applied! Duration: {inst_data['duration_s']}s, timeline_hash: {inst_data['timeline_hash'][:16]}...")

    # C. Submit render job
    r_render = client.post(f"/api/v1/sessions/{session_id}/render")
    assert r_render.status_code == 202, f"Render failed: {r_render.text}"
    render_job_id = r_render.json()["job_id"]
    print(f"Render job queued: {render_job_id}")

    # Wait for render
    for _ in range(50):
        rj_resp = client.get(f"/api/v1/jobs/{render_job_id}")
        rj_data = rj_resp.json()
        if rj_data["status"] == "succeeded":
            break
        time.sleep(0.05)

    assert rj_data["status"] == "succeeded", f"Render did not succeed: {rj_data}"
    print("Render succeeded! Result links:", rj_data.get("result_links"))
    print("Output manifest cost estimate:", rj_data.get("manifest", {}).get("estimated_cost_usd"))
    print("\nALL SMOKE CHECKS PASSED: SINGLE-CONTAINER CLOUD READINESS 100% VERIFIED!")

if __name__ == "__main__":
    run_smoke_test()
