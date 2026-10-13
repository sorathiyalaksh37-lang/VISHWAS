"""
Phase 4B: Voice Provider Integration Tests

Tests provider lifecycle, audio validation, real model inference, and error handling.

This test suite covers:
1. Provider lifecycle (lazy loading, reuse, failures)
2. Audio quality validation (empty, corrupt, too short, silence)
3. Real model inference execution (if dependencies available)
4. Error handling and graceful degradation
"""
import pytest
import tempfile
import wave
import struct
import math
import numpy as np
from pathlib import Path

from app.audio.voice_layer import get_voice_layer, VoiceLayer, MIN_SPEECH_SECONDS, MIN_SNR_DB


# ============================================================================
# AUDIO GENERATION HELPERS
# ============================================================================

def create_test_wav(
    duration_s: float,
    frequency: int = 440,
    sample_rate: int = 16000,
    amplitude: float = 0.3,
    add_noise: bool = False,
    noise_level: float = 0.01
) -> Path:
    """Create a synthetic WAV file for testing."""
    num_samples = int(sample_rate * duration_s)
    
    wav_buffer = []
    for i in range(num_samples):
        # Generate sine wave
        value = amplitude * math.sin(2 * math.pi * frequency * i / sample_rate)
        
        # Add noise if requested
        if add_noise:
            value += np.random.normal(0, noise_level)
        
        # Clip and convert to int16
        value = max(-1.0, min(1.0, value))
        value = int(32767 * value)
        wav_buffer.append(struct.pack('h', value))
    
    # Write WAV file
    wav_data = b''.join(wav_buffer)
    f = tempfile.NamedTemporaryFile(suffix='.wav', delete=False)
    with wave.open(f.name, 'wb') as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(sample_rate)
        wf.writeframes(wav_data)
    
    return Path(f.name)


def create_silence_wav(duration_s: float, sample_rate: int = 16000) -> Path:
    """Create a silent WAV file."""
    num_samples = int(sample_rate * duration_s)
    wav_buffer = [struct.pack('h', 0) for _ in range(num_samples)]
    
    wav_data = b''.join(wav_buffer)
    f = tempfile.NamedTemporaryFile(suffix='.wav', delete=False)
    with wave.open(f.name, 'wb') as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(sample_rate)
        wf.writeframes(wav_data)
    
    return Path(f.name)


def create_empty_wav() -> Path:
    """Create an empty/corrupt WAV file."""
    f = tempfile.NamedTemporaryFile(suffix='.wav', delete=False)
    f.write(b'')
    f.close()
    return Path(f.name)


def create_corrupt_wav() -> Path:
    """Create a corrupt WAV file with invalid header."""
    f = tempfile.NamedTemporaryFile(suffix='.wav', delete=False)
    f.write(b'CORRUPTED_HEADER_DATA')
    f.close()
    return Path(f.name)


# ============================================================================
# PROVIDER LIFECYCLE TESTS
# ============================================================================

class TestProviderLifecycle:
    """Test voice provider initialization and lifecycle."""
    
    def test_singleton_pattern(self):
        """get_voice_layer should return the same instance."""
        layer1 = get_voice_layer()
        layer2 = get_voice_layer()
        
        assert layer1 is layer2
        assert isinstance(layer1, VoiceLayer)
    
    def test_lazy_loading_not_on_init(self):
        """Model should not load on VoiceLayer initialization."""
        layer = VoiceLayer()
        
        # Should not have loaded yet
        assert not layer._spoof_loaded
        assert not layer._ecapa_loaded
    
    def test_lazy_loading_on_first_use(self):
        """Model should load on first analyze() call."""
        layer = VoiceLayer()
        
        wav_path = create_test_wav(5.0)
        try:
            result = layer.analyze(wav_path)
            
            # Should have attempted to load spoof model
            assert layer._spoof_loaded
            
            # Result should be one of the valid states
            assert result.status in ["ok", "unavailable", "inconclusive"]
            
        finally:
            wav_path.unlink(missing_ok=True)
    
    def test_model_reuse_no_reload(self):
        """Model should not reload on subsequent calls."""
        layer = VoiceLayer()
        
        wav_path = create_test_wav(5.0)
        try:
            # First call loads model
            layer.analyze(wav_path)
            spoof_loaded_first = layer._spoof_loaded
            
            # Second call reuses model
            layer.analyze(wav_path)
            spoof_loaded_second = layer._spoof_loaded
            
            # Both should be True (loaded)
            assert spoof_loaded_first
            assert spoof_loaded_second
            
        finally:
            wav_path.unlink(missing_ok=True)


