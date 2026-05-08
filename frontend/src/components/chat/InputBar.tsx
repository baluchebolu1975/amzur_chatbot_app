import { type ChangeEvent, type FormEvent, useState } from "react";

import type { RagDocument } from "../../lib/api";

export type PromptMode = "chat" | "image" | "rag" | "db";

type InputBarProps = {
  disabled: boolean;
  mode: PromptMode;
  onModeChange: (mode: PromptMode) => void;
  ragDocuments: RagDocument[];
  selectedRagDocId: string | null;
  onSelectRagDoc: (docId: string) => void;
  onUploadRag: (file: File) => Promise<void>;
  isUploadingRag: boolean;
  isSending: boolean;
  onSend: (
    message: string,
    attachments: File[],
    mode: PromptMode,
    ragDocId: string | null,
  ) => Promise<void>;
};

export function InputBar({
  disabled,
  mode,
  onModeChange,
  ragDocuments,
  selectedRagDocId,
  onSelectRagDoc,
  onUploadRag,
  isUploadingRag,
  isSending,
  onSend,
}: InputBarProps) {
  const [message, setMessage] = useState("");
  const [attachments, setAttachments] = useState<File[]>([]);

  const onFileChange = (event: ChangeEvent<HTMLInputElement>) => {
    const selected = Array.from(event.target.files ?? []);
    if (!selected.length) {
      return;
    }
    setAttachments((prev) => [...prev, ...selected].slice(0, 8));
    event.target.value = "";
  };

  const removeAttachment = (indexToRemove: number) => {
    setAttachments((prev) =>
      prev.filter((_, index) => index !== indexToRemove),
    );
  };

  const submit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    const trimmed = message.trim();
    const noMessage = !trimmed;
    const noAttachments = attachments.length === 0;
    if (mode === "chat" && noMessage && noAttachments) {
      return;
    }
    if (mode !== "chat" && noMessage) {
      return;
    }
    if (mode === "rag" && !selectedRagDocId) {
      return;
    }

    setMessage("");
    const filesToSend = [...attachments];
    setAttachments([]);
    await onSend(
      trimmed || "Analyze these attachments and answer.",
      filesToSend,
      mode,
      selectedRagDocId,
    );
  };

  const onRagUpload = async (event: ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0];
    if (!file) {
      return;
    }
    await onUploadRag(file);
    event.target.value = "";
  };

  const modeLabels: Record<PromptMode, string> = {
    chat: "Chat",
    image: "Generate Image",
    rag: "Ask PDF",
    db: "Database Insights",
  };
  const placeholders: Record<PromptMode, string> = {
    chat: "Type your question and optionally attach files...",
    image: "Describe the image you want to generate...",
    rag: "Ask a question grounded in your selected PDF...",
    db: "Ask about chat/image/RAG history in natural language...",
  };
  const modeLabel = modeLabels[mode];

  return (
    <form onSubmit={submit} className="border-t border-slate-200 bg-white p-4">
      <div className="mb-3 flex flex-wrap items-center gap-3">
        <label
          htmlFor="prompt-mode-select"
          className="text-xs font-semibold uppercase tracking-wide text-slate-500"
        >
          Mode
        </label>
        <select
          id="prompt-mode-select"
          value={mode}
          onChange={(event) => onModeChange(event.target.value as PromptMode)}
          className="rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm outline-none focus:border-cyan-700"
        >
          <option value="chat">Chatbot</option>
          <option value="image">Generate Image</option>
          <option value="rag">RAG (PDF)</option>
          <option value="db">DB Insights</option>
        </select>

        {mode === "rag" ? (
          <>
            <select
              value={selectedRagDocId ?? ""}
              onChange={(event) => onSelectRagDoc(event.target.value)}
              className="min-w-52 rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm outline-none focus:border-cyan-700"
            >
              <option value="" disabled>
                Select PDF document
              </option>
              {ragDocuments
                .filter((doc) => doc.status === "ready")
                .map((doc) => (
                  <option key={doc.id} value={doc.id}>
                    {doc.filename}
                  </option>
                ))}
            </select>

            <label className="cursor-pointer rounded-lg border border-slate-300 px-3 py-2 text-sm transition-all hover:bg-slate-50 disabled:opacity-60">
              {isUploadingRag ? (
                <div className="flex items-center gap-2">
                  <svg
                    className="h-4 w-4 animate-spin"
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
                  Uploading...
                </div>
              ) : (
                "Upload PDF"
              )}
              <input
                type="file"
                accept=".pdf"
                onChange={onRagUpload}
                className="hidden"
                disabled={isUploadingRag}
              />
            </label>
          </>
        ) : null}
      </div>

      {attachments.length > 0 ? (
        <div className="mb-3 flex flex-wrap gap-2">
          {attachments.map((file, index) => (
            <div
              key={`${file.name}-${index}`}
              className="flex items-center gap-2 rounded-full bg-slate-100 px-3 py-1 text-xs text-slate-700"
            >
              <span>{file.name}</span>
              <button
                type="button"
                onClick={() => removeAttachment(index)}
                className="rounded-full bg-slate-300 px-2 text-[10px]"
              >
                x
              </button>
            </div>
          ))}
        </div>
      ) : null}

      <div className="mb-2 text-xs text-slate-500">
        Active mode:{" "}
        <span className="font-semibold text-slate-700">{modeLabel}</span>
      </div>

      <div className="flex gap-3">
        <textarea
          value={message}
          onChange={(event) => setMessage(event.target.value)}
          className="h-20 flex-1 resize-none rounded-xl border border-slate-300 px-3 py-2 outline-none focus:border-cyan-700"
          placeholder={placeholders[mode]}
        />
        <div className="flex flex-col gap-2">
          <label
            className={`cursor-pointer rounded-xl border border-slate-300 px-4 py-2 text-center text-sm transition-colors ${
              mode !== "chat" ? "pointer-events-none opacity-40" : ""
            }`}
          >
            Attach
            <input
              type="file"
              multiple
              onChange={onFileChange}
              className="hidden"
              disabled={mode !== "chat"}
              accept="image/*,video/*,.csv,.tsv,.xlsx,.xls,.tex,.latex,.md,.py,.js,.ts,.tsx,.jsx,.java,.go,.rs,.cpp,.c,.sql,.json,.yaml,.yml"
            />
          </label>
          <button
            type="submit"
            disabled={disabled || isSending}
            className="flex items-center justify-center gap-2 rounded-xl bg-cyan-700 px-5 py-2 text-white transition-all disabled:opacity-60"
          >
            {isSending ? (
              <>
                <svg
                  className="h-4 w-4 animate-spin"
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
                Processing...
              </>
            ) : (
              "Send"
            )}
          </button>
        </div>
      </div>
    </form>
  );
}
