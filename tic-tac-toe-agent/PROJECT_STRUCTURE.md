# Tic-Tac-Toe AI Agent Structure

## Analysis From Current App

- Existing app already separates API route, schema, and service layers.
- Existing Tic-Tac-Toe flow already supports LLM move generation with fallback.
- Existing frontend already has route + page + API client pattern.

## Recommended Standalone Layout

```text
tic-tac-toe-agent/
  backend/
    app/
      ai/
        litellm_client.py
      agents/
        tictactoe_llm_agent.py
      api/
        router.py
        routes/
          game.py
      core/
        config.py
      domain/
        game_engine.py
      schemas/
        game.py
      services/
        game_service.py
      main.py
    requirements.txt
    .env.example
  frontend/
    src/
      components/
        Board.tsx
      lib/
        api.ts
      pages/
        TicTacToePage.tsx
      types/
        game.ts
      App.tsx
      main.tsx
    package.json
  README.md
```

## Why This Works

- Domain is deterministic and testable.
- Agent module is isolated for prompt and parser iteration.
- Service layer enforces safe move application.
- Route stays thin and validates request/response boundaries.
- Frontend remains simple and API-driven.
