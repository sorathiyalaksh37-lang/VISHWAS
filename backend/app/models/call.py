"""
Database models for call recordings and analysis.
"""
from sqlalchemy import Column, String, DateTime, Text, ForeignKey, Float, Integer, LargeBinary, Boolean
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from app.database.base import Base
import uuid


class CallRecord(Base):
    """Model for call recording metadata."""

    __tablename__ = "call_records"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    owner_id = Column(String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    original_filename = Column(String(255), nullable=False)
    stored_filename = Column(String(255), nullable=False)
    storage_reference = Column(String(500), nullable=False)
    status = Column(String(20), nullable=False, default="queued")  # queued, processing, completed, failed
    analysis_mode = Column(String(20), nullable=False, default="mock")
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)
    completed_at = Column(DateTime(timezone=True), nullable=True)
    error_message = Column(Text, nullable=True)

    # Relationship
    report = relationship("AnalysisReport", back_populates="call", uselist=False, cascade="all, delete-orphan")

    def __repr__(self):
        return f"<CallRecord(id={self.id}, owner_id={self.owner_id}, status={self.status})>"


class AnalysisReport(Base):
    """Model for analysis reports."""

    __tablename__ = "analysis_reports"

    id = Column(Integer, primary_key=True, autoincrement=True)
    call_id = Column(String(36), ForeignKey("call_records.id", ondelete="CASCADE"), nullable=False, unique=True)
    transcript_json = Column(Text, nullable=True)          # ASRResult JSON
    voice_json = Column(Text, nullable=True)               # VoiceEvidence JSON (M2 v3)
    agent_findings_json = Column(Text, nullable=True)      # Evidence layer JSON
    risk_level = Column(String(20), nullable=False)        # low, medium, high, critical
    risk_score = Column(Float, nullable=True)
    reasons_json = Column(Text, nullable=True)
    recommended_actions_json = Column(Text, nullable=True)
    warnings_json = Column(Text, nullable=True)
    analysis_mode = Column(String(20), nullable=False, default="mock")
    # v3 Trust Engine fields (Phase 5 audit)
    category_scores_json = Column(Text, nullable=True)     # CategoryScores JSON
    fired_rules_json = Column(Text, nullable=True)          # List[str] of rule IDs
    verification_json = Column(Text, nullable=True)         # Verification JSON
    killchain_stage = Column(String(50), nullable=True)     # Kill-chain stage name
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    # Relationship
    call = relationship("CallRecord", back_populates="report")

    def __repr__(self):
        return f"<AnalysisReport(call_id={self.call_id}, risk_level={self.risk_level})>"


class Contact(Base):
    """
    Trusted contact for the Trust Graph.
    Stores speaker embedding bytes only — NOT raw audio (privacy-first §9).
    """

    __tablename__ = "contacts"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    owner_id = Column(String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    name = Column(String(100), nullable=False)
    relation = Column(String(50), nullable=True)           # e.g. mother, bank
    saved_numbers = Column(Text, nullable=True)            # JSON list of phone numbers
    safe_word_hash = Column(String(64), nullable=True)     # sha256 of safe word
    typical_call_hours_start = Column(Integer, nullable=True, default=8)
    typical_call_hours_end = Column(Integer, nullable=True, default=22)
    typical_amount = Column(Float, nullable=True)
    # Voiceprint: stored as numpy float32 bytes — never raw audio
    voiceprint_embedding = Column(LargeBinary, nullable=True)
    voiceprint_model = Column(String(100), nullable=True)
    voiceprint_enrolled_at = Column(DateTime(timezone=True), nullable=True)
    # Trust level: 'high' (trusted), 'medium' (suspicious), 'low' (flagged/compromised)
    trust_level = Column(String(20), nullable=False, default='high')
    trust_flagged_by_call_id = Column(String(36), nullable=True)  # which analysis caused demotion
    trust_flagged_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    def __repr__(self):
        return f"<Contact(id={self.id}, owner_id={self.owner_id}, name={self.name}, relation={self.relation})>"
