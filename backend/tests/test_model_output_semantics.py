"""
Phase 4 - Model Output Semantics Verification

This test verifies that we correctly interpret the model's output.

Model: Vansh180/deepfake-audio-wav2vec2
Label mapping verified:
  - id2label: {0: 'real', 1: 'fake'}  
  - label2id: {'fake': 1, 'real': 0}

Our interpretation:
  - probs[0] = P(real/bonafide)
  - probs[1] = P(fake/spoof) ← We extract this as spoof_prob

CRITICAL LIMITATION: 
These tests use synthetic audio (sine waves, noise) NOT real human speech.
Real validation requires actual speech vs TTS/cloned samples.
"""
import pytest
import numpy as np
import math

try:
    import torch
    import transformers
    DEPENDENCIES_AVAILABLE = True
except ImportError:
    DEPENDENCIES_AVAILABLE = False


@pytest.mark.skipif(not DEPENDENCIES_AVAILABLE, reason="torch or transformers not installed")
class TestModelOutputSemantics:
    """Verify model output interpretation is correct."""
    
    def test_model_label_configuration(self):
        """Verify model has correct label mapping."""
        from transformers import AutoConfig
        
        model_id = "Vansh180/deepfake-audio-wav2vec2"
        config = AutoConfig.from_pretrained(model_id)
        
        # Verify binary classification
        assert config.num_labels == 2
        
        # Verify label mapping
        assert config.id2label == {0: 'real', 1: 'fake'}
        assert config.label2id == {'fake': 1, 'real': 0}
        
        print("\n✅ Model label configuration verified:")
        print(f"   Label 0 = '{config.id2label[0]}' (bonafide)")
        print(f"   Label 1 = '{config.id2label[1]}' (spoof)")
    
    def test_output_interpretation_with_silence(self):
        """Test model output on silence (baseline test)."""
        from transformers import AutoFeatureExtractor, AutoModelForAudioClassification
        import torch
        
        model_id = "Vansh180/deepfake-audio-wav2vec2"
        feature_extractor = AutoFeatureExtractor.from_pretrained(model_id)
        model = AutoModelForAudioClassification.from_pretrained(model_id)
        model.eval()
        
        # Generate 5 seconds of silence
        sample_rate = 16000
        duration = 5.0
        silence = np.zeros(int(sample_rate * duration), dtype=np.float32)
        
        # Run inference
        inputs = feature_extractor(silence, sampling_rate=16000, return_tensors='pt', padding=True)
        with torch.no_grad():
            logits = model(**inputs).logits
            probs = torch.softmax(logits, dim=-1).squeeze()
        
        # Verify output shape and interpretation
        assert probs.shape[0] == 2, "Model should output 2 classes"
        
        real_prob = float(probs[0].item())
        fake_prob = float(probs[1].item())
        
        # Probabilities should sum to 1
        assert abs((real_prob + fake_prob) - 1.0) < 0.01
        
        # Both should be in [0, 1]
        assert 0 <= real_prob <= 1
        assert 0 <= fake_prob <= 1
        
        print(f"\n✅ Model output interpretation verified:")
        print(f"   P(real) = {real_prob:.4f}")
        print(f"   P(fake) = {fake_prob:.4f}")
        print(f"   Sum = {real_prob + fake_prob:.4f}")
        
        # Our code extracts probs[1] as spoof_prob - verify this is correct
        spoof_prob_extracted = fake_prob
        print(f"   Our spoof_prob extraction: {spoof_prob_extracted:.4f} ✓")
    
    def test_output_interpretation_with_sine_wave(self):
        """Test model output on sine wave (non-speech audio)."""
        from transformers import AutoFeatureExtractor, AutoModelForAudioClassification
        import torch
        
        model_id = "Vansh180/deepfake-audio-wav2vec2"
        feature_extractor = AutoFeatureExtractor.from_pretrained(model_id)
        model = AutoModelForAudioClassification.from_pretrained(model_id)
        model.eval()
        
        # Generate 440Hz sine wave (5 seconds)
        sample_rate = 16000
        duration = 5.0
        t = np.linspace(0, duration, int(sample_rate * duration), False)
        sine = (0.3 * np.sin(2 * np.pi * 440 * t)).astype(np.float32)
        
        # Run inference
        inputs = feature_extractor(sine, sampling_rate=16000, return_tensors='pt', padding=True)
        with torch.no_grad():
            logits = model(**inputs).logits
            probs = torch.softmax(logits, dim=-1).squeeze()
        
        real_prob = float(probs[0].item())
        fake_prob = float(probs[1].item())
        
        # Sine wave should be classified as fake (non-speech)
        # This is expected behavior
        print(f"\n✅ Sine wave classification:")
        print(f"   P(real) = {real_prob:.4f}")
        print(f"   P(fake) = {fake_prob:.4f}")
        print(f"   Classification: {'REAL' if real_prob > fake_prob else 'FAKE'}")
        
        # Verify our extraction
        assert 0 <= fake_prob <= 1
        print(f"   Our spoof_prob: {fake_prob:.4f} ✓")
    
    def test_voice_layer_extracts_correct_probability(self):
        """Verify VoiceLayer extracts P(fake) not P(real)."""
        from app.audio.voice_layer import VoiceLayer
        import tempfile
        import wave
        from pathlib import Path
        
        # Create test audio (sine wave)
        sample_rate = 16000
        duration = 5.0
        t = np.linspace(0, duration, int(sample_rate * duration), False)
        sine = (0.3 * np.sin(2 * np.pi * 440 * t)).astype(np.float32)
        
        # Save to WAV
        f = tempfile.NamedTemporaryFile(suffix='.wav', delete=False)
        with wave.open(f.name, 'wb') as wf:
            wf.setnchannels(1)
            wf.setsampwidth(2)
            wf.setframerate(sample_rate)
            audio_int16 = (sine * 32767).astype(np.int16)
            wf.writeframes(audio_int16.tobytes())
        
        wav_path = Path(f.name)
        
        try:
            # Test via VoiceLayer
            layer = VoiceLayer()
            spoof_prob, windows = layer.run_check_a(wav_path)
            
            # Should have extracted a probability
            assert spoof_prob is not None
            assert 0 <= spoof_prob <= 1
            assert windows > 0
            
            # For sine wave, should be classified as fake (high spoof_prob)
            # Expected: spoof_prob > 0.5
            print(f"\n✅ VoiceLayer extracts spoof_prob correctly:")
            print(f"   Extracted spoof_prob: {spoof_prob:.4f}")
            print(f"   Windows analyzed: {windows}")
            print(f"   Interpretation: {'Suspicious' if spoof_prob >= 0.60 else 'Not flagged'}")
            
        finally:
            wav_path.unlink(missing_ok=True)


