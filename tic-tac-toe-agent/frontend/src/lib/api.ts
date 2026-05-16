import axios from "axios";

import type { MoveResponse, TicTacToeCell } from "../types/game";

const api = axios.create({
  baseURL: import.meta.env.VITE_API_URL ?? "http://127.0.0.1:8001/api",
  withCredentials: true,
});

export async function requestAiMove(
  board: TicTacToeCell[],
  playerSymbol: "X" | "O" = "X",
  aiSymbol: "X" | "O" = "O",
): Promise<MoveResponse> {
  const response = await api.post("/tictactoe/move", {
    board,
    player_symbol: playerSymbol,
    ai_symbol: aiSymbol,
  });
  return response.data as MoveResponse;
}
