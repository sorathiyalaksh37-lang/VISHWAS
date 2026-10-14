"""
Telephony codec handling for VISHWAS Phase 5A.

Supports G.711 μ-law audio as used by Twilio, Exotel, Plivo and similar
VoIP/telephony providers.  Decodes transport payloads arriving from
authorized gateway WebSocket connections and produces 16-bit PCM mono
suitable for the existing IncrementalASR / faster-whisper pipeline.

Design notes
------------
* μ-law bytes are NOT treated as PCM.  The full ITU-T G.711 lookup-table
  decoder is applied before any downstream processing.
* Resampling (8 kHz → 16 kHz) is performed only when required by the ASR
  model.  It cannot restore lost bandwidth; it merely avoids sample-rate
  mismatch errors.
* No WAV headers are added; the downstream IncrementalASR accepts raw
  16-bit PCM bytes directly.
* All decoding is synchronous and CPU-bound; callers must offload to a
  thread pool if called from an async context.
* Memory usage is bounded: per-session AudioBuffer enforces a configurable
  maximum and discards oldest bytes when full.
"""
from __future__ import annotations

import array
import base64
import logging
import struct
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)

# ── G.711 μ-law lookup table (ITU-T G.711 §2.4) ──────────────────────────────
# Maps each unsigned 8-bit μ-law byte to a signed 16-bit linear PCM sample.
# Generated once at module import; immutable thereafter.

def _build_ulaw_table() -> array.array:
    """Build the 256-entry μ-law decoding lookup table."""
    table = array.array("h", [0] * 256)
    for byte in range(256):
        val = ~byte & 0xFF
        sign = (val & 0x80) >> 7
        exponent = (val & 0x70) >> 4
        mantissa = val & 0x0F
        linear = ((mantissa | 0x10) << (exponent + 3)) - 132
        table[byte] = -linear if sign else linear
    return table


_ULAW_TABLE: array.array = _build_ulaw_table()

# ── Constants ─────────────────────────────────────────────────────────────────

TELEPHONY_SAMPLE_RATE = 8_000    # G.711 native
ASR_SAMPLE_RATE = 16_000         # faster-whisper expectation
BYTES_PER_PCM_SAMPLE = 2         # 16-bit signed little-endian
MAX_PAYLOAD_BYTES = 4096         # ~0.5 s of G.711 μ-law; reject larger chunks
MAX_BUFFER_BYTES = 640_000       # ~20 s of 16-kHz PCM per session


# ── Exceptions ────────────────────────────────────────────────────────────────

class TelephonyCodecError(ValueError):
    """Raised for malformed or rejected telephony payloads."""


# ── Codec functions ───────────────────────────────────────────────────────────

def decode_base64_payload(b64_payload: str) -> bytes:
    """
    Decode a base64-encoded telephony audio payload.

    Raises:
        TelephonyCodecError: If the string is not valid base64.
    """
    if not isinstance(b64_payload, str) or not b64_payload.strip():
        raise TelephonyCodecError("Payload must be a non-empty base64 string")
    try:
        raw = base64.b64decode(b64_payload, validate=True)
    except Exception as exc:
        raise TelephonyCodecError(f"Base64 decode failed: {exc}") from exc
    return raw


def validate_payload_size(raw: bytes) -> None:
    """
    Reject oversized or empty payloads before decoding.

    Raises:
        TelephonyCodecError: If size is 0 or exceeds MAX_PAYLOAD_BYTES.
    """
    if len(raw) == 0:
        raise TelephonyCodecError("Empty payload rejected")
    if len(raw) > MAX_PAYLOAD_BYTES:
        raise TelephonyCodecError(
            f"Payload too large: {len(raw)} bytes > {MAX_PAYLOAD_BYTES} limit"
        )


def ulaw_to_pcm16(ulaw_bytes: bytes) -> bytes:
    """
    Decode G.711 μ-law bytes to 16-bit signed PCM (little-endian).

    Each input byte maps to one 16-bit output sample using the ITU-T G.711
    lookup table.  The output length is exactly 2× the input length.

    Args:
        ulaw_bytes: Raw μ-law encoded bytes from telephony provider.

    Returns:
        bytes: 16-bit signed PCM, little-endian, mono.
    """
    if not ulaw_bytes:
        return b""
    samples = array.array("h", (_ULAW_TABLE[b] for b in ulaw_bytes))
    return samples.tobytes()


