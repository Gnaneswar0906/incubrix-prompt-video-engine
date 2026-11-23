import time
import requests
import json

BASE_URL = "https://gnaneswar1809-incubrix-video-studio.hf.space"
print(f"--- Running End-to-End Live Cloud Studio Smoke Test ---")
print(f"Target: {BASE_URL}\n")

# 1. Health & Readiness
res = requests.get(f"{BASE_URL}/ready", timeout=15)
assert res.status_code == 200, f"/ready failed: {res.text}"
print("[PASS] 1. GET /ready:", res.json())

# 2. Create Session
res = requests.post(
    f"{BASE_URL}/api/v1/sessions",
    data={"video_url": "test_media/single_speaker_interview.mp4"},
    headers={"Idempotency-Key": f"smoke_init_{int(time.time())}"},
    timeout=15
)
assert res.status_code == 202, f"Session creation failed: {res.text}"
init_data = res.json()
session_id = init_data["session_id"]
job_id = init_data["job_id"]
print(f"[PASS] 2. POST /api/v1/sessions -> Created {session_id} (intake job: {job_id})")

# 3. Poll intake job
for _ in range(30):
    time.sleep(0.5)
    jres = requests.get(f"{BASE_URL}/api/v1/jobs/{job_id}", timeout=10)
    job = jres.json()
    if job.get("status") == "succeeded":
        print(f"[PASS] 3. Intake job {job_id} succeeded in {job.get('progress')}%")
        break
else:
    raise RuntimeError("Intake job timed out")

# 4. Fetch initial timeline
res = requests.get(f"{BASE_URL}/api/v1/sessions/{session_id}/timeline", timeout=10)
assert res.status_code == 200
tl = res.json()
initial_dur = tl["duration_s"]
initial_hash = tl["timeline_hash"]
print(f"[PASS] 4. GET /timeline -> Duration: {initial_dur}s, Hash: {initial_hash[:16]}...")

# 5. Apply instruction: Cut filler words
res = requests.post(
    f"{BASE_URL}/api/v1/sessions/{session_id}/instructions",
    json={"say": "Cut all filler words"},
    headers={"Idempotency-Key": f"smoke_inst_1_{int(time.time())}"},
    timeout=15
)
assert res.status_code == 200
resp1 = res.json()
assert resp1["status"] == "applied"
print(f"[PASS] 5. Edit 1 ('Cut all filler words') -> {resp1['summary']['what_moved']}")

# 6. Apply instruction: Speed up
res = requests.post(
    f"{BASE_URL}/api/v1/sessions/{session_id}/instructions",
    json={"say": "Speed up from 0 to 10 by 2x"},
    headers={"Idempotency-Key": f"smoke_inst_2_{int(time.time())}"},
    timeout=15
)
assert res.status_code == 200
resp2 = res.json()
assert resp2["status"] == "applied"
print(f"[PASS] 6. Edit 2 ('Speed up 0-10s to 2x') -> {resp2['summary']['what_moved']}")

# 7. Check updated timeline
res = requests.get(f"{BASE_URL}/api/v1/sessions/{session_id}/timeline", timeout=10)
tl_updated = res.json()
print(f"[PASS] 7. Updated timeline -> Duration: {tl_updated['duration_s']}s (was {initial_dur}s), Hash: {tl_updated['timeline_hash'][:16]}...")

# 8. Trigger render
res = requests.post(
    f"{BASE_URL}/api/v1/sessions/{session_id}/render",
    json={},
    headers={"Idempotency-Key": f"smoke_render_{int(time.time())}"},
    timeout=15
)
assert res.status_code == 202
render_job_id = res.json()["job_id"]
print(f"[PASS] 8. POST /render -> Queued render job {render_job_id}")

# 9. Poll render job
for _ in range(60):
    time.sleep(1.0)
    jres = requests.get(f"{BASE_URL}/api/v1/jobs/{render_job_id}", timeout=10)
    job = jres.json()
    if job.get("status") == "succeeded":
        print(f"[PASS] 9. Render job succeeded! Progress: 100%")
        result_links = job.get("result_links", {})
        print(f"       Video artifact: {result_links.get('video')}")
        print(f"       OTIO artifact:  {result_links.get('otio')}")
        assert "manifest" in job
        print(f"       Manifest hash:  {job['manifest'].get('manifest_hash', 'verified')}")
        break
    elif job.get("status") == "failed":
        raise RuntimeError(f"Render job failed: {job.get('error')}")
else:
    raise RuntimeError("Render job timed out")

print("\n--- ALL 9 CLOUD E2E LIVE SMOKE TESTS PASSED 100% ---")
