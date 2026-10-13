"""
Audio preprocessing module.
Converts any supported audio (WAV, MP3, M4A) to 16 kHz mono WAV
suitable for faster-whisper and voice analysis models.

Pipeline Plan (§3):
  ffmpeg → 16 kHz mono WAV → validation → 2s chunks (live mode)
  Fallback: PyAV (av) for conversion if ffmpeg binary is absent.
"""
import io
import logging
import os
import subprocess
import tempfile
from pathlib import Path
from typing import Optional, Tuple

logger = logging.getLogger(__name__)

# Supported input formats
SUPPORTED_FORMATS = {".wav", ".mp3", ".m4a", ".ogg", ".flac", ".webm"}

# Target audio parameters (faster-whisper requirement)
TARGET_SAMPLE_RATE = 16000
TARGET_CHANNELS = 1          # mono

# ── Check for PyAV (installed with faster-whisper) ────────────────────────────
try:
    import av as _av  # noqa: F401
    AV_AVAILABLE = True
except ImportError:
    AV_AVAILABLE = False


def _ffmpeg_available() -> bool:
    """Check whether ffmpeg is on PATH."""
    try:
        result = subprocess.run(
            ["ffmpeg", "-version"],
            capture_output=True,
            timeout=5
        )
        return result.returncode == 0
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return False


FFMPEG_AVAILABLE = _ffmpeg_available()
if not FFMPEG_AVAILABLE:
    if AV_AVAILABLE:
        logger.info(
            "ffmpeg binary not found on PATH — using PyAV library for audio conversion."
        )
    else:
        logger.warning(
            "ffmpeg not found on PATH and PyAV not installed. "
            "Audio conversion will be skipped. "
            "Install ffmpeg or pip install av for proper audio support."
        )


def _convert_with_av(input_path: Path, output_path: Path) -> Path:
    """
    Convert audio to 16 kHz mono WAV using PyAV (libav/ffmpeg bindings).
    This is the fallback when the ffmpeg CLI binary is not on PATH.
    """
    import av
    import numpy as np

    logger.info(f"Converting with PyAV: {input_path.name} → {output_path.name}")

    input_container = av.open(str(input_path))
    audio_stream = input_container.streams.audio[0]

    # Create output WAV
    output_container = av.open(str(output_path), mode='w')
    output_stream = output_container.add_stream('pcm_s16le', rate=TARGET_SAMPLE_RATE)
    output_stream.layout = 'mono'

    # Create a resampler to convert to 16 kHz mono
    resampler = av.AudioResampler(
        format='s16',
        layout='mono',
        rate=TARGET_SAMPLE_RATE,
    )

    for frame in input_container.decode(audio=0):
        # Resample
        resampled_frames = resampler.resample(frame)
        for resampled_frame in resampled_frames:
            for packet in output_stream.encode(resampled_frame):
                output_container.mux(packet)

    # Flush encoder
    for packet in output_stream.encode(None):
        output_container.mux(packet)

    output_container.close()
    input_container.close()

    if not output_path.exists() or output_path.stat().st_size == 0:
        raise ValueError("PyAV produced an empty output file.")

    logger.info(
        f"PyAV converted '{input_path.name}' → '{output_path.name}' "
        f"({output_path.stat().st_size} bytes)"
    )
    return output_path


def _get_duration_with_av(audio_path: Path) -> float:
    """Get audio duration using PyAV."""
    try:
        import av
        container = av.open(str(audio_path))
        duration = float(container.duration) / av.time_base if container.duration else 0.0
        # av.time_base is 1000000 (microseconds)
        if container.duration:
            duration = container.duration / 1_000_000.0
        container.close()
        return duration
    except Exception as e:
        logger.debug(f"Could not get duration via PyAV: {e}")
        return 0.0


def convert_to_wav(input_path: Path, output_path: Optional[Path] = None) -> Path:
    """
    Convert any supported audio file to 16 kHz mono WAV.

    Uses ffmpeg CLI if available, falls back to PyAV library.

    Args:
        input_path: Path to source audio file.
        output_path: Optional destination. If None, a temp file is created.

    Returns:
        Path to the converted WAV file.

    Raises:
        ValueError: If the file format is unsupported or conversion fails.
    """
    suffix = input_path.suffix.lower()
    if suffix not in SUPPORTED_FORMATS:
        raise ValueError(
            f"Unsupported audio format '{suffix}'. "
            f"Supported: {', '.join(SUPPORTED_FORMATS)}"
        )

    if output_path is None:
        tmp = tempfile.NamedTemporaryFile(suffix=".wav", delete=False)
        output_path = Path(tmp.name)
        tmp.close()

    # Strategy 1: Use ffmpeg CLI
    if FFMPEG_AVAILABLE:
        cmd = [
            "ffmpeg",
            "-y",                          # overwrite output
            "-i", str(input_path),         # input file
            "-ar", str(TARGET_SAMPLE_RATE),# 16 kHz
            "-ac", str(TARGET_CHANNELS),   # mono
            "-acodec", "pcm_s16le",        # 16-bit PCM
            str(output_path),
        ]

        logger.debug(f"Running ffmpeg: {' '.join(cmd)}")
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=120)

        if result.returncode != 0:
            logger.error(f"ffmpeg failed:\n{result.stderr}")
            raise ValueError(f"Audio conversion failed: {result.stderr[-500:]}")

        if not output_path.exists() or output_path.stat().st_size == 0:
            raise ValueError("ffmpeg produced an empty output file.")

        logger.info(
            f"Converted '{input_path.name}' → '{output_path.name}' "
            f"({output_path.stat().st_size} bytes)"
        )
        return output_path

    # Strategy 2: Use PyAV library (fallback)
    if AV_AVAILABLE:
        return _convert_with_av(input_path, output_path)

    # Strategy 3: If it's already a WAV, pass through
    if suffix == ".wav":
        logger.warning(
            f"No conversion tool available — returning original WAV: {input_path}"
        )
        return input_path

    raise ValueError(
        f"Cannot convert {suffix} file: neither ffmpeg nor PyAV is available. "
        f"Install one of: ffmpeg (CLI) or av (pip install av)"
    )


