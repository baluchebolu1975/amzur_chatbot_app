import random
import string
import sys
from typing import List

import requests

BASE = "http://127.0.0.1:8001/api"
s = requests.Session()


def assert_true(condition: bool, message: str):
    if not condition:
        raise AssertionError(message)


def game_status(board: List[str]):
    lines = (
        (0, 1, 2), (3, 4, 5), (6, 7, 8),
        (0, 3, 6), (1, 4, 7), (2, 5, 8),
        (0, 4, 8), (2, 4, 6),
    )
    for a, b, c in lines:
        mark = board[a]
        if mark and mark == board[b] == board[c]:
            return "won", mark
    if "" not in board:
        return "draw", None
    return "in_progress", None


# 1) Health
r = s.get(f"{BASE}/health", timeout=15)
assert_true(r.status_code == 200, f"Health failed: {r.status_code} {r.text}")

# 2) Unauthorized tictactoe should be 401
unauth_payload = {"board": ["X", "", "", "", "", "", "", "", ""], "player_symbol": "X", "ai_symbol": "O"}
r = requests.post(f"{BASE}/tictactoe/move", json=unauth_payload, timeout=15)
assert_true(r.status_code == 401, f"Expected 401 for unauth move, got {r.status_code}: {r.text}")

# 3) Register+login isolated random user
suffix = "".join(random.choices(string.ascii_lowercase + string.digits, k=10))
email = f"ttt_smoke_{suffix}@example.com"
password = "SmokePass123!"

rr = s.post(
    f"{BASE}/auth/register",
    json={"email": email, "password": password, "full_name": "TicTacToe Smoke"},
    timeout=20,
)
assert_true(rr.status_code in (200, 201), f"Register failed: {rr.status_code} {rr.text}")

rl = s.post(f"{BASE}/auth/login", json={"email": email, "password": password}, timeout=20)
assert_true(rl.status_code == 200, f"Login failed: {rl.status_code} {rl.text}")

# 4) Authenticated repeated gameplay smoke
llm_moves = 0
fallback_moves = 0
completed_games = 0
requests_ok = 0

for _ in range(15):
    board = ["", "", "", "", "", "", "", "", ""]
    while True:
        status, winner = game_status(board)
        if status != "in_progress":
            completed_games += 1
            break

        legal = [i for i, cell in enumerate(board) if cell == ""]
        player_move = random.choice(legal)
        board[player_move] = "X"

        status, winner = game_status(board)
        if status != "in_progress":
            completed_games += 1
            break

        payload = {"board": board, "player_symbol": "X", "ai_symbol": "O"}
        resp = s.post(f"{BASE}/tictactoe/move", json=payload, timeout=30)
        assert_true(resp.status_code == 200, f"Move failed: {resp.status_code} {resp.text}")
        data = resp.json()

        # Schema checks
        assert_true(isinstance(data.get("board"), list) and len(data["board"]) == 9, "Invalid board in response")
        assert_true(data.get("move_source") in ("llm", "fallback"), f"Invalid move_source: {data.get('move_source')}")
        assert_true(isinstance(data.get("ai_move"), int), "ai_move is not int")
        assert_true(0 <= data["ai_move"] <= 8, "ai_move out of range")

        # Behavioral checks
        assert_true(data["board"][data["ai_move"]] == "O", "AI move not applied as O")
        assert_true(sum(1 for c in data["board"] if c == "O") == sum(1 for c in board if c == "O") + 1, "O count did not increment by 1")

        board = data["board"]
        requests_ok += 1
        if data["move_source"] == "llm":
            llm_moves += 1
        else:
            fallback_moves += 1

# 5) Invalid board must be rejected
invalid = {
    "board": ["X", "X", "X", "", "", "", "", "", ""],
    "player_symbol": "X",
    "ai_symbol": "O",
}
r_bad = s.post(f"{BASE}/tictactoe/move", json=invalid, timeout=20)
assert_true(r_bad.status_code == 400, f"Expected 400 for finished game, got {r_bad.status_code}: {r_bad.text}")

print("SMOKE_RESULT=PASS")
print(f"GAMES_COMPLETED={completed_games}")
print(f"MOVE_REQUESTS_OK={requests_ok}")
print(f"LLM_MOVES={llm_moves}")
print(f"FALLBACK_MOVES={fallback_moves}")
