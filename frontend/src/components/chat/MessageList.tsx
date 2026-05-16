import type { ComponentPropsWithoutRef } from "react";
import ReactMarkdown from "react-markdown";
import rehypeKatex from "rehype-katex";
import remarkGfm from "remark-gfm";
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

const MARKDOWN_LINK_RE = /\[[^\]]+\]\(https?:\/\/[^)]+\)/i;
const URL_RE = /https?:\/\/[^\s<>)\]]+/g;
const REF_HEADER_RE =
  /^\s*(?:#{1,6}\s*)?(?:\*\*)?\s*(references|reference|sources?)\s*(?:\*\*)?\s*:?\s*$/i;

function linkifyReferencesForDisplay(content: string): string {
  if (!content.trim()) {
    return content;
  }

  const lines = content.split("\n");
  const out: string[] = [];
  let inRefs = false;

  for (const line of lines) {
    const trimmed = line.trim();

    if (REF_HEADER_RE.test(trimmed)) {
      inRefs = true;
      out.push(line);
      continue;
    }

    if (inRefs && trimmed.startsWith("### ") && !REF_HEADER_RE.test(trimmed)) {
      inRefs = false;
    }

    if (!trimmed) {
      out.push(line);
      continue;
    }

    if (MARKDOWN_LINK_RE.test(line)) {
      out.push(line);
      continue;
    }

    if (URL_RE.test(line)) {
      out.push(line.replace(URL_RE, (url) => `[${url}](${url})`));
      continue;
    }

    if (!inRefs) {
      out.push(line);
      continue;
    }

    const match = line.match(/^(\s*(?:[-*]|\d+\.|\[\d+\]))\s+(.*)$/);
    if (match) {
      const prefix = match[1];
      const title = match[2].trim().replace(/[.;]+$/, "");
      if (title) {
        const query = encodeURIComponent(title);
        out.push(
          `${prefix} [${title}](https://arxiv.org/search/?query=${query}&searchtype=all)`,
        );
        continue;
      }
    }

    const title = trimmed.replace(/[.;]+$/, "");
    const query = encodeURIComponent(title);
    out.push(
      `- [${title}](https://arxiv.org/search/?query=${query}&searchtype=all)`,
    );
  }

  return out.join("\n");
}

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
    <div className="flex-1 space-y-4 overflow-auto p-6 slide-up">
      {combined.length === 0 ? (
        <div className="flex h-full items-center justify-center">
          <div className="text-center text-slate-500">
            <p className="text-2xl mb-2">💬</p>
            <p className="text-sm">No messages yet. Start a conversation!</p>
          </div>
        </div>
      ) : (
        combined.map((message) => {
          const isUserMessage = message.role === "user";
          const dataUrl = extractDataUrlFromMarkdown(message.content);
          const isImage = isDataImage(message.content);
          const dbResultTable = parseDbResultTable(message.content);
          const normalizedContent = linkifyReferencesForDisplay(
            dbResultTable?.displayContent ?? message.content,
          );
          const displayContent =
            isImage && dataUrl ? dataUrl : normalizedContent;
          const tableColumns = dbResultTable
            ? Array.from(
                new Set(dbResultTable.rows.flatMap((row) => Object.keys(row))),
              )
            : [];

          return (
            <article
              key={message.id}
              className={`slide-up max-w-2xl rounded-2xl px-5 py-4 text-sm leading-7 ${
                isUserMessage
                  ? "ml-auto bg-gradient-to-br from-blue-600 to-cyan-500 text-white shadow-lg shadow-blue-500/30"
                  : "mr-auto border border-slate-200 bg-white/95 text-slate-800 shadow-lg shadow-slate-900/5"
              }`}
            >
              <p className="mb-3 text-xs font-semibold uppercase tracking-widest opacity-70">
                {isUserMessage ? "👤 You" : "🤖 Assistant"}
              </p>
              <div
                className={`prose-sm max-w-none text-justify [&_p]:my-2 [&_h1]:text-lg [&_h1]:font-bold [&_h2]:text-base [&_h2]:font-bold [&_h3]:font-semibold [&_ol]:my-2 [&_ul]:my-2 [&_li]:my-1 [&_pre]:overflow-auto [&_pre]:rounded-xl [&_pre]:p-4 [&_pre_code]:bg-transparent [&_pre_code]:p-0 [&_code]:rounded [&_code]:px-1.5 [&_code]:py-0.5 [&_code]:font-mono [&_code]:text-xs [&_blockquote]:border-l-2 [&_blockquote]:pl-3 [&_blockquote]:italic [&_blockquote]:opacity-90 ${
                  isUserMessage
                    ? "prose-invert [&_pre]:border [&_pre]:border-white/20 [&_pre]:bg-slate-900/80 [&_pre]:text-slate-100 [&_code]:bg-white/20 [&_blockquote]:border-cyan-200"
                    : "text-slate-800 [&_pre]:border [&_pre]:border-slate-200 [&_pre]:bg-slate-900 [&_pre]:text-slate-100 [&_code]:bg-slate-100 [&_blockquote]:border-blue-400"
                }`}
              >
                {isImage && dataUrl ? (
                  <img
                    src={dataUrl}
                    alt="Generated"
                    className="max-h-96 rounded-xl border border-slate-300/80 object-contain"
                  />
                ) : (
                  <>
                    <ReactMarkdown
                      remarkPlugins={[remarkGfm, remarkMath]}
                      rehypePlugins={[rehypeKatex]}
                      components={{
                        a: ({ href, className, children, ...props }) => {
                          const anchorProps: ComponentPropsWithoutRef<"a"> = {
                            ...props,
                            href,
                            target: "_blank",
                            rel: "noopener noreferrer",
                            className: [
                              "font-medium text-blue-600 underline underline-offset-2 hover:text-blue-700 visited:text-blue-700 cursor-pointer",
                              className,
                            ]
                              .filter(Boolean)
                              .join(" "),
                          };

                          return <a {...anchorProps}>{children}</a>;
                        },
                      }}
                    >
                      {displayContent}
                    </ReactMarkdown>
                    {dbResultTable ? (
                      <div className="mt-4 overflow-x-auto rounded-xl border border-slate-200 bg-slate-50">
                        <table className="min-w-full border-collapse text-left text-xs">
                          <thead className="bg-slate-200/70">
                            <tr>
                              {tableColumns.map((column) => (
                                <th
                                  key={column}
                                  className="border-b border-slate-300 px-4 py-3 font-semibold text-slate-900"
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
                                className="border-b border-slate-200 transition hover:bg-slate-50"
                              >
                                {tableColumns.map((column) => (
                                  <td
                                    key={`${rowIndex}-${column}`}
                                    className="max-w-[260px] px-4 py-2 align-top break-words text-slate-900"
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
        })
      )}
      {isLoading && !streamingText ? (
        <article className="mr-auto max-w-3xl rounded-2xl border border-slate-200 bg-white px-4 py-3 text-sm leading-7 text-slate-700 shadow-sm">
          <p className="mb-2 text-[11px] uppercase tracking-wide opacity-70">
            assistant
          </p>
          <div className="flex items-center gap-2">
            <svg
              className="h-5 w-5 animate-spin text-blue-600"
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
