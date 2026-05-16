export type TicTacToeCell = "" | "X" | "O";

export type GameStatus = "in_progress" | "won" | "draw";

export interface MoveResponse {
  board: TicTacToeCell[];
  ai_move: number;
  ai_reasoning: string;
  move_source: "llm" | "fallback";
  status: GameStatus;
  winner: "X" | "O" | null;
}