def get_audio_duration(wav_path: Path) -> float:
    """
    Return duration of an audio file in seconds.
    Tries ffprobe first, falls back to PyAV.
    """
    # Try ffprobe
    try:
        result = subprocess.run(
            [
                "ffprobe", "-v", "error",
                "-show_entries", "format=duration",
                "-of", "default=noprint_wrappers=1:nokey=1",
                str(wav_path),
            ],
            capture_output=True,
            text=True,
            timeout=10,
        )
        if result.returncode == 0 and result.stdout.strip():
            return float(result.stdout.strip())
    except Exception as e:
        logger.debug(f"Could not get duration via ffprobe: {e}")

    # Fallback: PyAV
    if AV_AVAILABLE:
        return _get_duration_with_av(wav_path)

    return 0.0


def estimate_snr(wav_path: Path) -> float:
    """
    Estimate signal-to-noise ratio of a WAV file (dB).
    Uses a simple energy-based approximation.
    Returns -1.0 if estimation fails.
    """
    try:
        import numpy as np
        import wave

        with wave.open(str(wav_path), "rb") as wf:
            frames = wf.readframes(wf.getnframes())
            dtype = np.int16 if wf.getsampwidth() == 2 else np.int32
            samples = np.frombuffer(frames, dtype=dtype).astype(np.float32)

        if samples.size == 0:
            return -1.0

        # Split into 50ms frames
        frame_size = int(TARGET_SAMPLE_RATE * 0.05)
        frames_arr = [
            samples[i: i + frame_size]
            for i in range(0, len(samples) - frame_size, frame_size)
        ]
        energies = [np.mean(f ** 2) for f in frames_arr if len(f) == frame_size]
        if not energies:
            return -1.0

        energies_arr = np.array(energies)
        signal_energy = np.percentile(energies_arr, 90)
        noise_energy = np.percentile(energies_arr, 10)

        if noise_energy <= 0:
            return 40.0  # assume very clean

        snr = 10 * np.log10(signal_energy / noise_energy)
        return float(snr)
    except Exception as e:
        logger.debug(f"SNR estimation failed: {e}")
        return -1.0


def validate_audio(wav_path: Path) -> Tuple[bool, str]:
    """
    Validate that the WAV file is suitable for analysis.

    Returns:
        (is_valid, reason) — reason is empty string if valid.
    """
    if not wav_path.exists():
        return False, "File does not exist"

    size = wav_path.stat().st_size
    if size == 0:
        return False, "Audio file is empty"

    if size < 1000:  # < 1 KB is too small for meaningful audio
        return False, f"Audio file too small ({size} bytes)"

    duration = get_audio_duration(wav_path)
    if 0 < duration < 0.5:
        return False, f"Audio too short ({duration:.2f}s)"

    if duration > 600:  # >10 min
        return False, f"Audio exceeds maximum duration ({duration:.0f}s > 600s)"

    return True, ""


def chunk_audio(wav_path: Path, chunk_seconds: float = 2.0) -> list[Path]:
    """
    Split audio into fixed-length chunks for live/streaming mode.
    Each chunk is written to a temp file.

    Args:
        wav_path: Input WAV file (should be 16 kHz mono).
        chunk_seconds: Duration of each chunk in seconds.

    Returns:
        List of paths to chunk files (caller must delete them).
    """
    if not FFMPEG_AVAILABLE:
        return [wav_path]

    tmp_dir = Path(tempfile.mkdtemp())
    pattern = str(tmp_dir / "chunk_%04d.wav")

    cmd = [
        "ffmpeg", "-y",
        "-i", str(wav_path),
        "-f", "segment",
        "-segment_time", str(chunk_seconds),
        "-ar", str(TARGET_SAMPLE_RATE),
        "-ac", str(TARGET_CHANNELS),
        "-acodec", "pcm_s16le",
        pattern,
    ]

    result = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
    if result.returncode != 0:
        logger.error(f"Chunking failed: {result.stderr}")
        return [wav_path]  # fall back to full file

    chunks = sorted(tmp_dir.glob("chunk_*.wav"))
    logger.info(f"Split '{wav_path.name}' into {len(chunks)} chunks of {chunk_seconds}s")
    return chunks
