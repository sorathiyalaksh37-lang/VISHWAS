"""
AI Voice Detector — Evaluation Script

Runs the detector on labeled audio samples and reports precision, recall,
false-positive rate, and a confusion matrix.

Usage:
    python -m scripts.evaluate_detector --manifest evaluation_manifest.jsonl

Manifest format (JSONL, one entry per line):
    {"path": "data/genuine/speaker1.wav", "label": "genuine", "speaker": "A", "notes": "recorded locally"}
    {"path": "data/synthetic/tts_sample1.wav", "label": "synthetic", "speaker": "A", "notes": "ElevenLabs clone"}

Labels:
    genuine   — Real human speech
    synthetic — AI-generated, TTS, voice-cloned, or replayed speech

If no manifest is provided, the script generates synthetic test audio
(sine waves, noise, silence) and runs the detector on those. This is
a pipeline sanity check only — NOT a measure of detection accuracy.

Output:
    - Per-sample results table
    - Confusion matrix (if both labels present)
    - Precision, recall, FPR (if both labels present)
    - Clear statement of dataset size and limitations
"""
import argparse
import json
import math
import sys
import tempfile
import time
import wave
from pathlib import Path
from typing import Optional

import numpy as np

# Add backend to path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.audio.ai_voice_detector import AIVoiceDetector, AIVoiceStatus


def generate_test_audio(output_dir: Path) -> list[dict]:
    """
    Generate synthetic test audio for pipeline testing.

    WARNING: These are NOT real speech samples. Results on synthetic audio
    do not represent detection accuracy on real speech.
    """
    samples = []

    # Sine wave (440Hz, 5s) — a non-speech signal
    path = output_dir / "sine_440hz_5s.wav"
    _write_sine(path, duration=5.0, frequency=440, amplitude=0.3)
    samples.append({"path": str(path), "label": "synthetic", "notes": "440Hz sine wave (non-speech)"})

    # Random noise (5s) — a non-speech signal
    path = output_dir / "noise_5s.wav"
    _write_noise(path, duration=5.0, amplitude=0.1)
    samples.append({"path": str(path), "label": "synthetic", "notes": "Random noise (non-speech)"})

    # Mixed sine (varying frequency, 8s)
    path = output_dir / "chirp_8s.wav"
    _write_chirp(path, duration=8.0, f_start=200, f_end=2000, amplitude=0.2)
    samples.append({"path": str(path), "label": "synthetic", "notes": "Frequency chirp (non-speech)"})

    # Very quiet signal (near-silence)
    path = output_dir / "near_silence_5s.wav"
    _write_sine(path, duration=5.0, frequency=100, amplitude=0.0005)
    samples.append({"path": str(path), "label": "genuine", "notes": "Near-silence baseline"})

    # White noise at moderate volume (5s)
    path = output_dir / "moderate_noise_5s.wav"
    _write_noise(path, duration=5.0, amplitude=0.3)
    samples.append({"path": str(path), "label": "synthetic", "notes": "Moderate white noise"})

    return samples


def _write_sine(path: Path, duration: float, frequency: float, amplitude: float):
    n = int(16000 * duration)
    t = np.linspace(0, duration, n, endpoint=False)
    data = (amplitude * 32767 * np.sin(2 * np.pi * frequency * t)).astype(np.int16)
    with wave.open(str(path), "wb") as wf:
        wf.setnchannels(1); wf.setsampwidth(2); wf.setframerate(16000)
        wf.writeframes(data.tobytes())


def _write_noise(path: Path, duration: float, amplitude: float):
    n = int(16000 * duration)
    data = (amplitude * 32767 * np.random.randn(n)).clip(-32768, 32767).astype(np.int16)
    with wave.open(str(path), "wb") as wf:
        wf.setnchannels(1); wf.setsampwidth(2); wf.setframerate(16000)
        wf.writeframes(data.tobytes())


