"""Routes for ticket management."""
import logging
import uuid as uuid_lib
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.schemas.ticket import (
    TicketRequest,
    TicketResponse,
    TicketListItem,
    TicketStatusUpdate,
    TicketStatusResponse,
    ErrorResponse,
)
from app.api.deps import get_db
from app.services.n8n_service import N8nService

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/tickets", tags=["tickets"])
n8n_service = N8nService()


@router.post(
    "",
    response_model=TicketResponse,
    status_code=status.HTTP_201_CREATED,
    responses={400: {"model": ErrorResponse}, 502: {"model": ErrorResponse}},
)
async def create_ticket(ticket_request: TicketRequest, db: AsyncSession = Depends(get_db)) -> TicketResponse:
    """
    Create a new ticket via n8n Triage Sidecar.
    
    This endpoint validates the ticket request and forwards it to the n8n
    ticket triage workflow. The workflow will:
    1. Normalize the payload
    2. Triage the issue using AI
    3. Insert into Supabase
    4. Send confirmation email
    
    Args:
        ticket_request: Ticket creation request
        
    Returns:
        TicketResponse with ticket details
        
    Raises:
        HTTPException: 400 for validation errors, 502 for n8n failures
    """
    logger.info(f"Creating ticket for {ticket_request.user_email}: {ticket_request.issue[:50]}")

    # Validate request
    if not ticket_request.user_email:
        logger.warning("Missing user_email in ticket request")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="user_email is required",
        )

    if len(ticket_request.issue) < 10:
        logger.warning(f"Issue too short: {len(ticket_request.issue)} chars")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Issue description must be at least 10 characters",
        )

    # Attempt n8n triage workflow
    response = await n8n_service.send_ticket(ticket_request)

    if response.status != "error":
        logger.info(f"Ticket created via n8n: {response.ticket_id}")
        return response

    # n8n failed/timed out — write directly to DB so the user never sees a 502
    logger.warning(f"n8n unavailable ({response.message}); writing ticket directly to DB")

    ticket_id_text = f"TKT-{str(uuid_lib.uuid4())[:8].upper()}"
    result = await db.execute(
        text(
            """
            INSERT INTO public.tickets (ticket_id, user_email, issue, category, priority, status)
            VALUES (:ticket_id, :user_email, :issue, :category, :priority, 'open')
            RETURNING id, created_at
            """
        ),
        {
            "ticket_id": ticket_id_text,
            "user_email": ticket_request.user_email,
            "issue": ticket_request.issue,
            "category": ticket_request.category.capitalize(),
            "priority": ticket_request.priority,
        },
    )
    await db.commit()
    row = result.mappings().first()

    logger.info(f"Ticket written directly to DB: {ticket_id_text} (id={row['id']})")
    return TicketResponse(
        status="success",
        ticket_id=row["id"],
        message="Ticket received. AI triage will process shortly.",
        created_at=row["created_at"],
        email_status="pending",
    )


@router.get("", response_model=list[TicketListItem], status_code=status.HTTP_200_OK)
async def list_tickets(
    db: AsyncSession = Depends(get_db),
) -> list[TicketListItem]:
    """
    List all tickets for all users.

    Returns:
        List of TicketListItem objects
    """
    logger.info("Listing all tickets")

    result = await db.execute(
        text(
            """
            SELECT
                id,
                user_email,
                issue,
                category,
                priority,
                status,
                created_at,
                triage_label
            FROM public.tickets
            ORDER BY created_at DESC
            """
        )
    )

    rows = result.mappings().all()

    category_map = {
        "billing": "billing",
        "technical": "technical",
        "account": "account",
        "general": "general",
    }
    priority_map = {
        "low": "low",
        "medium": "medium",
        "high": "high",
        "urgent": "urgent",
    }
    status_map = {
        "open": "Open",
        "in progress": "In Progress",
        "in_progress": "In Progress",
        "resolved": "Resolved",
        "closed": "Closed",
    }

    tickets: list[TicketListItem] = []
    for row in rows:
        category = category_map.get(str(row.get("category", "general")).strip().lower(), "general")
        priority = priority_map.get(str(row.get("priority", "medium")).strip().lower(), "medium")
        normalized_status = status_map.get(str(row.get("status", "Open")).strip().lower(), "Open")

        tickets.append(
            TicketListItem(
                id=row["id"],
                user_email=row["user_email"],
                issue=row["issue"],
                category=category,
                priority=priority,
                status=normalized_status,
                created_at=row["created_at"],
                triage_label=row.get("triage_label"),
            )
        )

    return tickets


@router.put(
    "/{ticket_id}/status",
    response_model=TicketStatusResponse,
    status_code=status.HTTP_200_OK,
    responses={400: {"model": ErrorResponse}, 404: {"model": ErrorResponse}, 502: {"model": ErrorResponse}},
)
async def update_ticket_status(
    ticket_id: UUID, status_update: TicketStatusUpdate
) -> TicketStatusResponse:
    """
    Update ticket status and send notification email.
    
    This endpoint forwards the status update to the n8n Status Notifier workflow.
    The workflow will:
    1. Receive the webhook
    2. Send status notification email
    3. Return confirmation
    
    Args:
        ticket_id: UUID of the ticket to update
        status_update: Status update details
        
    Returns:
        TicketStatusResponse with update confirmation
        
    Raises:
        HTTPException: 400 for validation, 404 if not found, 502 for n8n failures
    """
    logger.info(f"Updating ticket {ticket_id} status to {status_update.status}")

    # Validate request
    if not ticket_id:
        logger.warning("Missing ticket_id")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="ticket_id is required",
        )

    if not status_update.user_email:
        logger.warning("Missing user_email in status update")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="user_email is required",
        )

    # Update ticket_id from URL param
    status_update.ticket_id = ticket_id

    # Send to n8n
    response = await n8n_service.update_ticket_status(status_update)

    if response.status == "error":
        logger.error(f"n8n status update failed: {response.message}")
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=response.message,
        )

    logger.info(f"Ticket status updated successfully: {ticket_id}")
    return response
