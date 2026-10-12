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
        """Generate a suspicious call scenario."""
        return {
            "language": "en",
            "transcript_segments": [
                {
                    "start": 0.0,
                    "end": 3.5,
                    "speaker": None,
                    "text": "Hello, this is calling from bank security department.",
                    "language": "en"
                },
                {
                    "start": 3.8,
                    "end": 6.2,
                    "speaker": None,
                    "text": "We have detected suspicious activity on your account.",
                    "language": "en"
                },
                {
                    "start": 6.5,
                    "end": 9.0,
                    "speaker": None,
                    "text": "Please share your OTP immediately to verify your identity.",
                    "language": "en"
                },
                {
                    "start": 9.3,
                    "end": 11.5,
                    "speaker": None,
                    "text": "This is urgent. Your account will be blocked in 10 minutes.",
                    "language": "en"
                }
            ],
            "agent_findings": [
                {
                    "agent": "impersonation_agent",
                    "signal": "authority_impersonation",
                    "severity": "high",
                    "evidence_text": "Hello, this is calling from bank security department.",
                    "start_time": 0.0,
                    "end_time": 3.5,
                    "confidence": None,
                    "source": "mock"
                },
                {
                    "agent": "threat_agent",
                    "signal": "urgency_tactic",
                    "severity": "medium",
                    "evidence_text": "This is urgent. Your account will be blocked in 10 minutes.",
                    "start_time": 9.3,
                    "end_time": 11.5,
                    "confidence": None,
                    "source": "mock"
                },
                {
                    "agent": "request_agent",
                    "signal": "sensitive_credential_request",
                    "severity": "critical",
                    "evidence_text": "Please share your OTP immediately to verify your identity.",
                    "start_time": 6.5,
                    "end_time": 9.0,
                    "confidence": None,
                    "source": "mock"
                }
            ],
            "risk_level": "high",
            "risk_score": None,
            "reasons": [
                "Authority impersonation detected (bank security claim)",
                "Sensitive credential request (OTP)",
                "Urgency tactics employed to pressure immediate action",
                "Threat of account blocking to create fear"
            ],
            "recommended_actions": [
                "Do not share OTP or any sensitive information with this caller",
                "Hang up immediately and contact your bank directly using official channels",
                "Verify the caller's identity through independent means",
                "Report this incident to your bank's fraud department",
                "Banks never ask for OTP or passwords over the phone"
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
            "risk_level": "low",
            "risk_score": None,
            "reasons": [
                "No suspicious patterns detected",
                "No requests for sensitive credentials",
                "No urgency or threat tactics",
                "Professional and courteous communication"
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
    
    def analyze_call(self, db: Session, call_id: str) -> None:
        """
        Run mock analysis on a call recording.
        
        This method:
        1. Updates call status to 'processing'
        2. Simulates processing delay
        3. Generates mock analysis results
        4. Saves the report
        5. Updates call status to 'completed'
        
        Args:
            db: Database session
            call_id: UUID of the call to analyze
        """
        try:
            logger.info(f"Starting mock analysis for call: {call_id}")
            
            # Get call record
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
                agent_findings_json=json.dumps(scenario["agent_findings"]),
                risk_level=scenario["risk_level"],
                risk_score=scenario.get("risk_score"),
                reasons_json=json.dumps(scenario["reasons"]),
                recommended_actions_json=json.dumps(scenario["recommended_actions"]),
                warnings_json=json.dumps(warnings),
                analysis_mode=self.analysis_mode
            )
            
            # Check if report already exists (shouldn't happen, but be safe)
            existing_report = db.query(AnalysisReport).filter(
                AnalysisReport.call_id == call_id
            ).first()
            
            if existing_report:
                logger.warning(f"Report already exists for call {call_id}, updating...")
                existing_report.transcript_json = report.transcript_json
                existing_report.agent_findings_json = report.agent_findings_json
                existing_report.risk_level = report.risk_level
                existing_report.risk_score = report.risk_score
                existing_report.reasons_json = report.reasons_json
                existing_report.recommended_actions_json = report.recommended_actions_json
                existing_report.warnings_json = report.warnings_json
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


# Singleton instance
mock_analysis_service = MockAnalysisService()
