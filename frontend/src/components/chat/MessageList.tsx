import ReactMarkdown from "react-markdown";
import rehypeKatex from "rehype-katex";
import remarkMath from "remark-math";

import type { Message } from "../../types";

type MessageListProps = {
  messages: Message[];
  streamingText: string;
  isLoading: boolean;
};

type DbResultTable = {
  rows: Array<Record<string, unknown>>;
  displayContent: string;
};

function isDataImage(content: string): boolean {
  const trimmed = content.trim();
  return (
    trimmed.startsWith("data:image/") ||
    trimmed.startsWith("![Generated image](data:image/")
  );
}

function extractDataUrlFromMarkdown(content: string): string | null {
  const match = content.match(/!\[Generated image\]\((data:image\/[^)]+)\)/);
  return match ? match[1] : null;
}

function parseDbResultTable(content: string): DbResultTable | null {
  const resultBlockRegex = /###\s*Result\s*```json\s*([\s\S]*?)\s*```/i;
  const match = content.match(resultBlockRegex);
  if (!match) {
    return null;
  }

  try {
    const parsed = JSON.parse(match[1]) as unknown;
    if (!Array.isArray(parsed)) {
      return null;
    }

    const rows = parsed.filter(
      (item): item is Record<string, unknown> =>
        typeof item === "object" && item !== null && !Array.isArray(item),
    );

    if (!rows.length) {
      return null;
    }

    const displayContent = content.replace(
      resultBlockRegex,
      "### Result\n(Shown in table format below)",
    );

    return { rows, displayContent };
  } catch {
    return null;
  }
}

function formatCellValue(value: unknown): string {
  if (value === null || value === undefined) {
    return "";
  }

  if (typeof value === "string") {
    return value;
  }

  if (typeof value === "number" || typeof value === "boolean") {
    return String(value);
  }

  try {
    return JSON.stringify(value);
  } catch {
    return String(value);
  }
}

export function MessageList({
  messages,
  streamingText,
  isLoading,
}: MessageListProps) {
  const combined = streamingText
    ? [
        ...messages,
        {
          id: "streaming",
          thread_id: messages[messages.length - 1]?.thread_id ?? "",
          role: "assistant",
          content: streamingText,
          created_at: new Date().toISOString(),
        },
      ]
    : messages;

  return (
    <div className="flex-1 space-y-4 overflow-auto p-4">
      {combined.map((message) => {
        const dataUrl = extractDataUrlFromMarkdown(message.content);
        const isImage = isDataImage(message.content);
        const dbResultTable = parseDbResultTable(message.content);
        const displayContent =
          isImage && dataUrl
            ? dataUrl
            : (dbResultTable?.displayContent ?? message.content);
        const tableColumns = dbResultTable
          ? Array.from(
              new Set(dbResultTable.rows.flatMap((row) => Object.keys(row))),
            )
          : [];

        return (
          <article
            key={message.id}
            className={`max-w-3xl rounded-2xl px-4 py-3 text-sm leading-7 shadow-sm ${
              message.role === "user"
                ? "ml-auto bg-cyan-800 text-white"
                : "mr-auto bg-white text-slate-900"
            }`}
          >
            <p className="mb-2 text-[11px] uppercase tracking-wide opacity-70">
              {message.role}
            </p>
            <div className="text-justify [&_p]:my-2 [&_pre]:overflow-auto [&_pre]:rounded-lg [&_pre]:border [&_pre]:border-slate-300 [&_pre]:bg-slate-50 [&_pre]:p-3 [&_pre]:text-slate-900 [&_pre_code]:bg-transparent [&_pre_code]:p-0 [&_code]:rounded [&_code]:bg-slate-100 [&_code]:px-1 [&_code]:text-slate-900">
              {isImage && dataUrl ? (
                <img
                  src={dataUrl}
                  alt="Generated"
                  className="max-h-96 rounded-lg border border-slate-200 object-contain"
                />
              ) : (
                <>
                  <ReactMarkdown
                    remarkPlugins={[remarkMath]}
                    rehypePlugins={[rehypeKatex]}
                  >
                    {displayContent}
                  </ReactMarkdown>
                  {dbResultTable ? (
                    <div className="mt-3 overflow-x-auto rounded-lg border border-slate-300 bg-white">
                      <table className="min-w-full border-collapse text-left text-xs">
                        <thead className="bg-slate-100 text-slate-800">
                          <tr>
                            {tableColumns.map((column) => (
                              <th
                                key={column}
                                className="border-b border-slate-300 px-3 py-2 font-semibold"
                              >
                                {column}
                              </th>
                            ))}
                          </tr>
                        </thead>
                        <tbody>
                          {dbResultTable.rows.map((row, rowIndex) => (
                            <tr
                              key={rowIndex}
                              className="odd:bg-white even:bg-slate-50"
                            >
                              {tableColumns.map((column) => (
                                <td
                                  key={`${rowIndex}-${column}`}
                                  className="max-w-[260px] border-b border-slate-200 px-3 py-2 align-top break-words text-slate-900"
                                >
                                  {formatCellValue(row[column])}
                                </td>
                              ))}
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>
                  ) : null}
                </>
              )}
            </div>
          </article>
        );
      })}
      {isLoading && !streamingText ? (
        <article className="mr-auto max-w-3xl rounded-2xl bg-white px-4 py-3 text-sm leading-7 text-slate-900 shadow-sm">
          <p className="mb-2 text-[11px] uppercase tracking-wide opacity-70">
            assistant
          </p>
          <div className="flex items-center gap-2">
            <svg
              className="h-5 w-5 animate-spin text-cyan-700"
              xmlns="http://www.w3.org/2000/svg"
              fill="none"
              viewBox="0 0 24 24"
            >
              <circle
                className="opacity-25"
                cx="12"
                cy="12"
                r="10"
                stroke="currentColor"
                strokeWidth="4"
              />
              <path
                className="opacity-75"
                fill="currentColor"
                d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"
              />
            </svg>
            <p className="text-slate-600">Working on your request...</p>
          </div>
        </article>
      ) : null}
    </div>
  );
}
