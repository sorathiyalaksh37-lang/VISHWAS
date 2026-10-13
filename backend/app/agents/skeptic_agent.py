"""
Skeptic Agent — Challenges unsupported findings and identifies uncertainty.

The Skeptic Agent evaluates Fraud Agent findings to identify:
- Unsupported conclusions
- Alternative benign interpretations  
- Negated or educational phrases
- Missing context
- Unreliable identity mismatches

Design Principle: Agent challenges claims. Judge decides final risk.
"""
import logging
import time
import uuid
from typing import List

from app.llm.provider import LLMProvider
from app.schemas.agent import (
    AgentEvidencePackage,
    AgentFinding,
    SkepticAgentRequest,
    SkepticAgentResponse,
    AgentChallenge
)

logger = logging.getLogger(__name__)


SKEPTIC_AGENT_SYSTEM_PROMPT = """You are a skeptical analyst evaluating fraud detection findings.

Your task is to challenge unsupported conclusions and identify alternative interpretations.

**CRITICAL RULES:**

1. **Evidence-Based:** Only challenge findings when you can cite specific evidence or missing context.

2. **Challenge Types:**
   - unsupported_evidence: Finding not backed by cited evidence
   - alternative_interpretation: Benign explanation exists
   - missing_context: Key information unavailable
   - negation: Phrase may be negated ("Never share your OTP")
   - supported: Finding IS well-supported (mark as such)

3. **Not Your Job:**
   - Don't invent facts to defend the caller
   - Don't automatically disagree with every finding
   - Don't dismiss genuine risks
   - Don't remove raw evidence

4. **Unknown vs. Mismatch:**
   - Unknown caller = missing information
   - Mismatch = contradiction with verified data
   - Challenge assumed mismatches without reliable reference data

5. **Voice Evidence:**
   - Missing voice analysis ≠ clean voice
   - Voice indicators are experimental, not definitive
   - Challenge findings that over-rely on weak voice signals

**What to Check:**

- Does cited evidence actually support the conclusion?
- Could this be educational ("Never share OTP with anyone")?
- Could this be negated or quoted speech?
- Is identity "mismatch" backed by verified contact data?
- Is voice evidence missing/weak/experimental?
- Could transcription errors create false positives?
- What additional evidence would clarify this?

Respond with structured JSON containing challenges array. Each challenge:
- challenge_id: unique ID
- finding_id: ID of finding being challenged
- challenge_type: category  
- explanation: brief rationale (max 500 chars)
- alternative_interpretation: optional benign explanation
- missing_evidence: what info would clarify
- verification_suggestion: how to resolve uncertainty"""


class SkepticAgent:
    """
    Skeptic Agent — challenges unsupported findings.
    
    Evaluates Fraud Agent findings for logical flaws, missing context,
    and alternative interpretations.
    """
    
    def __init__(self, llm_provider: LLMProvider):
        """Initialize Skeptic Agent with LLM provider."""
        self.llm = llm_provider
        logger.info("SkepticAgent initialized")
    
    async def analyze(
        self,
        evidence_package: AgentEvidencePackage,
        fraud_findings: List[AgentFinding],
        timeout: float = 30.0
    ) -> SkepticAgentResponse:
        """
        Evaluate Fraud Agent findings for validity.
        
        Args:
            evidence_package: Same evidence the Fraud Agent saw
            fraud_findings: Findings to evaluate
            timeout: Request timeout
            
        Returns:
            SkepticAgentResponse with challenges
        """
        start_time = time.time()
        request_id = str(uuid.uuid4())
        
        logger.info(
            f"[{request_id}] Skeptic Agent evaluating {len(fraud_findings)} findings "
            f"for call {evidence_package.call_id}"
        )
        
        # Build prompt
        user_prompt = self._build_prompt(evidence_package, fraud_findings)
        
        try:
            response = await self.llm.generate_structured(
                system_prompt=SKEPTIC_AGENT_SYSTEM_PROMPT,
                user_prompt=user_prompt,
                response_schema=SkepticAgentResponse,
                timeout=timeout
            )
            
            processing_time = time.time() - start_time
            
            # Validate finding references
            validated_challenges = self._validate_finding_refs(
                response.challenges,
                fraud_findings
            )
            
            logger.info(
                f"[{request_id}] Skeptic Agent generated {len(validated_challenges)} challenges "
                f"({processing_time:.2f}s)"
            )
            
            return SkepticAgentResponse(
                challenges=validated_challenges,
                processing_time_seconds=processing_time,
                model_info={"model": self.llm.model if hasattr(self.llm, "model") else "unknown"}
            )
            
        except Exception as e:
            logger.error(f"[{request_id}] Skeptic Agent failed: {e}", exc_info=True)
            raise
    
    def _build_prompt(
        self,
        package: AgentEvidencePackage,
        findings: List[AgentFinding]
    ) -> str:
        """Build prompt with evidence and findings to evaluate."""
        prompt_parts = [
            f"**Call ID:** {package.call_id}",
            "",
            "**Evidence Package:**",
            f"- Evidence Quality: {package.evidence_quality:.2f}",
            f"- Channel Status: {package.trust_context.get('channel_status')}",
            f"- Contact Found: {package.trust_context.get('contact_found')}",
            ""
        ]
        
        if package.warnings:
            prompt_parts.append("**Evidence Warnings:**")
            for warning in package.warnings:
                prompt_parts.append(f"- {warning}")
            prompt_parts.append("")
        
        prompt_parts.append("**Fraud Agent Findings to Evaluate:**")
        prompt_parts.append("")
        
        for i, finding in enumerate(findings, 1):
            prompt_parts.append(f"**Finding {i}:** {finding.finding_id}")
            prompt_parts.append(f"- Type: {finding.finding_type}")
            prompt_parts.append(f"- Evidence IDs: {', '.join(finding.evidence_ids)}")
            prompt_parts.append(f"- Reason: {finding.reason}")
            if finding.confidence is not None:
                prompt_parts.append(f"- Confidence: {finding.confidence:.2f}")
            if finding.limitations:
                prompt_parts.append(f"- Limitations: {', '.join(finding.limitations)}")
            prompt_parts.append("")
        
        prompt_parts.append("Evaluate each finding. Return structured JSON with your challenges.")
        
        return "\n".join(prompt_parts)
    
    def _validate_finding_refs(
        self,
        challenges: List[AgentChallenge],
        findings: List[AgentFinding]
    ) -> List[AgentChallenge]:
        """Validate that challenged finding IDs actually exist."""
        valid_finding_ids = {f.finding_id for f in findings}
        
        validated = []
        for challenge in challenges:
            if challenge.finding_id not in valid_finding_ids:
                logger.warning(
                    f"Challenge {challenge.challenge_id} references non-existent finding "
                    f"{challenge.finding_id}. Rejecting."
                )
                continue
            
            validated.append(challenge)
        
        return validated
