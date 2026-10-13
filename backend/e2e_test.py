"""
End-to-end upload and analysis test.
Creates a minimal valid WAV file and submits it through the API.
"""
import struct
import io
import time
import requests

BASE_URL = "http://localhost:8000/api/v1"

def make_wav_bytes(duration_s=1, sample_rate=16000):
    """Create a minimal 16kHz mono WAV file in memory."""
    num_samples = int(sample_rate * duration_s)
    # Silent PCM16 samples
    samples = bytes(num_samples * 2)  # 16-bit = 2 bytes per sample

    # WAV header
    data_size = len(samples)
    header = struct.pack(
        '<4sI4s4sIHHIIHH4sI',
        b'RIFF',
        36 + data_size,         # file size - 8
        b'WAVE',
        b'fmt ',
        16,                     # chunk size
        1,                      # PCM
        1,                      # mono
        sample_rate,
        sample_rate * 2,        # byte rate
        2,                      # block align
        16,                     # bits per sample
        b'data',
        data_size,
    )
    return header + samples


def test_upload_and_analyze():
    wav_data = make_wav_bytes(duration_s=2)
    print(f"[*] WAV file size: {len(wav_data)} bytes")

    # 1. Upload
    resp = requests.post(
        f"{BASE_URL}/analyze/recording",
        files={"file": ("test.wav", io.BytesIO(wav_data), "audio/wav")},
        timeout=15,
    )
    print(f"\n[1] POST /analyze/recording  => {resp.status_code}")
    print(resp.json())
    if resp.status_code != 202:
        print("FAIL: upload rejected")
        return

    call_id = resp.json()["call_id"]

    # 2. Poll status until done (max 30 s)
    for i in range(15):
        time.sleep(2)
        status_resp = requests.get(f"{BASE_URL}/call/{call_id}/status", timeout=10)
        status = status_resp.json().get("status")
        print(f"[2] Poll #{i+1}: status={status}")
        if status in ("completed", "failed"):
            break
    else:
        print("FAIL: timed out waiting for analysis")
        return

    if status == "failed":
        print("FAIL: analysis failed:", status_resp.json())
        return

    # 3. Fetch report
    report_resp = requests.get(f"{BASE_URL}/call/{call_id}/state", timeout=10)
    print(f"\n[3] GET /call/{call_id}/state  => {report_resp.status_code}")
    data = report_resp.json()
    print(f"    risk_level={data.get('level')}  score={data.get('score')}")
    print(f"    warnings={data.get('warnings')}")
    print("\nSUCCESS: Full pipeline working!")


if __name__ == "__main__":
    test_upload_and_analyze()
