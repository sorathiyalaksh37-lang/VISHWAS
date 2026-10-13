"""
Tests for anti-spoof evaluation harness (Phase 5).

Tests manifest validation, dataclass structures, and metrics calculation.
Full evaluation tests require labeled dataset (not available).
"""
import pytest
import tempfile
import json
from pathlib import Path
from app.evaluation.anti_spoof_evaluator import (
    EvaluationSample, 
    PredictionResult,
    AntiSpoofEvaluator
)


class TestEvaluationSample:
    """Test EvaluationSample dataclass and validation."""
    
    def test_valid_sample(self):
        """Test creating a valid evaluation sample."""
        sample = EvaluationSample(
            sample_id="test_001",
            audio_path=Path("/tmp/test.wav"),
            label="genuine"
        )
        
        is_valid, error = sample.validate()
        assert is_valid
        assert error is None
    
    def test_invalid_label(self):
        """Test sample with invalid label."""
        sample = EvaluationSample(
            sample_id="test_001",
            audio_path=Path("/tmp/test.wav"),
            label="invalid_label"
        )
        
        is_valid, error = sample.validate()
        assert not is_valid
        assert "genuine or spoofed" in error.lower()
    
    def test_path_traversal_detection(self):
        """Test path traversal detection in audio path."""
        sample = EvaluationSample(
            sample_id="test_001",
            audio_path=Path("../../etc/passwd"),
            label="genuine"
        )
        
        is_valid, error = sample.validate()
        assert not is_valid
        assert "traversal" in error.lower()
    
    def test_optional_fields_accepted(self):
        """Test that optional fields are properly stored."""
        sample = EvaluationSample(
            sample_id="test_001",
            audio_path=Path("/tmp/test.wav"),
            label="spoofed",
            language="hi",
            accent="mumbai",
            recording_condition="studio",
            source_dataset="asvspoof2021",
            speaker_id="spk_123"
        )
        
        assert sample.language == "hi"
        assert sample.accent == "mumbai"
        assert sample.recording_condition == "studio"
        assert sample.source_dataset == "asvspoof2021"
        assert sample.speaker_id == "spk_123"


class TestPredictionResult:
    """Test PredictionResult dataclass."""
    
    def test_correct_prediction(self):
        """Test prediction result with correct classification."""
        result = PredictionResult(
            sample_id="test_001",
            true_label="genuine",
            predicted_label="genuine",
            spoof_probability=0.25,
            threshold_used=0.60,
            inference_time_s=0.15,
            success=True
        )
        
        assert result.is_correct()
        assert result.true_label == result.predicted_label
    
    def test_incorrect_prediction(self):
        """Test prediction result with incorrect classification."""
        result = PredictionResult(
            sample_id="test_001",
            true_label="genuine",
            predicted_label="spoofed",
            spoof_probability=0.75,
            threshold_used=0.60,
            inference_time_s=0.15,
            success=True
        )
        
        assert not result.is_correct()
        assert result.true_label != result.predicted_label
    
    def test_failed_inference(self):
        """Test prediction result for failed inference."""
        result = PredictionResult(
            sample_id="test_001",
            true_label="genuine",
            predicted_label="unknown",
            spoof_probability=-1.0,
            threshold_used=0.60,
            inference_time_s=0.05,
            success=False,
            error_message="Model unavailable"
        )
        
        assert not result.success
        assert result.error_message == "Model unavailable"
        assert result.spoof_probability == -1.0


class TestManifestLoading:
    """Test manifest file loading and validation."""
    
    def test_load_valid_manifest(self):
        """Test loading a valid JSONL manifest."""
        with tempfile.TemporaryDirectory() as tmpdir:
            manifest_path = Path(tmpdir) / "manifest.jsonl"
            eval_dir = Path(tmpdir)
            
            # Create dummy audio files
            (eval_dir / "genuine.wav").touch()
            (eval_dir / "spoofed.wav").touch()
            
            # Write manifest
            with open(manifest_path, 'w') as f:
                f.write(json.dumps({
                    "sample_id": "sample_001",
                    "audio_path": "genuine.wav",
                    "label": "genuine"
                }) + '\n')
                f.write(json.dumps({
                    "sample_id": "sample_002",
                    "audio_path": "spoofed.wav",
                    "label": "spoofed"
                }) + '\n')
            
            evaluator = AntiSpoofEvaluator(
                manifest_path=manifest_path,
                evaluation_dir=eval_dir,
                use_real_model=False
            )
            evaluator.load_manifest()
            
            assert len(evaluator.samples) == 2
            assert evaluator.samples[0].label == "genuine"
            assert evaluator.samples[1].label == "spoofed"
    
    def test_empty_manifest(self):
        """Test that empty manifest raises error."""
        with tempfile.TemporaryDirectory() as tmpdir:
            manifest_path = Path(tmpdir) / "empty.jsonl"
            manifest_path.touch()  # Empty file
            
            evaluator = AntiSpoofEvaluator(
                manifest_path=manifest_path,
                evaluation_dir=Path(tmpdir),
                use_real_model=False
            )
            
            with pytest.raises(ValueError, match="No valid samples"):
                evaluator.load_manifest()
    
    def test_missing_manifest_file(self):
        """Test that missing manifest file raises error."""
        evaluator = AntiSpoofEvaluator(
            manifest_path=Path("/nonexistent/manifest.jsonl"),
            evaluation_dir=Path("/tmp"),
            use_real_model=False
        )
        
        with pytest.raises(FileNotFoundError):
            evaluator.load_manifest()
    
    def test_malformed_json_skipped(self):
        """Test that malformed JSON lines are skipped with warning."""
        with tempfile.TemporaryDirectory() as tmpdir:
            manifest_path = Path(tmpdir) / "manifest.jsonl"
            eval_dir = Path(tmpdir)
            (eval_dir / "test.wav").touch()
            
            with open(manifest_path, 'w') as f:
                f.write('{"sample_id": "s1", "audio_path": "test.wav", "label": "genuine"}\n')
                f.write('not valid json\n')  # Malformed line
                f.write('{"sample_id": "s2", "audio_path": "test.wav", "label": "spoofed"}\n')
            
            evaluator = AntiSpoofEvaluator(
                manifest_path=manifest_path,
                evaluation_dir=eval_dir,
                use_real_model=False
            )
            evaluator.load_manifest()
            
            # Should load 2 valid samples, skip the malformed line
            assert len(evaluator.samples) == 2


class TestMockInference:
    """Test mock inference mode (no real model required)."""
    
    def test_mock_inference_deterministic(self):
        """Test that mock inference is deterministic for same sample_id."""
        with tempfile.TemporaryDirectory() as tmpdir:
            manifest_path = Path(tmpdir) / "manifest.jsonl"
            eval_dir = Path(tmpdir)
            (eval_dir / "test.wav").touch()
            
            with open(manifest_path, 'w') as f:
                f.write('{"sample_id": "test_001", "audio_path": "test.wav", "label": "genuine"}\n')
            
            evaluator = AntiSpoofEvaluator(
                manifest_path=manifest_path,
                evaluation_dir=eval_dir,
                threshold=0.60,
                use_real_model=False  # Use mock
            )
            evaluator.load_manifest()
            
            sample = evaluator.samples[0]
            result1 = evaluator.run_inference(sample)
            result2 = evaluator.run_inference(sample)
            
            # Same sample should give same result
            assert result1.spoof_probability == result2.spoof_probability
            assert result1.predicted_label == result2.predicted_label
            assert result1.success
            assert result2.success
