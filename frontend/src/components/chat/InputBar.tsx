import { type ChangeEvent, useState } from "react";

import type { RagDocument } from "../../lib/api";

export type PromptMode = "chat" | "image" | "rag" | "db";

type InputBarProps = Readonly<{
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
}>;

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

  const submitPrompt = async () => {
    const trimmed = message.trim();
    const noMessage = !trimmed;
    const noAttachments = attachments.length === 0;
    if ((mode === "chat" || mode === "db") && noMessage && noAttachments) {
      return;
    }
    if (mode !== "chat" && mode !== "db" && noMessage) {
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

  const submit = (event: { preventDefault: () => void }) => {
    event.preventDefault();
    void submitPrompt();
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
    db: "Sheet Insights",
  };
  const placeholders: Record<PromptMode, string> = {
    chat: "Type your question and optionally attach files...",
    image: "Describe the image you want to generate...",
    rag: "Ask a question grounded in your selected PDF...",
    db: "Attach CSV/XLSX or ask a question about the loaded spreadsheet data...",
  };
  const modeLabel = modeLabels[mode];

  return (
    <form
      onSubmit={submit}
      className="rounded-2xl border border-slate-200/80 bg-white/90 p-6 shadow-lg shadow-slate-900/5 backdrop-blur"
    >
      <div className="mb-4 space-y-3">
        {/* Mode Selector */}
        <div className="flex flex-wrap items-center gap-3">
          <label
            htmlFor="prompt-mode-select"
            className="text-xs font-semibold uppercase tracking-widest text-slate-600"
          >
            🎯 Mode
          </label>
          <select
            id="prompt-mode-select"
            value={mode}
            onChange={(event) => onModeChange(event.target.value as PromptMode)}
            className="rounded-lg border border-slate-200 bg-white px-3 py-2 text-sm text-slate-800 shadow-sm transition focus:border-blue-400 focus:ring-2 focus:ring-blue-100"
          >
            <option value="chat" className="bg-white text-slate-900">
              💬 Chatbot
            </option>
            <option value="image" className="bg-white text-slate-900">
              🎨 Generate Image
            </option>
            <option value="rag" className="bg-white text-slate-900">
              📄 RAG (PDF)
            </option>
            <option value="db" className="bg-white text-slate-900">
              📊 Sheet Insights
            </option>
          </select>

          {mode === "rag" ? (
            <>
              <select
                value={selectedRagDocId ?? ""}
                onChange={(event) => onSelectRagDoc(event.target.value)}
                className="min-w-52 rounded-lg border border-slate-200 bg-white px-3 py-2 text-sm text-slate-800 shadow-sm transition focus:border-blue-400 focus:ring-2 focus:ring-blue-100"
              >
                <option value="" disabled className="bg-white text-slate-900">
                  Select PDF document
                </option>
                {ragDocuments
                  .filter((doc) => doc.status === "ready")
                  .map((doc) => (
                    <option
                      key={doc.id}
                      value={doc.id}
                      className="bg-white text-slate-900"
                    >
                      {doc.filename}
                    </option>
                  ))}
              </select>

              <label className="cursor-pointer rounded-lg border border-slate-200 bg-white px-4 py-2 text-sm font-medium text-slate-700 transition hover:bg-slate-50 hover:text-slate-900 disabled:opacity-50">
                {isUploadingRag ? (
                  <div className="flex items-center gap-2">
                    <span className="spin-smooth inline-block h-4 w-4 rounded-full border-2 border-blue-200 border-t-blue-600" />
                    <span>Uploading...</span>
                  </div>
                ) : (
                  "📤 Upload PDF"
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

        {/* Active Mode Indicator */}
        <div className="inline-flex gap-2 rounded-lg bg-blue-50 px-3 py-1">
          <p className="text-xs text-blue-700">Current Mode:</p>
          <span className="text-xs font-semibold text-blue-900">
            {modeLabel}
          </span>
        </div>
      </div>

      {/* Attachments Preview */}
      {attachments.length > 0 ? (
        <div className="mb-4 flex flex-wrap gap-2">
          {attachments.map((file, index) => (
            <div
              key={`${file.name}-${index}`}
              className="slide-down flex items-center gap-2 rounded-full border border-slate-200 bg-slate-50 px-3 py-1.5 text-xs text-slate-700"
            >
              <span className="truncate max-w-[200px]">📎 {file.name}</span>
              <button
                type="button"
                onClick={() => removeAttachment(index)}
                className="rounded-full bg-red-100 px-2 text-red-700 transition hover:bg-red-200"
              >
                ✕
              </button>
            </div>
          ))}
        </div>
      ) : null}

      {/* Input Area */}
      <div className="flex gap-3">
        <textarea
          value={message}
          onChange={(event) => setMessage(event.target.value)}
          className="h-20 flex-1 resize-none rounded-2xl border border-slate-200 bg-white px-4 py-3 text-slate-800 placeholder-slate-400 shadow-sm transition focus:border-blue-400 focus:ring-2 focus:ring-blue-100"
          placeholder={placeholders[mode]}
        />
        <div className="flex flex-col gap-2">
          <label
            className={`group cursor-pointer rounded-xl border border-slate-200 bg-white px-4 py-2 text-center text-sm font-medium text-slate-700 transition hover:bg-slate-50 hover:text-slate-900 ${
              mode === "chat" || mode === "db"
                ? ""
                : "pointer-events-none opacity-40"
            }`}
          >
            <span>📎</span>
            <input
              type="file"
              multiple
              onChange={onFileChange}
              className="hidden"
              disabled={mode !== "chat" && mode !== "db"}
              accept="image/*,video/*,.csv,.tsv,.xlsx,.xls,.tex,.latex,.md,.py,.js,.ts,.tsx,.jsx,.java,.go,.rs,.cpp,.c,.sql,.json,.yaml,.yml"
            />
          </label>
          <button
            type="submit"
            disabled={disabled || isSending}
            className="group relative flex items-center justify-center gap-2 overflow-hidden rounded-xl bg-gradient-to-r from-blue-600 to-cyan-500 px-5 py-2 font-semibold text-white shadow-md shadow-blue-500/30 transition hover:from-blue-700 hover:to-cyan-600 disabled:cursor-not-allowed disabled:opacity-50"
          >
            <div className="absolute inset-0 bg-gradient-to-r from-cyan-500 to-blue-600 opacity-0 transition group-hover:opacity-100"></div>
            <span className="relative flex items-center gap-2">
              {isSending ? (
                <>
                  <span className="spin-smooth inline-block h-4 w-4 rounded-full border-2 border-white/30 border-t-white" />
                  <span>Sending...</span>
                </>
              ) : (
                <>➤ Send</>
              )}
            </span>
          </button>
        </div>
      </div>
    </form>
  );
}
