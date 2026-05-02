import ReactMarkdown from "react-markdown";
import rehypeKatex from "rehype-katex";
import remarkMath from "remark-math";

import type { Message } from "../../types";

type MessageListProps = {
  messages: Message[];
  streamingText: string;
};

export function MessageList({ messages, streamingText }: MessageListProps) {
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
      {combined.map((message) => (
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
            <ReactMarkdown
              remarkPlugins={[remarkMath]}
              rehypePlugins={[rehypeKatex]}
            >
              {message.content}
            </ReactMarkdown>
          </div>
        </article>
      ))}
    </div>
  );
}