def resample_8k_to_16k(pcm_8k: bytes) -> bytes:
    """
    Upsample 8 kHz mono 16-bit PCM to 16 kHz by linear interpolation.

    This is a simple 2× upsample.  It does NOT restore lost bandwidth;
    it merely satisfies the ASR model's sample-rate expectation.

    Args:
        pcm_8k: 16-bit PCM at 8 000 Hz, little-endian, mono.

    Returns:
        bytes: 16-bit PCM at 16 000 Hz, little-endian, mono.
    """
    if not pcm_8k:
        return b""

    n_samples = len(pcm_8k) // 2
    if n_samples == 0:
        return b""

    samples_8k = struct.unpack(f"<{n_samples}h", pcm_8k[: n_samples * 2])
    out = array.array("h")

    for i in range(n_samples - 1):
        s0 = samples_8k[i]
        s1 = samples_8k[i + 1]
        out.append(s0)
        out.append((s0 + s1) // 2)   # interpolated midpoint

    # Last sample: repeat
    out.append(samples_8k[-1])
    out.append(samples_8k[-1])

    return out.tobytes()


def decode_telephony_chunk(
    b64_payload: str,
    codec: str = "mulaw",
    input_sample_rate: int = TELEPHONY_SAMPLE_RATE,
    output_sample_rate: int = ASR_SAMPLE_RATE,
) -> bytes:
    """
    Full decode pipeline for one telephony audio transport chunk.

    Steps:
      1. Validate and base64-decode the payload.
      2. Validate payload size.
      3. Decode codec (currently only 'mulaw' / 'ulaw').
      4. Resample to output_sample_rate if input_sample_rate differs.

    Args:
        b64_payload: Base64-encoded audio from gateway WebSocket.
        codec:       Audio codec.  Currently supports 'mulaw'/'ulaw' only.
        input_sample_rate:  Native sample rate from provider (default 8000).
        output_sample_rate: Target sample rate for ASR (default 16000).

    Returns:
        bytes: 16-bit PCM mono at output_sample_rate.

    Raises:
        TelephonyCodecError: On any malformed/invalid input.
    """
    if codec not in ("mulaw", "ulaw"):
        raise TelephonyCodecError(
            f"Unsupported codec '{codec}'. Only 'mulaw'/'ulaw' is supported."
        )

    raw = decode_base64_payload(b64_payload)
    validate_payload_size(raw)

    pcm_native = ulaw_to_pcm16(raw)

    if input_sample_rate == output_sample_rate:
        return pcm_native

    if input_sample_rate == 8_000 and output_sample_rate == 16_000:
        return resample_8k_to_16k(pcm_native)

    raise TelephonyCodecError(
        f"Unsupported sample-rate conversion: {input_sample_rate} Hz → "
        f"{output_sample_rate} Hz.  Only 8 kHz → 16 kHz is currently supported."
    )


# ── Per-session audio buffer ──────────────────────────────────────────────────

@dataclass
class AudioBuffer:
    """
    Bounded per-session buffer for decoded PCM audio.

    Enforces MAX_BUFFER_BYTES to prevent unbounded memory growth.
    When full, oldest bytes are discarded and a warning is emitted.
    Call clear() on session teardown to release memory explicitly.
    """
    session_id: str
    max_bytes: int = MAX_BUFFER_BYTES
    _data: bytearray = field(default_factory=bytearray, repr=False)
    _total_received: int = field(default=0, repr=False)
    _total_dropped: int = field(default=0, repr=False)

    def append(self, pcm_bytes: bytes) -> None:
        """Append decoded PCM bytes, discarding oldest if buffer is full."""
        if not pcm_bytes:
            return
        self._total_received += len(pcm_bytes)
        available = self.max_bytes - len(self._data)
        if len(pcm_bytes) > available:
            excess = len(pcm_bytes) - available
            del self._data[:excess]
            self._total_dropped += excess
            logger.warning(
                "[AudioBuffer %s] Buffer full: dropped %d bytes (total dropped: %d)",
                self.session_id,
                excess,
                self._total_dropped,
            )
        self._data.extend(pcm_bytes)

    def read_bytes(self, n: int) -> bytes:
        """Read up to n bytes from the front without consuming them."""
        return bytes(self._data[:n])

    def consume(self, n: int) -> bytes:
        """Remove and return up to n bytes from the front."""
        chunk = bytes(self._data[:n])
        del self._data[:n]
        return chunk

    def __len__(self) -> int:
        return len(self._data)

    @property
    def duration_seconds(self) -> float:
        """Approximate buffered duration at 16 kHz 16-bit mono."""
        return len(self._data) / (ASR_SAMPLE_RATE * BYTES_PER_PCM_SAMPLE)

    def clear(self) -> None:
        """Release all buffered audio (call on session cleanup)."""
        self._data.clear()
        logger.debug("[AudioBuffer %s] Cleared on session teardown", self.session_id)

    @property
    def stats(self) -> dict:
        return {
            "session_id": self.session_id,
            "buffered_bytes": len(self._data),
            "total_received_bytes": self._total_received,
            "total_dropped_bytes": self._total_dropped,
            "duration_s": round(self.duration_seconds, 3),
        }
