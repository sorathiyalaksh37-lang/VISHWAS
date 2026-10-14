"""
Qwen2.5-3B-Instruct Parameter Extractor for VISHWAS.

Model: Qwen/Qwen2.5-3B-Instruct (revision: main)
Inference: Local, transformers pipeline, Apple MPS when available.

Design rules:
- Singleton pattern: model loaded ONCE per process, not per transcript.
- Constrained JSON output: strict schema prompt + Pydantic validation.
- Never executes generated code or tool calls.
- On any failure, raises LLMExtractionError → caller falls back to Tier1.
- Does NOT invent voice evidence. Voice fields come from VoiceParam only.
- Transcript PII should be masked before passing here.
"""
from __future__ import annotations

import json
import logging
import re
import threading
import time
from typing import Any, Dict, List, Optional

from app.core.config import settings

logger = logging.getLogger(__name__)

# ── Model config ───────────────────────────────────────────────────────────────
QWEN_MODEL_ID = "Qwen/Qwen2.5-3B-Instruct"
QWEN_REVISION = "main"
MAX_NEW_TOKENS = 1024
TEMPERATURE = 0.0          # greedy / deterministic
LOAD_IN_4BIT = True        # ~2 GB VRAM/RAM on MPS
TIMEOUT_S = 60.0

_pipeline = None
_pipeline_lock = threading.Lock()
_load_error: Optional[str] = None


class LLMExtractionError(RuntimeError):
    """Raised when LLM extraction fails; caller must fall back to Tier1."""
    pass


def _load_pipeline():
    """
    Lazy-load Qwen2.5-3B-Instruct once.
    Uses bitsandbytes 4-bit quantization when available (reduces RAM to ~2 GB).
    Falls back to fp32 CPU if MPS not available.
    """
    global _pipeline, _load_error

    with _pipeline_lock:
        if _pipeline is not None or _load_error is not None:
            return  # Already loaded or permanently failed

        try:
            import torch
            from transformers import AutoTokenizer, AutoModelForCausalLM, pipeline as hf_pipeline

            logger.info(f"Loading {QWEN_MODEL_ID} (revision={QWEN_REVISION})...")
            t0 = time.time()

            device = "mps" if torch.backends.mps.is_available() else "cpu"
            logger.info(f"Using device: {device}")

            # Try 4-bit quantization first (requires bitsandbytes)
            kwargs: Dict[str, Any] = {
                "pretrained_model_name_or_path": QWEN_MODEL_ID,
                "revision": QWEN_REVISION,
                "trust_remote_code": True,
            }

            quantized = False
            try:
                import bitsandbytes  # noqa: F401
                from transformers import BitsAndBytesConfig
                bnb_cfg = BitsAndBytesConfig(load_in_4bit=True)
                kwargs["quantization_config"] = bnb_cfg
                kwargs["device_map"] = "auto"
                quantized = True
                logger.info("Using 4-bit quantization via bitsandbytes")
            except ImportError:
                logger.info("bitsandbytes not available; loading in fp32")
                if device == "mps":
                    kwargs["torch_dtype"] = torch.float32
                    kwargs["device_map"] = {"": device}
                else:
                    kwargs["device_map"] = "cpu"

            tokenizer = AutoTokenizer.from_pretrained(
                QWEN_MODEL_ID, revision=QWEN_REVISION, trust_remote_code=True
            )
            model = AutoModelForCausalLM.from_pretrained(**kwargs)

            _pipeline = hf_pipeline(
                "text-generation",
                model=model,
                tokenizer=tokenizer,
                max_new_tokens=MAX_NEW_TOKENS,
                temperature=TEMPERATURE,
                do_sample=False,
                return_full_text=False,
            )

            elapsed = time.time() - t0
            logger.info(
                f"Qwen2.5-3B-Instruct loaded in {elapsed:.1f}s "
                f"(quantized={quantized}, device={device})"
            )

        except Exception as exc:
            _load_error = str(exc)
            logger.error(f"Failed to load Qwen model: {exc}", exc_info=True)


# ── Prompt ─────────────────────────────────────────────────────────────────────