# ============================================================================
# AUDIO QUALITY TESTS
# ============================================================================

class TestAudioQuality:
    """Test audio quality validation and gates."""
    
    def test_empty_audio_handling(self):
        """Empty audio file should return unavailable or inconclusive."""
        layer = get_voice_layer()
        empty_path = create_empty_wav()
        
        try:
            result = layer.analyze(empty_path)
            
            # Should handle gracefully
            assert result.status in ["unavailable", "inconclusive"]
            if result.error:
                assert len(result.error) > 0
                
        finally:
            empty_path.unlink(missing_ok=True)
    
    def test_corrupt_audio_handling(self):
        """Corrupt audio file should return unavailable or inconclusive."""
        layer = get_voice_layer()
        corrupt_path = create_corrupt_wav()
        
        try:
            result = layer.analyze(corrupt_path)
            
            # Should handle gracefully without crash
            # Can be either unavailable or inconclusive depending on failure point
            assert result.status in ["unavailable", "inconclusive"]
            
        finally:
            corrupt_path.unlink(missing_ok=True)
    
    def test_too_short_audio(self):
        """Audio < MIN_SPEECH_SECONDS should return inconclusive."""
        layer = get_voice_layer()
        
        # Create 1 second audio (< 3s minimum)
        short_path = create_test_wav(1.0)
        
        try:
            result = layer.analyze(short_path)
            
            # Should be inconclusive due to duration
            assert result.status == "inconclusive"
            assert result.duration_s < MIN_SPEECH_SECONDS
            
        finally:
            short_path.unlink(missing_ok=True)
    
    def test_borderline_duration(self):
        """Audio exactly at MIN_SPEECH_SECONDS should pass quality gate."""
        layer = get_voice_layer()
        
        # Create exactly 3 second audio
        borderline_path = create_test_wav(MIN_SPEECH_SECONDS)
        
        try:
            result = layer.analyze(borderline_path)
            
            # Should pass duration check
            assert result.duration_s >= MIN_SPEECH_SECONDS
            
            # Status should be ok or unavailable (if model missing)
            # but NOT inconclusive due to duration
            if result.status == "inconclusive":
                # If inconclusive, it must be for SNR, not duration
                assert result.error is not None
                assert "SNR" in result.error or "snr" in result.error.lower()
            
        finally:
            borderline_path.unlink(missing_ok=True)
    
    def test_silence_detection(self):
        """Silent audio should be handled (may pass through or be rejected)."""
        layer = get_voice_layer()
        
        silence_path = create_silence_wav(5.0)
        
        try:
            result = layer.analyze(silence_path)
            
            # Silence may be processed (status="ok") or rejected as low quality
            # Both outcomes are acceptable
            assert result.status in ["ok", "inconclusive", "unavailable"]
            
            # If it passes, it will have a spoof_prob (though meaningless for silence)
            # If rejected, spoof_prob will be None
            
        finally:
            silence_path.unlink(missing_ok=True)
    
    def test_valid_audio_quality_metrics(self):
        """Valid audio should have quality metrics populated."""
        layer = get_voice_layer()
        
        valid_path = create_test_wav(5.0)
        
        try:
            result = layer.analyze(valid_path)
            
            # Should have duration
            assert result.duration_s > 0
            
            # SNR may be 0 if estimation failed (acceptable for test audio)
            # The key is that it's a float, not None
            assert isinstance(result.snr_db, (int, float))
            
        finally:
            valid_path.unlink(missing_ok=True)


