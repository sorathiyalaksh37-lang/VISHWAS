"""
Mock analysis service for Phase 1 demonstration.
This service provides clearly labeled sample analysis results.
"""
import json
import logging
import time
from datetime import datetime
from sqlalchemy.orm import Session
from typing import Dict, List

from app.core.config import settings
from app.models.call import CallRecord, AnalysisReport

logger = logging.getLogger(__name__)


class MockAnalysisService:
    """
    Mock analysis service that generates illustrative fraud detection reports.
    
    This service demonstrates the complete workflow before actual AI models are integrated.
    All results are clearly labeled as mock data.
    """
    
    # Demo scenarios
    SCENARIO_SUSPICIOUS = "suspicious"
    SCENARIO_LEGITIMATE = "legitimate"
    
    def __init__(self):
        """Initialize mock analysis service."""
        self.analysis_mode = "mock"
    
    def _get_suspicious_scenario(self) -> Dict:
        """Generate a suspicious call scenario — CRITICAL threat level with v3 schema."""
        return {
            "language": "en",
            "transcript_segments": [
                {
                    "start": 0.0,
                    "end": 4.2,
                    "speaker": "CALLER",
                    "text": "Good after Mr. Sharma, I'm a Police Officer from Cyber Security Cell. My badge number is PP-4471.",
                    "language": "en"
                },
                {
                    "start": 4.5,
                    "end": 9.1,
                    "speaker": "CALLER",
                    "text": "We have detected a fraudulent transaction of \u20b950,000 from your account to a flagged account linked to money laundering.",
                    "language": "en"
                },
                {
                    "start": 9.4,
                    "end": 13.8,
                    "speaker": "VICTIM",
                    "text": "Hello? What? I didn't receive any notification regarding this.",
                    "language": "en"
                },
                {
                    "start": 14.1,
                    "end": 18.9,
                    "speaker": "CALLER",
                    "text": "Sir, for your account safety and my OTP has a transaction reference of \u20b950,000. I need you to read out the 6-digit code right now, police complaint 420 will be lodged and your account certificate is in \u20b950,000.",
                    "language": "en"
                },
                {
                    "start": 19.2,
                    "end": 23.5,
                    "speaker": "CALLER",
                    "text": "My SMS says: Do not share this OTP with anyone including bank staff. Read out the 6 digit code received on your mobile screen now.",
                    "language": "en"
                }
            ],
            "agent_findings": [
                {
                    "agent": "impersonation_agent",
                    "signal": "authority_impersonation",
                    "severity": "critical",
                    "evidence_text": "I'm a Police Officer from Cyber Security Cell. My badge number is PP-4471.",
                    "start_time": 0.0,
                    "end_time": 4.2,
                    "confidence": 0.96,
                    "source": "mock"
                },
                {
                    "agent": "threat_agent",
                    "signal": "urgency_tactic",
                    "severity": "high",
                    "evidence_text": "police complaint 420 will be lodged and your account certificate is in \u20b950,000.",
                    "start_time": 14.1,
                    "end_time": 18.9,
                    "confidence": 0.91,
                    "source": "mock"
                },
                {
                    "agent": "request_agent",
                    "signal": "otp_solicitation",
                    "severity": "critical",
                    "evidence_text": "Read out the 6 digit code received on your mobile screen now.",
                    "start_time": 19.2,
                    "end_time": 23.5,
                    "confidence": 0.99,
                    "source": "mock"
                },
                {
                    "agent": "deepfake_agent",
                    "signal": "synthetic_voice_detected",
                    "severity": "high",
                    "evidence_text": "Real-time voice synthesis markers detected — spectral artifacts at 3.2kHz, GAN fingerprint probability 84.2%",
                    "start_time": 0.0,
                    "end_time": 23.5,
                    "confidence": 0.84,
                    "source": "mock"
                }
            ],
            "risk_level": "CRITICAL",
            "risk_score": 86,
            "category_scores": {
                "identity": 23,
                "request": 29,
                "behavior": 19,
                "channel": 10,
                "voice": 9
            },
            "fired_rules": [
                "authority_impersonation",
                "otp_request_detected",
                "urgency_language",
                "legal_threat_coercion",
                "synthetic_voice_marker",
                "police_impersonation",
                "credential_request_otp",
                "killchain_stage_execution"
            ],
            "killchain_stage": "Elicitation",
            "voice_data": {
                "status": "ok",
                "spoof_prob": 0.842,
                "windows_analyzed": 23,
                "speaker_match": {
                    "claimed_contact": None,
                    "similarity": 0.11,
                    "enrolled": False
                },
                "quality": {
                    "duration_s": 23.5,
                    "snr_db": 18.5
                },
                "model": "speechbrain/spkrec-ecapa-voxceleb (mock)"
            },
            "verification": {
                "action": "callback_official_number",
                "target": "Cyber Cell Helpline 1930 or your bank's official number",
                "safe_word_prompt": True
            },
            "counterfactuals": [
                {"change": "If call originated from verified government number", "new_score": 32},
                {"change": "If caller did not request OTP", "new_score": 41},
                {"change": "If voice was not synthetic", "new_score": 55}
            ],
            "reasons": [
                "Coercive authority impersonation — caller claims to be Cyber Cell police officer with badge PP-4471",
                "OTP solicitation detected — explicitly asked to read out 6-digit code from SMS",
                "Legal threat coercion — threatened FIR/police complaint to force compliance",
                "Real-time deepfake voice signature — 84.2% synthetic probability with GAN markers",
                "Urgency language — immediate action demanded to prevent account freeze",
                "Kill-chain stage: Elicitation — active credential harvesting in progress"
            ],
            "recommended_actions": [
                "HANG UP IMMEDIATELY — Do not share the OTP under any circumstances",
                "Call back the Cyber Crime Helpline at 1930 to verify legitimacy",
                "Contact your bank directly using the official number on their website or card",
                "Never share OTP with anyone claiming to be police, bank, or government",
                "Report this number to cybercrime.gov.in and TRAI DND registry",
                "Screenshot and save the caller's number for reporting"
            ]
        }
    
    def _get_legitimate_scenario(self) -> Dict:
        """Generate a legitimate call scenario."""
        return {
            "language": "en",
            "transcript_segments": [
                {
                    "start": 0.0,
                    "end": 2.5,
                    "speaker": None,
                    "text": "Hello, this is Sarah from customer service.",
                    "language": "en"
                },
                {
                    "start": 2.8,
                    "end": 5.5,
                    "speaker": None,
                    "text": "I'm calling to follow up on your recent inquiry about account balance.",
                    "language": "en"
                },
                {
                    "start": 5.8,
                    "end": 8.0,
                    "speaker": None,
                    "text": "Would you like me to send the information to your registered email?",
                    "language": "en"
                }
            ],
            "agent_findings": [],
            "risk_level": "LOW",
            "risk_score": 12,
            "category_scores": {
                "identity": 2,
                "request": 1,
                "behavior": 3,
                "channel": 2,
                "voice": 1
            },
            "fired_rules": [],
            "killchain_stage": None,
            "voice_data": {
                "spoof_probability": 0.08,
                "confidence": 0.91,
                "is_likely_synthetic": False,
                "quality": {
                    "snr_db": 24.3,
                    "overall": "good"
                }
            },
            "verification": {
                "recommended_steps": [
                    "standard_verification"
                ],
                "safe_actions": [
                    "Verify through registered email if needed",
                    "Use official customer service channels for follow-up"
                ],
                "danger_actions": []
            },
            "timeline": [
                {
                    "timestamp": 0.0,
                    "event": "call_start",
                    "description": "Call initiated"
                },
                {
                    "timestamp": 0.0,
                    "event": "professional_greeting",
                    "description": "Professional introduction"
                },
                {
                    "timestamp": 2.8,
                    "event": "legitimate_purpose",
                    "description": "Follow-up on existing inquiry"
                },
                {
                    "timestamp": 5.8,
                    "event": "non_invasive_request",
                    "description": "Offers to send info to registered email"
                }
            ],
            "reasons": [
                "No suspicious patterns detected",
                "No requests for sensitive credentials",
                "No urgency or threat tactics",
                "Professional and courteous communication",
                "Voice analysis shows natural human speech patterns"
            ],
            "recommended_actions": [
                "Verify caller identity if needed by calling back using official contact information",
                "Continue to be cautious about sharing personal information",
                "Keep records of all financial communications"
            ]
        }
    
    def _select_scenario(self, call_id: str) -> Dict:
        """
        Select a demo scenario based on call_id.
        In Phase 1, we use a simple heuristic for demonstration.
        """
        # Use call_id hash to deterministically select scenario for testing
        # In real usage, this would be explicitly selected or random
        hash_value = sum(ord(c) for c in call_id)
        if hash_value % 2 == 0:
            return self._get_suspicious_scenario()
        else:
            return self._get_legitimate_scenario()
    
    def analyze_call(self, call_id: str) -> None:
        """
        Run mock analysis on a call recording.
        
        This method:
        1. Updates call status to 'processing'
        2. Simulates processing delay
        3. Generates mock analysis results
        4. Saves the report
        5. Updates call status to 'completed'
        
        Args:
            call_id: UUID of the call to analyze
        """
        # Create a new database session for the background task
        from app.database.session import SessionLocal
        db = SessionLocal()
        
        try:
            logger.info(f"Starting mock analysis for call: {call_id}")
            
            # Get call recordWorking..
            
            call = db.query(CallRecord).filter(CallRecord.id == call_id).first()
            if not call:
                logger.error(f"Call not found: {call_id}")
                return
            
            # Update status to processing
            call.status = "processing"
            call.analysis_mode = self.analysis_mode
            db.commit()
            logger.info(f"Call {call_id} status updated to 'processing'")
            
            # Simulate processing delay
            delay = settings.mock_processing_delay_seconds
            logger.info(f"Simulating processing delay: {delay} seconds")
            time.sleep(delay)
            
            # Select demo scenario
            scenario = self._select_scenario(call_id)
            
            # Create transcript
            transcript_data = {
                "call_id": call_id,
                "language": scenario["language"],
                "transcription_status": "completed",
                "segments": scenario["transcript_segments"],
                "is_mock": True
            }
            
            # Create warnings
            warnings = [
                "This is a mock analysis for Phase 1 demonstration",
                "Real fraud detection will be implemented in future phases",
                "Do not rely on this analysis for actual fraud prevention"
            ]
            
            # Create analysis report
            report = AnalysisReport(
                call_id=call_id,
                transcript_json=json.dumps(transcript_data),
                voice_json=json.dumps(scenario.get("voice_data")),
                agent_findings_json=json.dumps(scenario["agent_findings"]),
                risk_level=scenario["risk_level"],
                risk_score=scenario.get("risk_score"),
                reasons_json=json.dumps(scenario["reasons"]),
                recommended_actions_json=json.dumps(scenario["recommended_actions"]),
                warnings_json=json.dumps(warnings),
                analysis_mode=self.analysis_mode,
                # v3 Trust Engine fields
                category_scores_json=json.dumps(scenario.get("category_scores")),
                fired_rules_json=json.dumps(scenario.get("fired_rules", [])),
                verification_json=json.dumps(scenario.get("verification")),
                killchain_stage=scenario.get("killchain_stage")
            )
            
            # Check if report already exists (shouldn't happen, but be safe)
            existing_report = db.query(AnalysisReport).filter(
                AnalysisReport.call_id == call_id
            ).first()
            
            if existing_report:
                logger.warning(f"Report already exists for call {call_id}, updating...")
                existing_report.transcript_json = report.transcript_json
                existing_report.voice_json = report.voice_json
                existing_report.agent_findings_json = report.agent_findings_json
                existing_report.risk_level = report.risk_level
                existing_report.risk_score = report.risk_score
                existing_report.reasons_json = report.reasons_json
                existing_report.recommended_actions_json = report.recommended_actions_json
                existing_report.warnings_json = report.warnings_json
                existing_report.category_scores_json = report.category_scores_json
                existing_report.fired_rules_json = report.fired_rules_json
                existing_report.verification_json = report.verification_json
                existing_report.killchain_stage = report.killchain_stage
            else:
                db.add(report)
            
            # Update call status to completed
            call.status = "completed"
            call.completed_at = datetime.utcnow()
            
            db.commit()
            logger.info(f"Mock analysis completed for call: {call_id}")
            
        except Exception as e:
            logger.error(f"Mock analysis failed for call {call_id}: {e}")
            
            # Update call status to failed
            try:
                call = db.query(CallRecord).filter(CallRecord.id == call_id).first()
                if call:
                    call.status = "failed"
                    call.error_message = f"Analysis failed: {str(e)}"
                    call.completed_at = datetime.utcnow()
                    db.commit()
            except Exception as commit_error:
                logger.error(f"Failed to update error status: {commit_error}")
                db.rollback()
        finally:
            # Always close the database session
            db.close()


# Singleton instance
mock_analysis_service = MockAnalysisService()