SYSTEM_PROMPT = """You are a parameter extractor for a voice-fraud detection system.
Your ONLY job is to extract structured parameters from a phone call transcript.

Rules you MUST follow:
1. Output ONLY valid JSON matching the schema below. No prose, no markdown.
2. Never invent information not present in the transcript.
3. For each field, if not present set status to "not_detected".
4. "confidence" is your extraction confidence (0.0-1.0), NOT a fraud score.
5. Never claim the speaker IS genuinely the person they claim to be.
6. If a statement is negated (e.g. "don't send money"), mark status "not_detected".
7. Hypothetical statements ("if you don't pay...") are not real requests.
8. Never add voice analysis data; that comes from the audio layer.
9. Quote the transcript verbatim in excerpt fields (max 120 chars).
10. Assign speaker labels from the transcript (SPEAKER_00, SPEAKER_01, etc.) when available.

JSON Schema to return:
{
  "identity": {
    "claimed_name": null or string,
    "claimed_relationship": null or one of [relative, organization, authority, service_provider, friend, unknown],
    "verification_status": one of [verified, unverified, mismatch, not_attempted],
    "inconsistencies": [],
    "excerpt": null or string,
    "timestamp_s": null or number,
    "speaker": null or string,
    "confidence": number 0-1,
    "claim_changes": integer
  },
  "money_requests": [
    {
      "amount": null or number,
      "currency": "INR",
      "payment_method": null or string,
      "excerpt": null or string,
      "timestamp_s": null or number,
      "speaker": null or string,
      "confidence": number 0-1
    }
  ],
  "credential_requests": [
    {
      "credential_type": one of [otp, pin, password, cvv, card_number, account_number, aadhar, pan, kyc_details, other],
      "excerpt": null or string,
      "timestamp_s": null or number,
      "speaker": null or string,
      "confidence": number 0-1
    }
  ],
  "pressure_tactics": [
    {
      "tactic_type": one of [urgency, threat, secrecy, emotional, repeated_demand, resistance_to_verification],
      "severity": one of [low, medium, high],
      "excerpt": null or string,
      "timestamp_s": null or number,
      "speaker": null or string,
      "confidence": number 0-1
    }
  ],
  "consistency": [
    {
      "contradiction_type": one of [changed_story, changed_identity, bypass_verification, self_contradiction, other],
      "excerpt": null or string,
      "timestamp_s": null or number,
      "confidence": number 0-1
    }
  ]
}"""


def _build_user_prompt(transcript_text: str, call_id: str) -> str:
    # Truncate to avoid token overflow (approx 3000 chars ~ 750 tokens)
    if len(transcript_text) > 3000:
        transcript_text = transcript_text[:3000] + "\n[TRANSCRIPT TRUNCATED]"
    return f"Call ID: {call_id}\n\nTranscript:\n{transcript_text}\n\nExtract parameters:"


def _extract_json(raw: str) -> Dict[str, Any]:
    """Pull JSON from model output (strips fences / leading text)."""
    # Try direct parse
    try:
        return json.loads(raw.strip())
    except json.JSONDecodeError:
        pass

    # Try extracting first {...} block
    match = re.search(r"\{.*\}", raw, re.DOTALL)
    if match:
        try:
            return json.loads(match.group(0))
        except json.JSONDecodeError:
            pass

    raise LLMExtractionError(f"Could not parse JSON from model output: {raw[:200]!r}")


# ── Main extraction function ───────────────────────────────────────────────────

def extract_parameters_llm(
    transcript_text: str,
    call_id: str,
) -> Dict[str, Any]:
    """
    Run Qwen2.5-3B-Instruct on the transcript and return raw dict.
    Caller (ParameterExtractor) converts dict → CallParameters.

    Raises LLMExtractionError on any failure.
    Caller MUST fall back to Tier1 when this raises.
    """
    global _pipeline, _load_error

    if not transcript_text or not transcript_text.strip():
        raise LLMExtractionError("Empty transcript — skipping LLM extraction")

    # Load on first use
    if _pipeline is None and _load_error is None:
        _load_pipeline()

    if _load_error:
        raise LLMExtractionError(f"Model load failed permanently: {_load_error}")

    if _pipeline is None:
        raise LLMExtractionError("Model pipeline not available")

    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": _build_user_prompt(transcript_text, call_id)},
    ]

    try:
        t0 = time.time()
        # Apply chat template so Qwen knows the turn structure
        tokenizer = _pipeline.tokenizer
        text_input = tokenizer.apply_chat_template(
            messages,
            tokenize=False,
            add_generation_prompt=True,
        )

        outputs = _pipeline(
            text_input,
            max_new_tokens=MAX_NEW_TOKENS,
            do_sample=False,
        )
        raw = outputs[0]["generated_text"] if outputs else ""
        latency_ms = (time.time() - t0) * 1000
        logger.info(
            f"[{call_id}] LLM extraction: {latency_ms:.0f} ms, "
            f"output_len={len(raw)}"
        )

        result = _extract_json(raw)
        result["_latency_ms"] = latency_ms
        return result

    except LLMExtractionError:
        raise
    except Exception as exc:
        raise LLMExtractionError(f"LLM inference error: {exc}") from exc


def is_model_loaded() -> bool:
    return _pipeline is not None


def get_model_status() -> Dict[str, Any]:
    return {
        "model_id": QWEN_MODEL_ID,
        "revision": QWEN_REVISION,
        "loaded": is_model_loaded(),
        "load_error": _load_error,
    }