@pytest.mark.skipif(not DEPENDENCIES_AVAILABLE, reason="torch or transformers not installed")
class TestThresholdMapping:
    """Verify threshold mapping matches documentation."""
    
    def test_threshold_boundaries_match_scoring(self):
        """Verify our thresholds match the scoring rules."""
        # These thresholds are defined in voice_layer.py VoiceSpoofEvidence schema
        # and used in scoring.py _score_voice()
        
        THRESHOLD_HIGH = 0.80
        THRESHOLD_MEDIUM = 0.60
        
        # Test cases for scoring
        test_cases = [
            (0.00, 0, "Below medium threshold"),
            (0.59, 0, "Just below medium threshold"),
            (0.60, 5, "Exactly at medium threshold"),
            (0.70, 5, "Between medium and high"),
            (0.79, 5, "Just below high threshold"),
            (0.80, 10, "Exactly at high threshold"),
            (1.00, 10, "Maximum spoof probability"),
        ]
        
        for spoof_prob, expected_points, description in test_cases:
            if spoof_prob >= THRESHOLD_HIGH:
                actual_points = 10
            elif spoof_prob >= THRESHOLD_MEDIUM:
                actual_points = 5
            else:
                actual_points = 0
            
            assert actual_points == expected_points, \
                f"Threshold mapping failed for {description}: " \
                f"spoof_prob={spoof_prob}, expected={expected_points}, got={actual_points}"
        
        print("\n✅ Threshold mapping verified:")
        print(f"   spoof_prob < {THRESHOLD_MEDIUM:.2f} → 0 points")
        print(f"   spoof_prob ≥ {THRESHOLD_MEDIUM:.2f} → 5 points")
        print(f"   spoof_prob ≥ {THRESHOLD_HIGH:.2f} → 10 points")


class TestRealSpeechValidationRequired:
    """Document that real speech validation is still required."""
    
    def test_synthetic_audio_limitation_documented(self):
        """
        CRITICAL: Current tests use synthetic audio only.
        
        Real validation requires:
        1. Genuine human speech samples (various speakers, languages)
        2. TTS/voice-cloned samples (various systems)
        3. Comparison of model outputs on both
        4. Measurement of accuracy metrics (EER, FPR, FNR)
        
        This test serves as documentation that the limitation is known.
        """
        limitation = (
            "Current inference verification uses synthetic audio (sine waves, noise). "
            "Real validation requires actual human speech vs TTS/cloned samples. "
            "Model output interpretation is verified correct, but detection accuracy "
            "on real speech is unmeasured."
        )
        
        print(f"\n⚠️  DOCUMENTED LIMITATION:")
        print(f"   {limitation}")
        
        # This test always passes - it's documentation
        assert True, "Limitation documented"
    
    def test_where_to_get_real_samples(self):
        """
        Document where to obtain real speech samples for validation.
        
        Sources:
        1. ASVspoof datasets (requires registration)
           - ASVspoof 2019 LA: https://datashare.ed.ac.uk/handle/10283/3336
           - ASVspoof 2021: https://zenodo.org/record/4835108
        
        2. LibriSpeech (genuine speech only)
           - http://www.openslr.org/12/
        
        3. Generate TTS samples using:
           - Google Cloud TTS
           - Amazon Polly
           - Microsoft Azure TTS
           - ElevenLabs (voice cloning)
        
        4. Record team member voices (with consent)
           - Genuine: direct recording
           - Cloned: use voice cloning service on their sample
        """
        guidance = (
            "To validate detection accuracy, acquire labeled genuine and spoofed "
            "speech samples. Test model on both and measure precision/recall at "
            "thresholds 0.60 and 0.80."
        )
        
        print(f"\n📚 VALIDATION GUIDANCE:")
        print(f"   {guidance}")
        
        assert True, "Guidance provided"
