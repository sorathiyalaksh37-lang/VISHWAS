"""
Agent Orchestrator — Coordinates Fraud and Skeptic agents.

Handles bounded execution, validation, and graceful fallback to Phase 2.
"""
import logging
import asyncio
from typing import Optional

from app.llm.provider import get_llm_provider
from app.agents.fraud_agent import FraudAgent
from app.agents.skeptic_agent import SkepticAgent
from app.schemas.agent import (
    AgentEvidencePackage,
    AgentAnalysisResult,
    AgentFinding
)
from app.schemas.evidence import EvidenceExtraction
from app.trust_engine.trust_graph import TrustGraph
from app.trust_engine.scoring import ScoreBreakdown

logger = logging.getLogger(__name__)


class AgentOrchestrator:
    """
    Orchestrates Fraud and Skeptic agents for Tier 2 analysis.
    
    Execution sequence:
    1. Build evidence package
    2. Execute Fraud Agent (with timeout)
    3. Validate Fraud Agent output
    4. Execute Skeptic Agent (with timeout)
    5. Validate Skeptic Agent output
    6. Return combined result or fallback status
    """
    
    def __init__(self):
        """Initialize orchestrator."""
        self.llm_provider = get_llm_provider()
        
        if self.llm_provider:
            self.fraud_agent = FraudAgent(self.llm_provider)
            self.skeptic_agent = SkepticAgent(self.llm_provider)
            logger.info("AgentOrchestrator initialized with LLM provider")
        else:
            self.fraud_agent = None
            self.skeptic_agent = None
            logger.info("AgentOrchestrator initialized WITHOUT LLM provider (Tier 2 disabled)")
    
    async def analyze(
        self,
        call_id: str,
        evidence: EvidenceExtraction,
        trust_context: dict,
        score_breakdown: ScoreBreakdown,
        timeout_per_agent: float = 30.0
    ) -> AgentAnalysisResult:
        """
        Run Tier 2 agent analysis.
        
        Args:
            call_id: Call identifier
            evidence: Validated Phase 2 evidence
            trust_context: Trust Graph context
            score_breakdown: Phase 2 score breakdown
            timeout_per_agent: Timeout for each agent
            
        Returns:
            AgentAnalysisResult (may be empty if Tier 2 unavailable)
        """
        # Check if Tier 2 is available
        if not self.llm_provider or not self.fraud_agent or not self.skeptic_agent:
            logger.info(f"[{call_id}] Tier 2 unavailable, returning disabled status")
            return AgentAnalysisResult(
                tier2_status="disabled",
                warnings=["Tier 2 agentic AI is disabled or unavailable"]
            )
        
        # Build evidence package
        try:
            evidence_package = self._build_evidence_package(
                call_id,
                evidence,
                trust_context,
                score_breakdown
            )
        except Exception as e:
            logger.error(f"[{call_id}] Failed to build evidence package: {e}")
            return AgentAnalysisResult(
                tier2_status="unavailable",
                warnings=[f"Evidence package creation failed: {str(e)}"]
            )
        
        # Execute Fraud Agent
        fraud_findings: list[AgentFinding] = []
        fraud_failed = False
        
        try:
            fraud_response = await asyncio.wait_for(
                self.fraud_agent.analyze(evidence_package, timeout_per_agent),
                timeout=timeout_per_agent + 5  # Extra buffer
            )
            fraud_findings = fraud_response.findings
            logger.info(f"[{call_id}] Fraud Agent: {len(fraud_findings)} findings")
            
        except asyncio.TimeoutError:
            logger.warning(f"[{call_id}] Fraud Agent timeout")
            fraud_failed = True
        except Exception as e:
            logger.error(f"[{call_id}] Fraud Agent failed: {e}")
            fraud_failed = True
        
        # If Fraud Agent failed, return Phase 2 only
        if fraud_failed:
            return AgentAnalysisResult(
                tier2_status="fraud_failed",
                warnings=["Fraud Agent execution failed or timed out"]
            )
        
        # Execute Skeptic Agent
        skeptic_challenges = []
        skeptic_failed = False
        
        try:
            skeptic_response = await asyncio.wait_for(
                self.skeptic_agent.analyze(
                    evidence_package,
                    fraud_findings,
                    timeout_per_agent
                ),
                timeout=timeout_per_agent + 5
            )
            skeptic_challenges = skeptic_response.challenges
            logger.info(f"[{call_id}] Skeptic Agent: {len(skeptic_challenges)} challenges")
            
        except asyncio.TimeoutError:
            logger.warning(f"[{call_id}] Skeptic Agent timeout")
            skeptic_failed = True
        except Exception as e:
            logger.error(f"[{call_id}] Skeptic Agent failed: {e}")
            skeptic_failed = True
        
        # Determine final status
        if skeptic_failed:
            tier2_status = "skeptic_failed"
            warnings = ["Skeptic Agent execution failed, Fraud findings provisional"]
        else:
            tier2_status = "completed"
            warnings = []
        
        # Build result
        return AgentAnalysisResult(
            fraud_findings=fraud_findings,
            skeptic_challenges=skeptic_challenges,
            tier2_status=tier2_status,
            warnings=warnings,
            agent_metadata={
                "fraud_agent_findings": len(fraud_findings),
                "skeptic_agent_challenges": len(skeptic_challenges)
            }
        )
    
    def _build_evidence_package(
        self,
        call_id: str,
        evidence: EvidenceExtraction,
        trust_context: dict,
        score_breakdown: ScoreBreakdown
    ) -> AgentEvidencePackage:
        """Build bounded evidence package for agents."""
        
        # Convert evidence to serializable format
        evidence_summary = {}
        
        # Claims
        if evidence.claims and evidence.claims.claims:
            evidence_summary["claims"] = {
                "claims": [
                    {
                        "id": f"claim_{i}",
                        "type": claim.type,
                        "value": claim.value,
                        "confidence": claim.confidence,
                        "quote": claim.quote[:100]  # Truncate for privacy
                    }
                    for i, claim in enumerate(evidence.claims.claims)
                ]
            }
        
        # Requests
        requests_summary = {}
        
        if evidence.requests.credential_requests:
            requests_summary["credential_requests"] = [
                {
                    "id": f"cred_{i}",
                    "type": req.type,
                    "confidence": req.confidence
                }
                for i, req in enumerate(evidence.requests.credential_requests)
            ]
        
        if evidence.requests.money_requests:
            requests_summary["money_requests"] = [
                {
                    "id": f"money_{i}",
                    "amount": req.amount,
                    "currency": req.currency,
                    "confidence": req.confidence
                }
                for i, req in enumerate(evidence.requests.money_requests)
            ]
        
        if requests_summary:
            evidence_summary["requests"] = requests_summary
        
        # Behavior
        behavior_summary = {}
        
        if evidence.behavior.urgency.detected:
            behavior_summary["urgency"] = {
                "detected": True,
                "severity": evidence.behavior.urgency.severity
            }
        
        if evidence.behavior.secrecy.detected:
            behavior_summary["secrecy"] = {
                "detected": True
            }
        
        if evidence.behavior.emotional_pressure.detected:
            behavior_summary["emotional_pressure"] = {
                "detected": True,
                "pressure_types": evidence.behavior.emotional_pressure.pressure_types
            }
        
        if behavior_summary:
            evidence_summary["behavior"] = behavior_summary
        
        # Phase 2 signals
        phase2_signals = {
            "risk_score": score_breakdown.final_score,
            "risk_level": score_breakdown.risk_level.value,
            "category_scores": {
                "identity": score_breakdown.identity,
                "request": score_breakdown.request,
                "behavior": score_breakdown.behavior,
                "channel": score_breakdown.channel,
                "voice": score_breakdown.voice
            },
            "fired_rules": score_breakdown.fired_rules,
            "applied_floors": score_breakdown.applied_floors
        }
        
        return AgentEvidencePackage(
            call_id=call_id,
            evidence_summary=evidence_summary,
            trust_context=trust_context,
            phase2_signals=phase2_signals,
            evidence_quality=evidence.evidence_quality_score,
            warnings=evidence.extraction_warnings
        )
