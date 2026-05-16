import type { TicTacToeCell } from "../types/game";

interface BoardProps {
  board: TicTacToeCell[];
  disabled: boolean;
  onSelect: (index: number) => void;
}

export default function Board({
  board,
  disabled,
  onSelect,
}: Readonly<BoardProps>) {
  return (
    <div
      style={{
        display: "grid",
        gridTemplateColumns: "repeat(3, 96px)",
        gap: 8,
      }}
    >
      {board.map((cell, index) => (
        <button
          key={`cell-${index}`}
          disabled={disabled || cell !== ""}
          onClick={() => onSelect(index)}
          style={{ width: 96, height: 96, fontSize: 30, fontWeight: 700 }}
        >
          {cell || "-"}
        </button>
      ))}
    </div>
  );
}
