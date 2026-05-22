"""Service for n8n integration and webhook communication."""
import logging
from typing import Any, Dict, Optional
from uuid import UUID

import httpx

from app.core.config import get_settings
from app.schemas.ticket import TicketRequest, TicketResponse, TicketStatusUpdate, TicketStatusResponse

logger = logging.getLogger(__name__)
settings = get_settings()


class N8nService:
    """Service to handle n8n webhook communication."""

    def __init__(self):
        self.webhook_url = settings.N8N_WEBHOOK_URL
        self.status_webhook_url = settings.N8N_STATUS_WEBHOOK_URL
        self.api_key = settings.N8N_API_KEY
        self.timeout = 10.0
        self.max_retries = 2

    async def send_ticket(self, ticket_request: TicketRequest) -> TicketResponse:
        """
        Send ticket creation request to n8n Triage Sidecar workflow.
        
        Args:
            ticket_request: Ticket creation request data
            
        Returns:
            TicketResponse with ticket details and status
            
        Raises:
            httpx.HTTPError: If n8n webhook fails
        """
        if not self.webhook_url:
            logger.error("N8N_WEBHOOK_URL not configured")
            return TicketResponse(
                status="error",
                message="Ticket service unavailable. N8N_WEBHOOK_URL not configured.",
                email_status="failed",
            )

        payload = {
            "user_email": ticket_request.user_email,
            "issue": ticket_request.issue,
            "category": ticket_request.category,
            "priority": ticket_request.priority,
            "source": ticket_request.source,
        }

        for attempt in range(self.max_retries):
            try:
                async with httpx.AsyncClient(timeout=self.timeout) as client:
                    logger.info(f"Sending ticket to n8n (attempt {attempt + 1}/{self.max_retries})")
                    response = await client.post(
                        self.webhook_url,
                        json=payload,
                        headers=self._get_headers(),
                    )
                    response.raise_for_status()

                    response_data = response.json()
                    logger.info(f"n8n ticket response: {response_data}")
                    return self._parse_ticket_response(response_data)

            except httpx.TimeoutException:
                logger.warning(f"Timeout on attempt {attempt + 1}/{self.max_retries}")
                if attempt == self.max_retries - 1:
                    return TicketResponse(
                        status="error",
                        message="Ticket creation timed out. Please try again.",
                        email_status="failed",
                    )
            except httpx.HTTPError as e:
                logger.error(f"HTTP error on attempt {attempt + 1}: {str(e)}")
                if attempt == self.max_retries - 1:
                    return TicketResponse(
                        status="error",
                        message="Ticket creation failed. Please contact support.",
                        email_status="failed",
                    )
            except Exception as e:
                logger.error(f"Unexpected error on attempt {attempt + 1}: {str(e)}")
                if attempt == self.max_retries - 1:
                    return TicketResponse(
                        status="error",
                        message="An unexpected error occurred.",
                        email_status="failed",
                    )

        return TicketResponse(
            status="error",
            message="Ticket creation failed after retries.",
            email_status="failed",
        )

    async def update_ticket_status(self, status_update: TicketStatusUpdate) -> TicketStatusResponse:
        """
        Send ticket status update to n8n Status Notifier workflow.
        
        Args:
            status_update: Status update request data
            
        Returns:
            TicketStatusResponse with update status
            
        Raises:
            httpx.HTTPError: If n8n webhook fails
        """
        if not self.status_webhook_url:
            logger.error("N8N_STATUS_WEBHOOK_URL not configured")
            return TicketStatusResponse(
                ticket_id=status_update.ticket_id,
                notification_status="failed",
                message="Status notifier unavailable. N8N_STATUS_WEBHOOK_URL not configured.",
            )

        payload = {
            "ticket_id": str(status_update.ticket_id),
            "user_email": status_update.user_email,
            "status": status_update.status,
        }

        for attempt in range(self.max_retries):
            try:
                async with httpx.AsyncClient(timeout=self.timeout) as client:
                    logger.info(f"Sending status update to n8n (attempt {attempt + 1}/{self.max_retries})")
                    response = await client.post(
                        self.status_webhook_url,
                        json=payload,
                        headers=self._get_headers(),
                    )
                    response.raise_for_status()

                    response_data = response.json()
                    logger.info(f"n8n status response: {response_data}")
                    return self._parse_status_response(response_data, status_update.ticket_id)

            except httpx.TimeoutException:
                logger.warning(f"Timeout on attempt {attempt + 1}/{self.max_retries}")
                if attempt == self.max_retries - 1:
                    return TicketStatusResponse(
                        ticket_id=status_update.ticket_id,
                        notification_status="failed",
                        message="Status update timed out.",
                    )
            except httpx.HTTPError as e:
                logger.error(f"HTTP error on attempt {attempt + 1}: {str(e)}")
                if attempt == self.max_retries - 1:
                    return TicketStatusResponse(
                        ticket_id=status_update.ticket_id,
                        notification_status="failed",
                        message="Status update failed.",
                    )
            except Exception as e:
                logger.error(f"Unexpected error on attempt {attempt + 1}: {str(e)}")
                if attempt == self.max_retries - 1:
                    return TicketStatusResponse(
                        ticket_id=status_update.ticket_id,
                        notification_status="failed",
                        message="An unexpected error occurred.",
                    )

        return TicketStatusResponse(
            ticket_id=status_update.ticket_id,
            notification_status="failed",
            message="Status update failed after retries.",
        )

    def _get_headers(self) -> Dict[str, str]:
        """Build request headers."""
        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        return headers

    def _parse_ticket_response(self, response_data: Dict[str, Any]) -> TicketResponse:
        """Parse n8n ticket response into TicketResponse model."""
        try:
            return TicketResponse(
                status=response_data.get("status", "success"),
                ticket_id=response_data.get("ticket_id"),
                message=response_data.get("message", "Ticket created successfully"),
                created_at=response_data.get("created_at"),
                email_status=response_data.get("email_status", "sent"),
                triage_label=response_data.get("triage_label"),
            )
        except Exception as e:
            logger.error(f"Error parsing ticket response: {str(e)}")
            return TicketResponse(
                status="error",
                message="Failed to parse response from ticket service.",
                email_status="failed",
            )

    def _parse_status_response(
        self, response_data: Dict[str, Any], ticket_id: UUID
    ) -> TicketStatusResponse:
        """Parse n8n status response into TicketStatusResponse model."""
        try:
            return TicketStatusResponse(
                status=response_data.get("status", "success"),
                ticket_id=ticket_id,
                notification_status=response_data.get("notification_status", "sent"),
                message=response_data.get("message", "Status updated successfully"),
            )
        except Exception as e:
            logger.error(f"Error parsing status response: {str(e)}")
            return TicketStatusResponse(
                ticket_id=ticket_id,
                notification_status="failed",
                message="Failed to parse response from status service.",
            )
