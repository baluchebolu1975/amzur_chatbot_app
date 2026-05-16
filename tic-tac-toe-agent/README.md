# Tic-Tac-Toe AI Agent (LiteLLM)

This scaffold is a standalone project structure for a Tic-Tac-Toe game where the opponent is an LLM-powered agent.

## Goals

- Keep game rules deterministic in backend domain logic.
- Let LLM choose the move through LiteLLM integration.
- Validate and sanitize every model output before applying the move.
- Preserve a fallback strategy when model output is invalid.

## High-Level Structure

- `backend/app/domain`: Board rules and game state evaluation.
- `backend/app/agents`: LLM prompt, parsing, and move selection.
- `backend/app/services`: Orchestration between rules and agent.
- `backend/app/api`: FastAPI routes.
- `frontend/src/pages`: Game screen.
- `frontend/src/components`: Board UI and status panels.
- `frontend/src/lib`: API client for backend route calls.

## Next Step

Implement route and UI wiring incrementally using this structure.
