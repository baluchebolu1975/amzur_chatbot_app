"""Pydantic models for ticket management."""
from datetime import datetime
from typing import Literal, Optional
from uuid import UUID

from pydantic import BaseModel, EmailStr, Field


class TicketRequest(BaseModel):
    """Request model for creating a ticket."""

    user_email: EmailStr = Field(..., description="User email address")
    issue: str = Field(..., min_length=10, max_length=2000, description="Issue description")
    category: Literal["billing", "technical", "account", "general"] = Field(
        default="general", description="Ticket category"
    )
    priority: Literal["low", "medium", "high", "urgent"] = Field(
        default="medium", description="Ticket priority"
    )
    source: str = Field(default="chatbot", description="Source of the ticket")


class TicketResponse(BaseModel):
    """Response model for ticket creation."""

    status: Literal["success", "error"] = Field(default="success", description="Operation status")
    ticket_id: Optional[UUID] = Field(default=None, description="Generated ticket ID")
    message: str = Field(..., description="Response message")
    created_at: Optional[datetime] = Field(default=None, description="Ticket creation timestamp")
    email_status: Literal["sent", "failed", "pending"] = Field(
        default="pending", description="Email confirmation status"
    )
    triage_label: Optional[str] = Field(default=None, description="AI-generated triage label")


class TicketListItem(BaseModel):
    """Response model for listing tickets in UI."""

    id: UUID = Field(..., description="Ticket ID")
    user_email: EmailStr = Field(..., description="User email address")
    issue: str = Field(..., description="Issue description")
    category: Literal["billing", "technical", "account", "general"] = Field(
        ..., description="Ticket category"
    )
    priority: Literal["low", "medium", "high", "urgent"] = Field(
        ..., description="Ticket priority"
    )
    status: Literal["Open", "In Progress", "Resolved", "Closed"] = Field(
        ..., description="Ticket status"
    )
    created_at: datetime = Field(..., description="Ticket creation timestamp")
    triage_label: Optional[str] = Field(default=None, description="AI-generated triage label")


class TicketStatusUpdate(BaseModel):
    """Request model for updating ticket status."""

    ticket_id: UUID = Field(..., description="Ticket ID to update")
    status: Literal["Open", "In Progress", "Resolved", "Closed"] = Field(
        ..., description="New ticket status"
    )
    user_email: EmailStr = Field(..., description="User email for notification")


class TicketStatusResponse(BaseModel):
    """Response model for status update."""

    status: Literal["success", "error"] = Field(default="success", description="Operation status")
    ticket_id: UUID = Field(..., description="Ticket ID")
    notification_status: Literal["sent", "failed", "pending"] = Field(
        default="pending", description="Notification email status"
    )
    message: str = Field(..., description="Response message")


class ErrorResponse(BaseModel):
    """Standard error response model."""

    detail: str = Field(..., description="Error detail message")
    error_code: str = Field(..., description="Error code for categorization")
