"""Quick end-to-end test for upload + analysis pipeline."""
import requests
import time
import os

WAV_PATH = os.path.join(os.environ["TEMP"], "test_upload.wav")

# Upload test
with open(WAV_PATH, "rb") as f:
    files = {"file": ("test.wav", f, "audio/wav")}
    resp = requests.post("http://localhost:8000/api/v1/calls", files=files)

print("Upload:", resp.status_code, resp.json())

if resp.status_code in (200, 201, 202):
    call_id = resp.json()["call_id"]
    print(f"\nPolling status for call_id={call_id}...")
    
    status = None
    for i in range(10):
        time.sleep(1)
        status_resp = requests.get(f"http://localhost:8000/api/v1/calls/{call_id}/status")
        status = status_resp.json()
        s = status["status"]
        print(f"  [{i+1}s] Status: {s}")
        if s in ("completed", "failed"):
            err = status.get("error")
            if err:
                print(f"  Error: {err[:200]}")
            break
    
    if status and status["status"] == "completed":
        report = requests.get(f"http://localhost:8000/api/v1/calls/{call_id}/report")
        print(f"\nReport status code: {report.status_code}")
        if report.status_code == 200:
            r = report.json()
            print(f"Risk level: {r.get('level')}")
            print(f"Risk score: {r.get('score')}")
            print("SUCCESS - Full pipeline works!")
        else:
            print(f"Report error: {report.text[:200]}")
