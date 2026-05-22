"""Integration tests for ticket endpoints."""
import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from uuid import UUID, uuid4

from app.schemas.ticket import (
    TicketRequest,
    TicketResponse,
    TicketStatusUpdate,
    TicketStatusResponse,
)
from app.services.n8n_service import N8nService


@pytest.fixture
def ticket_request():
    """Sample ticket request."""
    return TicketRequest(
        user_email="test@example.com",
        issue="I cannot log into my account after password reset",
        category="account",
        priority="high",
        source="chatbot",
    )


@pytest.fixture
def ticket_response():
    """Sample ticket response."""
    return {
        "status": "success",
        "ticket_id": str(uuid4()),
        "message": "Ticket created successfully",
        "created_at": "2026-05-22T10:30:00Z",
        "email_status": "sent",
        "triage_label": "account_recovery",
    }


@pytest.fixture
def n8n_service():
    """N8n service instance."""
    return N8nService()


@pytest.mark.asyncio
async def test_send_ticket_success(n8n_service, ticket_request, ticket_response):
    """Test successful ticket creation."""
    with patch("app.services.n8n_service.httpx.AsyncClient") as mock_client:
        mock_response = MagicMock()
        mock_response.json.return_value = ticket_response
        mock_response.raise_for_status.return_value = None

        mock_client.return_value.__aenter__.return_value.post = AsyncMock(
            return_value=mock_response
        )

        result = await n8n_service.send_ticket(ticket_request)

        assert result.status == "success"
        assert result.ticket_id is not None
        assert result.email_status == "sent"


@pytest.mark.asyncio
async def test_send_ticket_timeout(n8n_service, ticket_request):
    """Test ticket creation timeout and retry."""
    import httpx

    with patch("app.services.n8n_service.httpx.AsyncClient") as mock_client:
        mock_client.return_value.__aenter__.return_value.post = AsyncMock(
            side_effect=httpx.TimeoutException("Timeout")
        )

        result = await n8n_service.send_ticket(ticket_request)

        assert result.status == "error"
        assert "timed out" in result.message.lower()


@pytest.mark.asyncio
async def test_send_ticket_no_webhook_url(ticket_request):
    """Test ticket creation when webhook URL not configured."""
    service = N8nService()
    service.webhook_url = None

    result = await service.send_ticket(ticket_request)

    assert result.status == "error"
    assert "not configured" in result.message.lower()


@pytest.mark.asyncio
async def test_update_ticket_status_success(n8n_service):
    """Test successful ticket status update."""
    ticket_id = uuid4()
    status_update = TicketStatusUpdate(
        ticket_id=ticket_id,
        status="In Progress",
        user_email="test@example.com",
    )

    status_response = {
        "status": "success",
        "ticket_id": str(ticket_id),
        "notification_status": "sent",
        "message": "Status updated successfully",
    }

    with patch("app.services.n8n_service.httpx.AsyncClient") as mock_client:
        mock_response = MagicMock()
        mock_response.json.return_value = status_response
        mock_response.raise_for_status.return_value = None

        mock_client.return_value.__aenter__.return_value.post = AsyncMock(
            return_value=mock_response
        )

        result = await n8n_service.update_ticket_status(status_update)

        assert result.status == "success"
        assert result.notification_status == "sent"


@pytest.mark.asyncio
async def test_update_ticket_status_no_webhook_url():
    """Test status update when webhook URL not configured."""
    service = N8nService()
    service.status_webhook_url = None

    ticket_id = uuid4()
    status_update = TicketStatusUpdate(
        ticket_id=ticket_id,
        status="Resolved",
        user_email="test@example.com",
    )

    result = await service.update_ticket_status(status_update)

    assert result.status == "error"
    assert "not configured" in result.message.lower()


def test_parse_ticket_response_success(n8n_service, ticket_response):
    """Test parsing valid ticket response."""
    result = n8n_service._parse_ticket_response(ticket_response)

    assert result.status == "success"
    assert result.ticket_id is not None
    assert result.triage_label == "account_recovery"


def test_parse_ticket_response_invalid_data(n8n_service):
    """Test parsing invalid ticket response."""
    result = n8n_service._parse_ticket_response({"invalid": "data"})

    assert result.status == "error"
    assert "parse" in result.message.lower()


def test_parse_status_response_success(n8n_service):
    """Test parsing valid status response."""
    ticket_id = uuid4()
    response_data = {
        "status": "success",
        "ticket_id": str(ticket_id),
        "notification_status": "sent",
        "message": "Status updated",
    }

    result = n8n_service._parse_status_response(response_data, ticket_id)

    assert result.status == "success"
    assert result.notification_status == "sent"


def test_get_headers_with_api_key(n8n_service):
    """Test header generation with API key."""
    n8n_service.api_key = "test-key"
    headers = n8n_service._get_headers()

    assert "Authorization" in headers
    assert headers["Authorization"] == "Bearer test-key"
    assert headers["Content-Type"] == "application/json"


def test_get_headers_without_api_key(n8n_service):
    """Test header generation without API key."""
    n8n_service.api_key = None
    headers = n8n_service._get_headers()

    assert "Authorization" not in headers
    assert headers["Content-Type"] == "application/json"
