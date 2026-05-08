import ReactMarkdown from "react-markdown";
import rehypeKatex from "rehype-katex";
import remarkMath from "remark-math";

import type { Message } from "../../types";

type MessageListProps = {
  messages: Message[];
  streamingText: string;
  isLoading: boolean;
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
        const displayContent = isImage && dataUrl ? dataUrl : message.content;

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
            <div className="text-justify [&_p]:my-2 [&_pre]:overflow-auto [&_pre]:rounded-lg [&_pre]:bg-slate-900 [&_pre]:p-3 [&_pre]:text-slate-100 [&_code]:rounded [&_code]:bg-slate-200 [&_code]:px-1">
              {isImage && dataUrl ? (
                <img
                  src={dataUrl}
                  alt="Generated"
                  className="max-h-96 rounded-lg border border-slate-200 object-contain"
                />
              ) : (
                <ReactMarkdown
                  remarkPlugins={[remarkMath]}
                  rehypePlugins={[rehypeKatex]}
                >
                  {displayContent}
                </ReactMarkdown>
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
            <p className="text-slate-600">
              Working on your request...
            </p>
          </div>
        </article>
      ) : null}
    </div>
  );
}