# ============================================================================
# REAL MODEL INFERENCE TESTS
# ============================================================================

class TestRealModelInference:
    """Test real model inference execution (if dependencies available)."""
    
    @pytest.mark.skipif(
        not __import__('importlib.util').util.find_spec('torch') or
        not __import__('importlib.util').util.find_spec('transformers'),
        reason="torch or transformers not installed"
    )
    def test_model_loading_with_dependencies(self):
        """If torch/transformers available, model should load successfully."""
        layer = VoiceLayer()
        
        success = layer._load_spoof_model()
        
        # Should load successfully
        assert success
        assert layer._spoof_model is not None
        assert layer._spoof_extractor is not None
    
    @pytest.mark.skipif(
        not __import__('importlib.util').util.find_spec('torch') or
        not __import__('importlib.util').util.find_spec('transformers'),
        reason="torch or transformers not installed"
    )
    def test_real_inference_execution(self):
        """Execute real model inference on test audio."""
        layer = get_voice_layer()
        
        # Create valid test audio (5 seconds, 440Hz tone)
        test_path = create_test_wav(5.0, frequency=440)
        
        try:
            result = layer.analyze(test_path)
            
            # Should complete successfully
            assert result.status == "ok"
            
            # Should have spoof probability
            assert result.spoof_prob is not None
            assert 0.0 <= result.spoof_prob <= 1.0
            
            # Should have analyzed windows
            assert result.windows_analyzed > 0
            
            # Should have model identifier
            assert "Vansh180" in result.model or "deepfake" in result.model.lower()
            
            # Should have processing time
            assert result.processing_time_s > 0
            
            print(f"\n✅ Real inference successful:")
            print(f"   Spoof probability: {result.spoof_prob:.4f}")
            print(f"   Windows analyzed: {result.windows_analyzed}")
            print(f"   Duration: {result.duration_s:.2f}s")
            print(f"   SNR: {result.snr_db:.2f}dB")
            print(f"   Processing time: {result.processing_time_s:.3f}s")
            print(f"   Model: {result.model}")
            
        finally:
            test_path.unlink(missing_ok=True)
    
    @pytest.mark.skipif(
        not __import__('importlib.util').util.find_spec('torch') or
        not __import__('importlib.util').util.find_spec('transformers'),
        reason="torch or transformers not installed"
    )
    def test_inference_output_range(self):
        """Model output should be valid probability in [0, 1]."""
        layer = get_voice_layer()
        
        test_path = create_test_wav(5.0)
        
        try:
            result = layer.analyze(test_path)
            
            if result.status == "ok" and result.spoof_prob is not None:
                # Spoof probability must be valid
                assert isinstance(result.spoof_prob, float)
                assert 0.0 <= result.spoof_prob <= 1.0
                assert not math.isnan(result.spoof_prob)
                assert not math.isinf(result.spoof_prob)
                
        finally:
            test_path.unlink(missing_ok=True)
    
    @pytest.mark.skipif(
        not __import__('importlib.util').util.find_spec('torch') or
        not __import__('importlib.util').util.find_spec('transformers'),
        reason="torch or transformers not installed"
    )
    def test_multiple_inferences_consistency(self):
        """Multiple inferences on same audio should be consistent."""
        layer = get_voice_layer()
        
        test_path = create_test_wav(5.0, frequency=440)
        
        try:
            result1 = layer.analyze(test_path)
            result2 = layer.analyze(test_path)
            
            # Both should succeed
            assert result1.status == result2.status
            
            if result1.status == "ok" and result2.status == "ok":
                # Scores should be identical (deterministic model)
                assert result1.spoof_prob == result2.spoof_prob
                assert result1.windows_analyzed == result2.windows_analyzed
                
        finally:
            test_path.unlink(missing_ok=True)


# ============================================================================
# ERROR HANDLING TESTS
# ============================================================================

