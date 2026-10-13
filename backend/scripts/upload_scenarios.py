"""
Upload every audio file in a folder, wait for analysis, save results to CSV.


"""
import argparse
import csv
import sys
import time
from pathlib import Path

import httpx

ALLOWED = {".wav", ".mp3", ".m4a"}


def process_file(client: httpx.Client, path: Path, timeout_s: int) -> dict:
    row = {"file": path.name, "call_id": "", "status": "", "level": "", "error": ""}
    try:
        with path.open("rb") as fh:
            r = client.post("/calls", files={"file": (path.name, fh, "application/octet-stream")})
        r.raise_for_status()
        call_id = r.json()["call_id"]
        row["call_id"] = call_id

        start = time.time()
        while True:
            s = client.get(f"/calls/{call_id}/status").json()
            if s["status"] in ("completed", "failed"):
                break
            if time.time() - start > timeout_s:
                raise TimeoutError("analysis timed out")
            time.sleep(1)

        row["status"] = s["status"]
        if s["status"] == "completed":
            report = client.get(f"/calls/{call_id}/report").json()
            row["level"] = report["level"]
        else:
            row["error"] = s.get("error_message") or ""
    except Exception as exc:
        row["status"] = "error"
        row["error"] = str(exc)
    return row


def main():
    parser = argparse.ArgumentParser(description="Batch-upload recordings to VISHWAS")
    parser.add_argument("folder", help="Folder containing .wav/.mp3/.m4a files")
    parser.add_argument("--base", default="http://localhost:8000/api/v1", help="API base URL")
    parser.add_argument("--timeout", type=int, default=120, help="Seconds to wait per file")
    args = parser.parse_args()

    folder = Path(args.folder)
    files = sorted(p for p in folder.iterdir() if p.suffix.lower() in ALLOWED)
    if not files:
        sys.exit(f"No audio files found in {folder}")

    rows = []
    with httpx.Client(base_url=args.base, timeout=60) as client:
        for path in files:
            row = process_file(client, path, args.timeout)
            print(f"{row['file']:40} {row['status']:10} {row['level']:8} {row['error']}")
            rows.append(row)

    out_csv = folder / "results.csv"
    with out_csv.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=["file", "call_id", "status", "level", "error"])
        writer.writeheader()
        writer.writerows(rows)

    done = sum(1 for r in rows if r["status"] == "completed")
    print(f"\n{done}/{len(rows)} completed. Saved to {out_csv}")


if __name__ == "__main__":
    main()