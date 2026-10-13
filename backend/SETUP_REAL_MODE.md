# Setting Up Real Transcription Mode

This guide walks you through enabling **real audio transcription** in VISHWAS backend (Member 2 responsibilities).

## Prerequisites

- Python 3.9 or higher
- Git
- ~2GB disk space for models
- Internet connection for first-time model downloads

## Step 1: Install System Dependencies

### ffmpeg (Required for Audio Conversion)

**Windows (using Chocolatey):**
```powershell
choco install ffmpeg
```

**Windows (manual):**
1. Download from https://ffmpeg.org/download.html
2. Extract to `C:\ffmpeg`
3. Add `C:\ffmpeg\bin` to PATH
4. Verify: `ffmpeg -version`

**Linux (Ubuntu/Debian):**
```bash
sudo apt update
sudo apt install ffmpeg
```

**macOS:**
```bash
brew install ffmpeg
```

## Step 2: Install Python Dependencies

### Option A: Full Installation (Recommended)

Install all dependencies including voice layer:

```bash
cd backend
pip install -r requirements.txt
```

This includes:
- `faster-whisper` for ASR (transcription)
- `torch`, `transformers`, `torchaudio` for voice models
- `speechbrain` for voiceprint matching

**Note:** This will download ~2GB of packages and may take 10-15 minutes.

### Option B: Minimal Installation (ASR Only)

If you only want transcription without voice analysis:

```bash
pip install fastapi uvicorn sqlalchemy pydantic numpy faster-whisper
```

Then set `ENABLE_VOICE_LAYER=false` in `.env`

## Step 3: Configure Environment

Create `.env` file in `backend/` directory:

```env
# Switch from mock to real mode
ANALYSIS_MODE=real

# ASR Configuration
WHISPER_MODEL_SIZE=base          # Options: base, small, medium
WHISPER_DEVICE=cpu               # Use 'cuda' if you have GPU
WHISPER_COMPUTE_TYPE=int8        # int8 for CPU, float16 for GPU

# Voice Layer (set to false if not installed)
ENABLE_VOICE_LAYER=true

# Other settings
DEBUG=true
LOG_LEVEL=INFO
```

### Model Size Guide

| Model | Size | Speed | Accuracy | Use Case |
|-------|------|-------|----------|----------|
| base  | 140MB | Fast | Good | Development, demos |
| small | 460MB | Medium | Better | Production (English/Hindi) |
| medium| 1.5GB | Slow | Best | High accuracy needs |

## Step 4: Verify Installation

### Check Dependencies

```bash
cd backend
python -c "import faster_whisper; print('✓ faster-whisper installed')"
python -c "import torch; print('✓ torch installed')"
python -c "import speechbrain; print('✓ speechbrain installed')"
```

### Start Server

```bash
cd backend
python -m uvicorn app.main:app --reload
```

Look for these startup messages:
```
INFO:     Starting VISHWAS backend...
INFO:     Analysis mode: real
INFO:     ✓ ffmpeg available for audio conversion
INFO:     ✓ faster-whisper installed for ASR
INFO:     ✓ torch available for voice layer
INFO:     ✓ speechbrain available for voiceprint matching
```

**Warning Messages:**
- If you see `⚠️ CRITICAL: ffmpeg not found` → Install ffmpeg (Step 1)
- If you see `⚠️ faster-whisper not installed` → Run `pip install faster-whisper`
- Voice layer warnings are OK if `ENABLE_VOICE_LAYER=false`

## Step 5: Test Real Transcription

### Using cURL

```bash
# Upload a test audio file (replace with your file path)
curl -X POST http://localhost:8000/api/v1/analyze/recording \
  -F "file=@test_sample.wav" \
  -o response.json

# Extract call_id
$CALL_ID = (Get-Content response.json | ConvertFrom-Json).call_id

# Poll status
curl http://localhost:8000/api/v1/call/$CALL_ID/status

# Get full results (once status = "completed")
curl http://localhost:8000/api/v1/call/$CALL_ID/state
```

### Using Python

