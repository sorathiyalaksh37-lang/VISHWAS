"""
Database models for call recordings and analysis.
"""
from sqlalchemy import Column, String, DateTime, Text, ForeignKey, Float, Integer
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from app.database.base import Base
import uuid


class CallRecord(Base):
    """Model for call recording metadata."""
    
    __tablename__ = "call_records"
    
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
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
        return f"<CallRecord(id={self.id}, status={self.status})>"


class AnalysisReport(Base):
    """Model for analysis reports."""
    
    __tablename__ = "analysis_reports"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    call_id = Column(String(36), ForeignKey("call_records.id", ondelete="CASCADE"), nullable=False, unique=True)
    transcript_json = Column(Text, nullable=True)  # JSON string
    agent_findings_json = Column(Text, nullable=True)  # JSON string
    risk_level = Column(String(20), nullable=False)  # low, medium, high, critical
    risk_score = Column(Float, nullable=True)
    reasons_json = Column(Text, nullable=True)  # JSON string
    recommended_actions_json = Column(Text, nullable=True)  # JSON string
    warnings_json = Column(Text, nullable=True)  # JSON string
    analysis_mode = Column(String(20), nullable=False, default="mock")
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    
    # Relationship
    call = relationship("CallRecord", back_populates="report")
    
    def __repr__(self):
        return f"<AnalysisReport(call_id={self.call_id}, risk_level={self.risk_level})>"
