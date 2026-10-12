"""
Pydantic schemas for call-related endpoints.
"""
from pydantic import BaseModel, Field
from datetime import datetime
from typing import Optional, List


class HealthResponse(BaseModel):
    """Health check response."""
    status: str = Field(..., description="Service status")
    service: str = Field(..., description="Service name")
    version: str = Field(..., description="API version")


class UploadResponse(BaseModel):
    """Response for successful upload."""
    call_id: str = Field(..., description="UUID for the uploaded call")
    status: str = Field(..., description="Initial processing status")
    message: str = Field(..., description="Human-readable confirmation")
    analysis_mode: str = Field(..., description="Analysis mode (mock or real)")


class CallStatusResponse(BaseModel):
    """Response for call status check."""
    call_id: str = Field(..., description="Call UUID")
    status: str = Field(..., description="Current processing status")
    created_at: datetime = Field(..., description="Creation timestamp")
    updated_at: datetime = Field(..., description="Last update timestamp")
    completed_at: Optional[datetime] = Field(None, description="Completion timestamp")
    error_message: Optional[str] = Field(None, description="Error message if failed")


class CallListItem(BaseModel):
    """Individual call item in list response."""
    call_id: str = Field(..., description="Call UUID")
    original_filename: str = Field(..., description="Original uploaded filename")
    status: str = Field(..., description="Current processing status")
    created_at: datetime = Field(..., description="Creation timestamp")
    updated_at: datetime = Field(..., description="Last update timestamp")


class PaginationInfo(BaseModel):
    """Pagination metadata."""
    page: int = Field(..., description="Current page number")
    page_size: int = Field(..., description="Items per page")
    total: int = Field(..., description="Total number of items")
    pages: int = Field(..., description="Total number of pages")


class CallListResponse(BaseModel):
    """Response for listing calls."""
    calls: List[CallListItem] = Field(..., description="List of calls")
    pagination: PaginationInfo = Field(..., description="Pagination information")
