import { isAxiosError } from "axios";
import { useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";

import {
  requestTicTacToeAiMove,
  type TicTacToeCell,
  type TicTacToeMoveResponse,
} from "../lib/api";

const WIN_LINES: ReadonlyArray<ReadonlyArray<number>> = [
  [0, 1, 2],
  [3, 4, 5],
  [6, 7, 8],
  [0, 3, 6],
  [1, 4, 7],
  [2, 5, 8],
  [0, 4, 8],
  [2, 4, 6],
];
const BOARD_KEYS = [
  "cell-0",
  "cell-1",
  "cell-2",
  "cell-3",
  "cell-4",
  "cell-5",
  "cell-6",
  "cell-7",
  "cell-8",
] as const;

const EMPTY_BOARD: TicTacToeCell[] = ["", "", "", "", "", "", "", "", ""];

type GameStatus = "in_progress" | "won" | "draw";
type GameWinner = "X" | "O" | null;

function evaluateBoard(board: TicTacToeCell[]): {
  status: GameStatus;
  winner: GameWinner;
} {
  for (const [a, b, c] of WIN_LINES) {
    const marker = board[a];
    if (marker && marker === board[b] && marker === board[c]) {
      return { status: "won", winner: marker };
    }
  }

  if (board.every((cell) => cell !== "")) {
    return { status: "draw", winner: null };
  }

  return { status: "in_progress", winner: null };
}

function statusText(status: GameStatus, winner: GameWinner): string {
  if (status === "won" && winner === "X") {
    return "You won this round.";
  }

  if (status === "won" && winner === "O") {
    return "AI Agent won this round.";
  }

  if (status === "draw") {
    return "Draw game.";
  }

  return "Your turn. Play X.";
}

function getRequestErrorMessage(error: unknown): string {
  if (isAxiosError(error)) {
    const detail = error.response?.data?.detail;

    if (typeof detail === "string" && detail.trim()) {
      return detail;
    }

    if (
      detail &&
      typeof detail === "object" &&
      "message" in detail &&
      typeof detail.message === "string" &&
      detail.message.trim()
    ) {
      return detail.message;
    }

    if (error.code === "ERR_NETWORK") {
      return "Backend is unreachable. Start the API server and try again.";
    }

    if (error.response?.status === 401) {
      return "Your session expired. Log in again and retry the move.";
    }

    if (error.response?.status) {
      return `AI move request failed with status ${error.response.status}.`;
    }
  }

  if (error instanceof Error && error.message.trim()) {
    return error.message;
  }

  return "Failed to get AI move.";
}

export default function TicTacToePage() {
  const navigate = useNavigate();
  const [board, setBoard] = useState<TicTacToeCell[]>(EMPTY_BOARD);
  const [status, setStatus] = useState<GameStatus>("in_progress");
  const [winner, setWinner] = useState<GameWinner>(null);
  const [aiReasoning, setAiReasoning] = useState(
    "The AI agent will reason over your board after your move.",
  );
  const [moveSource, setMoveSource] = useState<"llm" | "fallback" | null>(null);
  const [isThinking, setIsThinking] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const boardDisabled = status !== "in_progress" || isThinking;

  const headline = useMemo(() => statusText(status, winner), [status, winner]);

  const resetGame = () => {
    setBoard([...EMPTY_BOARD]);
    setStatus("in_progress");
    setWinner(null);
    setAiReasoning("The AI agent will reason over your board after your move.");
    setMoveSource(null);
    setError(null);
    setIsThinking(false);
  };

  const handleCellClick = async (index: number) => {
    if (boardDisabled || board[index] !== "") {
      return;
    }

    setError(null);

    const playerBoard = [...board];
    playerBoard[index] = "X";
    setBoard(playerBoard);

    const afterPlayer = evaluateBoard(playerBoard);
    if (afterPlayer.status !== "in_progress") {
      setStatus(afterPlayer.status);
      setWinner(afterPlayer.winner);
      setAiReasoning("Round ended before AI turn.");
      setMoveSource(null);
      return;
    }

    setIsThinking(true);
    setAiReasoning("AI agent is analyzing the board and choosing a move...");

    try {
      const response: TicTacToeMoveResponse = await requestTicTacToeAiMove(
        playerBoard,
        "X",
        "O",
      );

      setBoard(response.board);
      setStatus(response.status);
      setWinner(response.winner);
      setAiReasoning(response.ai_reasoning);
      setMoveSource(response.move_source);
    } catch (requestError) {
      const message = getRequestErrorMessage(requestError);
      setError(message);
      setAiReasoning(`Unable to complete AI move. Failure case: ${message}`);
    } finally {
      setIsThinking(false);
    }
  };

  return (
    <main className="min-h-screen px-4 py-6 md:px-8">
      <section className="mx-auto flex w-full max-w-5xl flex-col gap-6">
        <header className="glass-effect slide-down rounded-2xl px-5 py-4 md:px-6">
          <div className="flex flex-wrap items-center justify-between gap-3">
            <div>
              <h1 className="text-2xl font-extrabold tracking-tight text-slate-900">
                Tic Tac Toe Agent Arena
              </h1>
              <p className="text-sm text-slate-600">
                You are X. The opponent is an LLM-powered agent via LiteLLM.
              </p>
            </div>
            <div className="flex items-center gap-2">
              <button
                onClick={() => navigate("/chat")}
                className="rounded-lg border border-slate-300 bg-white px-4 py-2 text-sm font-semibold text-slate-700 hover:bg-slate-50"
              >
                Back to Chat
              </button>
              <button
                onClick={resetGame}
                className="rounded-lg bg-gradient-to-r from-cyan-500 to-blue-600 px-4 py-2 text-sm font-semibold text-white shadow-md shadow-blue-500/30 hover:brightness-105"
              >
                New Game
              </button>
            </div>
          </div>
        </header>

        <div className="grid gap-6 lg:grid-cols-[minmax(320px,360px)_1fr]">
          <article className="glass-effect slide-up rounded-2xl p-5">
            <div className="mb-4 flex items-center justify-between">
              <h2 className="text-sm font-bold uppercase tracking-wide text-slate-500">
                Board
              </h2>
              {isThinking ? (
                <span className="rounded-full bg-blue-50 px-3 py-1 text-xs font-semibold text-blue-700">
                  AI thinking...
                </span>
              ) : null}
            </div>

            <div className="grid grid-cols-3 gap-2">
              {board.map((cell, index) => (
                <button
                  key={BOARD_KEYS[index]}
                  onClick={() => {
                    void handleCellClick(index);
                  }}
                  disabled={boardDisabled || cell !== ""}
                  className="aspect-square rounded-xl border border-slate-300 bg-white text-3xl font-black text-slate-900 shadow-sm transition hover:border-blue-400 disabled:cursor-not-allowed disabled:opacity-80"
                >
                  {cell || "·"}
                </button>
              ))}
            </div>
          </article>

          <article className="glass-effect slide-up rounded-2xl p-5">
            <h2 className="text-sm font-bold uppercase tracking-wide text-slate-500">
              Match Status
            </h2>
            <p className="mt-2 text-lg font-bold text-slate-900">{headline}</p>

            {error ? (
              <div className="mt-4 rounded-lg border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-700">
                {error}
              </div>
            ) : null}

            <div className="mt-5 rounded-xl border border-slate-200 bg-white/70 p-4">
              <h3 className="text-xs font-semibold uppercase tracking-wide text-slate-500">
                AI Agent Reasoning
              </h3>
              <p className="mt-2 whitespace-pre-wrap text-sm leading-6 text-slate-700">
                {aiReasoning}
              </p>
              <p className="mt-3 text-xs font-semibold text-slate-500">
                Source: {moveSource ?? "pending"}
              </p>
            </div>

            <div className="mt-5 rounded-xl border border-cyan-200 bg-cyan-50/80 p-4 text-sm text-cyan-900">
              The AI move is generated by an LLM agent call through LiteLLM.
              Fallback logic is used only if the model returns invalid output.
            </div>
          </article>
        </div>
      </section>
    </main>
  );
}
