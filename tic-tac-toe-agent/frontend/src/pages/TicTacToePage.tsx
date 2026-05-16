import { useState } from "react";

import Board from "../components/Board";
import { requestAiMove } from "../lib/api";
import type { GameStatus, TicTacToeCell } from "../types/game";

const EMPTY_BOARD: TicTacToeCell[] = ["", "", "", "", "", "", "", "", ""];

export default function TicTacToePage() {
  const [board, setBoard] = useState<TicTacToeCell[]>(EMPTY_BOARD);
  const [status, setStatus] = useState<GameStatus>("in_progress");
  const [winner, setWinner] = useState<"X" | "O" | null>(null);
  const [reason, setReason] = useState(
    "AI agent will choose a move after you play.",
  );
  const [isThinking, setIsThinking] = useState(false);

  const reset = () => {
    setBoard([...EMPTY_BOARD]);
    setStatus("in_progress");
    setWinner(null);
    setReason("AI agent will choose a move after you play.");
    setIsThinking(false);
  };

  const onSelect = async (index: number) => {
    if (isThinking || status !== "in_progress" || board[index] !== "") {
      return;
    }

    const nextBoard = [...board];
    nextBoard[index] = "X";
    setBoard(nextBoard);
    setIsThinking(true);
    setReason("AI agent is thinking...");

    try {
      const response = await requestAiMove(nextBoard, "X", "O");
      setBoard(response.board);
      setStatus(response.status);
      setWinner(response.winner);
      setReason(`${response.ai_reasoning} (source: ${response.move_source})`);
    } catch {
      setReason("Failed to get AI move from backend.");
    } finally {
      setIsThinking(false);
    }
  };

  return (
    <main style={{ padding: 20, fontFamily: "Segoe UI, sans-serif" }}>
      <h1>Tic-Tac-Toe AI Agent</h1>
      <p>
        Status: {status}
        {winner ? ` | Winner: ${winner}` : ""}
      </p>
      <Board
        board={board}
        disabled={isThinking || status !== "in_progress"}
        onSelect={onSelect}
      />
      <p style={{ marginTop: 12 }}>{reason}</p>
      <button onClick={reset}>New Game</button>
    </main>
  );
}
