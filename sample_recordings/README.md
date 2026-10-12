# Sample Recordings

This directory is for storing test audio files for VISHWAS development and demonstration.

## Purpose

Use this directory to store authorized sample call recordings for:
- Testing the upload functionality
- Demonstrating the analysis workflow
- Verifying end-to-end system operation
- Performance testing

## Important Notes

### ⚠️ Privacy and Legal Compliance

1. **Only use authorized recordings** - Do not upload recordings without proper consent
2. **Do not commit actual call recordings to version control** - The `.gitignore` excludes audio files from the repository
3. **Remove sensitive information** - Ensure test files contain no real personal information
4. **Comply with local recording laws** - Recording phone calls may require consent in your jurisdiction

### Supported Formats

Phase 1 supports the following audio formats:
- **WAV** (.wav) - Uncompressed audio
- **MP3** (.mp3) - Compressed audio
- **M4A** (.m4a) - Apple compressed audio

### File Requirements

- **Maximum size**: 50 MB (configurable in backend)
- **Sample rate**: Any (not validated in Phase 1)
- **Channels**: Mono or stereo

## Creating Test Files

### Option 1: Generate Synthetic Audio

You can create test files using Python:

```python
import wave
import numpy as np

# Generate 5 seconds of silence
sample_rate = 16000
duration = 5  # seconds
samples = np.zeros(sample_rate * duration, dtype=np.int16)

# Write WAV file
with wave.open('test_recording.wav', 'wb') as wav_file:
    wav_file.setnchannels(1)  # Mono
    wav_file.setsampwidth(2)  # 16-bit
    wav_file.setframerate(sample_rate)
    wav_file.writeframes(samples.tobytes())
```

### Option 2: Use Text-to-Speech

Generate test audio using online TTS services:
1. Use a service like Google Cloud Text-to-Speech
2. Generate a short conversation
3. Save as WAV or MP3
4. Place in this directory

### Option 3: Record Test Conversations

Record yourself reading test scripts:
- Use a simple voice recorder app
- Read fraud scenario scripts (mock conversations)
- Export as supported format
- Place in this directory

## Example Test Scripts

### Suspicious Call Script

```
Caller: "Hello, this is calling from bank security department."
Caller: "We have detected suspicious activity on your account."
Caller: "Please share your OTP immediately to verify your identity."
Caller: "This is urgent. Your account will be blocked in 10 minutes."
```

### Legitimate Call Script

```
Caller: "Hello, this is Sarah from customer service."
Caller: "I'm calling to follow up on your recent inquiry about account balance."
Caller: "Would you like me to send the information to your registered email?"
```

## Using Sample Files

### In Web Dashboard

1. Start the backend and dashboard
2. Navigate to "Upload Recording"
3. Select a file from this directory
4. Upload and analyze

### In Android App

1. Copy test files to your device:
   ```bash
   adb push test_recording.wav /sdcard/Download/
   ```
2. Open VISHWAS app
3. Tap "Upload Recording"
4. Select the file from Downloads
5. Upload and analyze

### Via API (curl)

```bash
curl -X POST "http://localhost:8000/api/v1/calls" \
  -H "accept: application/json" \
  -H "Content-Type: multipart/form-data" \
  -F "file=@test_recording.wav"
```

## Git Ignore Settings

The following patterns are ignored by git (in `.gitignore`):
```
sample_recordings/*.mp3
sample_recordings/*.wav
sample_recordings/*.m4a
```

This README file is tracked, but actual audio files are not committed to the repository.

## Phase 1 Behavior

Remember that Phase 1 uses **mock analysis**:
- The uploaded audio file is stored and validated
- The actual audio content is NOT analyzed
- Mock transcript and findings are generated based on a predetermined scenario
- All reports clearly indicate `"is_mock": true`

Future phases will implement real audio transcription and fraud detection.

## Recommended Test Cases

Create or collect audio files to test:

1. **Valid upload** - Standard WAV/MP3/M4A file
2. **Large file** - File close to 50MB limit
3. **Empty file** - 0-byte file (should be rejected)
4. **Wrong format** - TXT or other non-audio file (should be rejected)
5. **Corrupted file** - Intentionally malformed audio header
6. **Various durations** - 5 seconds, 30 seconds, 5 minutes, etc.
7. **Various quality levels** - Different bitrates and sample rates

## Cleanup

To remove all test recordings:

```bash
rm sample_recordings/*.wav
rm sample_recordings/*.mp3
rm sample_recordings/*.m4a
```

Backend storage can be cleaned separately:

```bash
rm -rf backend/storage/uploads/*
```

## Future Enhancements

In future phases, this directory may include:
- Multi-language audio samples
- Various accent examples
- Background noise scenarios
- Different call quality levels
- Specific fraud pattern examples