def _write_chirp(path: Path, duration: float, f_start: float, f_end: float, amplitude: float):
    n = int(16000 * duration)
    t = np.linspace(0, duration, n, endpoint=False)
    freq = f_start + (f_end - f_start) * t / duration
    data = (amplitude * 32767 * np.sin(2 * np.pi * np.cumsum(freq) / 16000)).astype(np.int16)
    with wave.open(str(path), "wb") as wf:
        wf.setnchannels(1); wf.setsampwidth(2); wf.setframerate(16000)
        wf.writeframes(data.tobytes())


def load_manifest(manifest_path: Path) -> list[dict]:
    """Load JSONL manifest of labeled audio samples."""
    samples = []
    with open(manifest_path, "r") as f:
        for line_num, line in enumerate(f, 1):
            line = line.strip()
            if not line:
                continue
            try:
                entry = json.loads(line)
                assert "path" in entry, "Missing 'path' field"
                assert "label" in entry, "Missing 'label' field"
                assert entry["label"] in ("genuine", "synthetic"), (
                    f"Label must be 'genuine' or 'synthetic', got '{entry['label']}'"
                )
                samples.append(entry)
            except Exception as e:
                print(f"[WARN] Skipping manifest line {line_num}: {e}")
    return samples


def evaluate(samples: list[dict], detector: AIVoiceDetector) -> dict:
    """
    Run detector on all samples and compute metrics.

    Returns a dict with per-sample results and aggregate metrics.
    """
    results = []
    tp = fp = tn = fn = 0
    inconclusive_count = 0
    unavailable_count = 0

    for i, sample in enumerate(samples):
        path = Path(sample["path"])
        label = sample["label"]
        notes = sample.get("notes", "")

        if not path.exists():
            print(f"[WARN] File not found: {path} -- skipping")
            results.append({
                **sample,
                "status": "file_not_found",
                "predicted": None,
                "spoof_score": None,
            })
            unavailable_count += 1
            continue

        t0 = time.perf_counter()
        result = detector.detect(path)
        elapsed = time.perf_counter() - t0

        status = result.ai_voice_status
        predicted = None

        if status == AIVoiceStatus.AI_GENERATED_OR_SPOOF_SUSPECTED.value:
            predicted = "synthetic"
        elif status == AIVoiceStatus.LIKELY_GENUINE.value:
            predicted = "genuine"
        elif status == AIVoiceStatus.INCONCLUSIVE.value:
            predicted = "inconclusive"
            inconclusive_count += 1
        else:
            predicted = "unavailable"
            unavailable_count += 1

        # Confusion matrix (only for definitive predictions)
        if predicted == "synthetic" and label == "synthetic":
            tp += 1
        elif predicted == "synthetic" and label == "genuine":
            fp += 1
        elif predicted == "genuine" and label == "genuine":
            tn += 1
        elif predicted == "genuine" and label == "synthetic":
            fn += 1

        results.append({
            **sample,
            "status": status,
            "predicted": predicted,
            "spoof_score": result.spoof_score,
            "genuine_score": result.genuine_score,
            "windows": result.windows_analyzed,
            "time_s": round(elapsed, 2),
        })

        symbol = "[PASS]" if predicted == label else ("[WARN]" if predicted in ("inconclusive", "unavailable") else "[FAIL]")
        spoof_display = f"{result.spoof_score:.4f}" if result.spoof_score is not None else "N/A"
        print(
            f"  [{i+1}/{len(samples)}] {symbol} "
            f"label={label:10s} predicted={predicted:12s} "
            f"spoof={spoof_display:>8} "
            f"({elapsed:.1f}s) {path.name}"
        )

    # Compute metrics
    total_definitive = tp + fp + tn + fn
    metrics = {
        "total_samples": len(samples),
        "definitive_predictions": total_definitive,
        "inconclusive_count": inconclusive_count,
        "unavailable_count": unavailable_count,
        "true_positives": tp,
        "false_positives": fp,
        "true_negatives": tn,
        "false_negatives": fn,
    }

    if total_definitive > 0:
        metrics["accuracy"] = round((tp + tn) / total_definitive, 4) if total_definitive else None
        metrics["precision"] = round(tp / (tp + fp), 4) if (tp + fp) > 0 else None
        metrics["recall"] = round(tp / (tp + fn), 4) if (tp + fn) > 0 else None
        metrics["fpr"] = round(fp / (fp + tn), 4) if (fp + tn) > 0 else None

    return {"results": results, "metrics": metrics}