```python
import requests
import time

# Upload
with open("test_sample.wav", "rb") as f:
    response = requests.post(
        "http://localhost:8000/api/v1/analyze/recording",
        files={"file": f}
    )
call_id = response.json()["call_id"]
print(f"Uploaded: {call_id}")

# Wait for completion
while True:
    status = requests.get(
        f"http://localhost:8000/api/v1/call/{call_id}/status"
    ).json()
    print(f"Status: {status['status']}")
    if status["status"] in ["completed", "failed"]:
        break
    time.sleep(2)

# Get results
if status["status"] == "completed":
    report = requests.get(
        f"http://localhost:8000/api/v1/call/{call_id}/state"
    ).json()
    
    # Check transcript
    if report["transcript"]:
        print(f"Language: {report['transcript']['language']}")
        print(f"Segments: {len(report['transcript']['segments'])}")
        for seg in report["transcript"]["segments"][:3]:
            print(f"  [{seg['start']:.2f}s] {seg['text']}")
    
    # Check voice evidence
    if "voice" in report and report["voice"]:
        print(f"Voice status: {report['voice']['status']}")
        if report["voice"]["spoof_prob"]:
            print(f"Spoof probability: {report['voice']['spoof_prob']:.2f}")
```

### Expected Output

✅ **Success indicators:**
- `transcription_status: "completed"`
- Language detected (e.g., `"language": "en"`)
- Multiple segments with timestamps
- `is_mock: false`

❌ **Failure indicators:**
- `transcription_status: "unavailable"` → Model not installed
- `transcription_status: "failed"` → Check logs for error
- `status: "failed"` → Audio conversion or validation failed

## Step 6: Model Downloads (First Run)

On first transcription, models download automatically:

```
Downloading faster-whisper base model... (140 MB)
Downloading SpeechBrain ECAPA-TDNN... (80 MB)
Downloading wav2vec2 model... (360 MB) [if voice layer enabled]
```

This happens **once**. Models cache to:
- Windows: `%USERPROFILE%\.cache\huggingface`
- Linux/Mac: `~/.cache/huggingface`

**Tip:** Download in advance using Python:
```python
from faster_whisper import WhisperModel
model = WhisperModel("base", device="cpu", compute_type="int8")
print("Model downloaded!")
```

## Common Issues

### Issue: "ffmpeg not found"
**Solution:** Add ffmpeg to PATH and restart terminal

### Issue: "torch not compatible with your CUDA version"
**Solution:** Uninstall torch and reinstall CPU version:
```bash
pip uninstall torch torchaudio
pip install torch torchaudio --index-url https://download.pytorch.org/whl/cpu
```

### Issue: "Transcription failed: Out of memory"
**Solutions:**
1. Use smaller model: `WHISPER_MODEL_SIZE=base`
2. Process shorter files (<5 minutes)
3. Close other applications

### Issue: "Voice layer unavailable"
**Solution:** This is OK if `ENABLE_VOICE_LAYER=false`. To enable:
```bash
pip install torch transformers torchaudio speechbrain
```

### Issue: Test returns "mock" transcript
**Solution:** Check `.env` has `ANALYSIS_MODE=real` and restart server

## Performance Tuning

### CPU Optimization
```env
WHISPER_MODEL_SIZE=base
WHISPER_COMPUTE_TYPE=int8
WHISPER_DEVICE=cpu
```
- ~2-3x real-time processing
- Example: 1 minute audio → 30-40s processing

### GPU Optimization (CUDA)
```env
WHISPER_MODEL_SIZE=small
WHISPER_COMPUTE_TYPE=float16
WHISPER_DEVICE=cuda
```
- ~0.5x real-time processing
- Example: 1 minute audio → 30s processing

### Disable Voice Layer for Speed
```env
ENABLE_VOICE_LAYER=false
```
- Saves ~5-10s per call
- Only affects spoof detection, not transcription

## Security & Privacy

### PII Masking
All transcripts are **automatically PII-masked** before being sent to Tier 2 LLM agents:
- Phone numbers → `[MASKED_PHONE]`
- Emails → `[MASKED_EMAIL]`
- Credit card numbers → `[MASKED_CARD]`
- Account numbers → `[MASKED_ACCOUNT]`

Raw transcripts are stored in database but never sent to external APIs.

### Voiceprint Privacy
- Only embeddings stored (768 bytes per contact)
- Raw audio clips deleted immediately after enrollment
- Embeddings cannot be reverse-engineered to audio

## Next Steps

1. ✅ **Test with Real Audio:** Upload 5-10 diverse samples (Hindi, English, Hinglish)
2. ⚠️ **Replace Spoof Model:** Current model is placeholder (see voice_layer.py comments)
3. ✅ **Run Tests:** `pytest tests/test_m2_perception.py -v`
4. 📊 **Monitor Performance:** Check processing times in logs
5. 🔒 **Verify PII Masking:** Check agent prompts contain `[MASKED_X]` tokens

## Support

If you encounter issues:
1. Check logs: `backend/logs/vishwas.log`
2. Enable debug mode: `DEBUG=true` in `.env`
3. Run health check: `curl http://localhost:8000/api/v1/health`
4. Check this audit report: `backend/AUDIT_REPORT.md`