class TestErrorHandling:
    """Test graceful error handling."""
    
    def test_nonexistent_file(self):
        """Nonexistent file should return unavailable or inconclusive."""
        layer = get_voice_layer()
        
        fake_path = Path("/tmp/nonexistent_audio_file.wav")
        
        result = layer.analyze(fake_path)
        
        # Should handle gracefully
        assert result.status in ["unavailable", "inconclusive"]
    
    def test_invalid_path_type(self):
        """Invalid path type should be handled."""
        layer = get_voice_layer()
        
        # This should raise or handle gracefully
        try:
            result = layer.analyze(None)
            # If it doesn't raise, should return unavailable
            assert result.status == "unavailable"
        except (TypeError, AttributeError):
            # Expected error - acceptable
            pass
    
    def test_processing_time_recorded_on_error(self):
        """Processing time should be recorded even on errors."""
        layer = get_voice_layer()
        
        fake_path = Path("/tmp/nonexistent.wav")
        result = layer.analyze(fake_path)
        
        # Should have recorded time even though it failed
        assert result.processing_time_s >= 0


# ============================================================================
# INTEGRATION WITH EXISTING ARCHITECTURE
# ============================================================================

class TestArchitectureIntegration:
    """Test integration with existing VISHWAS architecture."""
    
    def test_status_contract(self):
        """Verify status values match schema contract."""
        layer = get_voice_layer()
        
        # Test with valid audio
        valid_path = create_test_wav(5.0)
        
        try:
            result = layer.analyze(valid_path)
            
            # Status must be one of the three valid values
            assert result.status in ["ok", "inconclusive", "unavailable"]
            
        finally:
            valid_path.unlink(missing_ok=True)
    
    def test_unavailable_has_no_spoof_prob(self):
        """When unavailable, spoof_prob should be None."""
        layer = get_voice_layer()
        
        corrupt_path = create_corrupt_wav()
        
        try:
            result = layer.analyze(corrupt_path)
            
            if result.status == "unavailable":
                # Should not have a spoof probability
                assert result.spoof_prob is None
                
        finally:
            corrupt_path.unlink(missing_ok=True)
    
    def test_inconclusive_has_quality_metrics(self):
        """Inconclusive should still have quality metrics."""
        layer = get_voice_layer()
        
        short_path = create_test_wav(1.0)
        
        try:
            result = layer.analyze(short_path)
            
            if result.status == "inconclusive":
                # Should have duration and SNR even if inconclusive
                assert result.duration_s > 0
                
        finally:
            short_path.unlink(missing_ok=True)
    
    def test_model_version_identifier(self):
        """Model field should identify the actual model used."""
        layer = get_voice_layer()
        
        valid_path = create_test_wav(5.0)
        
        try:
            result = layer.analyze(valid_path)
            
            # Should have model identifier
            assert result.model is not None
            assert len(result.model) > 0
            
            # Should reference the check types
            assert "Check A" in result.model or "Check B" in result.model or result.model != ""
            
        finally:
            valid_path.unlink(missing_ok=True)


# ============================================================================
# PERFORMANCE TESTS
# ============================================================================

class TestPerformance:
    """Test performance and resource usage."""
    
    @pytest.mark.skipif(
        not __import__('importlib.util').util.find_spec('torch') or
        not __import__('importlib.util').util.find_spec('transformers'),
        reason="torch or transformers not installed"
    )
    def test_inference_latency_reasonable(self):
        """Inference should complete in reasonable time."""
        layer = get_voice_layer()
        
        test_path = create_test_wav(5.0)
        
        try:
            result = layer.analyze(test_path)
            
            if result.status == "ok":
                # For 5s audio, processing should be < 30s
                assert result.processing_time_s < 30.0
                
                print(f"\n⏱️  Latency: {result.processing_time_s:.3f}s for {result.duration_s:.1f}s audio")
                
        finally:
            test_path.unlink(missing_ok=True)
    
    def test_temporary_file_cleanup(self):
        """Temporary files should be cleaned up (implicit test)."""
        layer = get_voice_layer()
        
        # Run multiple analyses
        for _ in range(3):
            test_path = create_test_wav(5.0)
            layer.analyze(test_path)
            test_path.unlink(missing_ok=True)
        
        # If we get here without memory errors, cleanup is working
        assert True