def print_report(evaluation: dict, is_synthetic_data: bool = False):
    """Print a formatted evaluation report."""
    metrics = evaluation["metrics"]

    print("\n" + "=" * 72)
    print("AI VOICE DETECTOR — EVALUATION REPORT")
    print("=" * 72)

    if is_synthetic_data:
        print("\n[WARN] This evaluation uses SYNTHETIC test audio (sine waves,")
        print("   noise), NOT real speech. Results do NOT represent detection accuracy")
        print("   on real human speech vs real AI-generated speech.")
        print("   To measure real accuracy, provide a manifest with labeled speech samples.")

    print(f"\n  Total samples:             {metrics['total_samples']}")
    print(f"  Definitive predictions:    {metrics['definitive_predictions']}")
    print(f"  Inconclusive:              {metrics['inconclusive_count']}")
    print(f"  Unavailable:               {metrics['unavailable_count']}")

    if metrics["definitive_predictions"] > 0:
        print(f"\n  Confusion Matrix:")
        print(f"                    Predicted Synthetic  Predicted Genuine")
        print(f"  Actual Synthetic:  TP={metrics['true_positives']:>4}             FN={metrics['false_negatives']:>4}")
        print(f"  Actual Genuine:    FP={metrics['false_positives']:>4}             TN={metrics['true_negatives']:>4}")

        if metrics.get("accuracy") is not None:
            print(f"\n  Accuracy:    {metrics['accuracy']:.2%}")
        if metrics.get("precision") is not None:
            print(f"  Precision:   {metrics['precision']:.2%}")
        if metrics.get("recall") is not None:
            print(f"  Recall:      {metrics['recall']:.2%}")
        if metrics.get("fpr") is not None:
            print(f"  FPR:         {metrics['fpr']:.2%}")
    else:
        print("\n  [WARN] No definitive predictions -- cannot compute metrics.")

    print(f"\n  Model:   {evaluation['results'][0].get('status', 'N/A') if evaluation['results'] else 'N/A'}")
    print(f"\n  Dataset size:  {metrics['total_samples']} samples")
    print(f"  [NOTE] With only {metrics['total_samples']} samples, these metrics have")
    print(f"     very high variance and should NOT be cited as accuracy claims.")
    print("=" * 72)


def main():
    parser = argparse.ArgumentParser(description="Evaluate AI Voice Detector")
    parser.add_argument(
        "--manifest", type=str, default=None,
        help="Path to JSONL manifest with labeled audio samples",
    )
    parser.add_argument(
        "--output", type=str, default=None,
        help="Path to write JSON evaluation results",
    )
    args = parser.parse_args()

    print("Loading AI Voice Detector...")
    detector = AIVoiceDetector()

    is_synthetic = False
    if args.manifest:
        manifest_path = Path(args.manifest)
        if not manifest_path.exists():
            print(f"[ERROR] Manifest not found: {manifest_path}")
            sys.exit(1)
        samples = load_manifest(manifest_path)
        if not samples:
            print("[ERROR] No valid samples in manifest")
            sys.exit(1)
    else:
        print("No manifest provided -- generating synthetic test audio...")
        tmp_dir = Path(tempfile.mkdtemp())
        samples = generate_test_audio(tmp_dir)
        is_synthetic = True

    print(f"\nRunning evaluation on {len(samples)} samples...\n")
    evaluation = evaluate(samples, detector)
    print_report(evaluation, is_synthetic_data=is_synthetic)

    if args.output:
        output_path = Path(args.output)
        output_path.write_text(json.dumps(evaluation, indent=2, default=str))
        print(f"\nResults written to: {output_path}")


if __name__ == "__main__":
    main()
