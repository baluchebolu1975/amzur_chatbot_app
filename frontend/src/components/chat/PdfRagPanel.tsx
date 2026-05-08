import { useEffect, useRef, useState } from "react";
import {
  deleteRagDocument,
  listRagDocuments,
  streamRagAnswer,
  uploadRagDocument,
  type RagDocument,
} from "../../lib/api";

interface Message {
  role: "user" | "assistant";
  content: string;
}

export function PdfRagPanel() {
  const [documents, setDocuments] = useState<RagDocument[]>([]);
  const [activeDocId, setActiveDocId] = useState<string | null>(null);
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState("");
  const [isStreaming, setIsStreaming] = useState(false);
  const [isUploading, setIsUploading] = useState(false);
  const [uploadError, setUploadError] = useState<string | null>(null);
  const [chatError, setChatError] = useState<string | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const messagesEndRef = useRef<HTMLDivElement>(null);

  const activeDoc = documents.find((d) => d.id === activeDocId) ?? null;

  // Load documents on mount
  useEffect(() => {
    listRagDocuments()
      .then((docs) => {
        setDocuments(docs);
        if (docs.length > 0 && !activeDocId) {
          setActiveDocId(docs[0].id);
        }
      })
      .catch(() => {});
  }, []);

  // Auto scroll to bottom when new messages appear
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  async function handleUpload(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0];
    if (!file) return;

    setIsUploading(true);
    setUploadError(null);

    try {
      const doc = await uploadRagDocument(file);
      setDocuments((prev) => [doc, ...prev]);
      setActiveDocId(doc.id);
      setMessages([]);
    } catch (err: unknown) {
      const msg =
        err instanceof Error ? err.message : "Upload failed. Please try again.";
      setUploadError(msg);
    } finally {
      setIsUploading(false);
      if (fileInputRef.current) fileInputRef.current.value = "";
    }
  }

  async function handleDeleteDocument(docId: string) {
    try {
      await deleteRagDocument(docId);
      setDocuments((prev) => prev.filter((d) => d.id !== docId));
      if (activeDocId === docId) {
        const remaining = documents.filter((d) => d.id !== docId);
        setActiveDocId(remaining.length > 0 ? remaining[0].id : null);
        setMessages([]);
      }
    } catch {
      // ignore
    }
  }

  async function handleSend() {
    if (!input.trim() || !activeDocId || isStreaming) return;
    if (activeDoc?.status !== "ready") return;

    const question = input.trim();
    setInput("");
    setChatError(null);

    const userMessage: Message = { role: "user", content: question };
    setMessages((prev) => [...prev, userMessage]);

    const assistantMessage: Message = { role: "assistant", content: "" };
    setMessages((prev) => [...prev, assistantMessage]);

    setIsStreaming(true);

    try {
      // Build history without the just-added empty assistant message
      const history = [...messages, userMessage].map((m) => ({
        role: m.role,
        content: m.content,
      }));

      await streamRagAnswer(activeDocId, question, history, (chunk) => {
        setMessages((prev) => {
          const updated = [...prev];
          const last = updated[updated.length - 1];
          if (last?.role === "assistant") {
            updated[updated.length - 1] = {
              ...last,
              content: last.content + chunk,
            };
          }
          return updated;
        });
      });
    } catch (err: unknown) {
      const msg =
        err instanceof Error ? err.message : "Failed to get response.";
      setChatError(msg);
      // Remove the empty assistant message
      setMessages((prev) => prev.filter((_, i) => i !== prev.length - 1));
    } finally {
      setIsStreaming(false);
    }
  }

  return (
    <div className="flex h-[600px] flex-col overflow-hidden rounded-xl border border-slate-200 bg-white shadow-sm">
      {/* Header */}
      <div className="flex items-center justify-between border-b border-slate-200 bg-slate-50 px-4 py-3">
        <div>
          <h3 className="font-semibold text-slate-900">Chat with PDF</h3>
          <p className="text-xs text-slate-500">
            Upload a PDF and ask questions about its content
          </p>
        </div>
        <div className="flex items-center gap-2">
          <input
            ref={fileInputRef}
            type="file"
            accept=".pdf"
            onChange={handleUpload}
            className="hidden"
            id="rag-pdf-upload"
          />
          <label
            htmlFor="rag-pdf-upload"
            className={`cursor-pointer rounded-md border border-slate-300 bg-white px-3 py-1.5 text-sm font-medium text-slate-700 hover:bg-slate-50 ${
              isUploading ? "pointer-events-none opacity-60" : ""
            }`}
          >
            {isUploading ? "Uploading…" : "Upload PDF"}
          </label>
        </div>
      </div>

      {uploadError && (
        <div className="border-b border-red-100 bg-red-50 px-4 py-2 text-sm text-red-700">
          {uploadError}
        </div>
      )}

      <div className="flex flex-1 overflow-hidden">
        {/* Document sidebar */}
        <div className="w-52 flex-shrink-0 overflow-y-auto border-r border-slate-200 bg-slate-50 p-2">
          <p className="mb-2 px-1 text-xs font-semibold uppercase tracking-wide text-slate-500">
            Documents
          </p>
          {documents.length === 0 && (
            <p className="px-1 text-xs text-slate-400">No PDFs uploaded yet.</p>
          )}
          {documents.map((doc) => (
            <div
              key={doc.id}
              onClick={() => {
                if (activeDocId !== doc.id) {
                  setActiveDocId(doc.id);
                  setMessages([]);
                  setChatError(null);
                }
              }}
              className={`group mb-1 flex cursor-pointer items-start justify-between gap-1 rounded-lg px-2 py-2 text-xs transition ${
                activeDocId === doc.id
                  ? "bg-cyan-50 text-cyan-900"
                  : "text-slate-700 hover:bg-slate-100"
              }`}
            >
              <div className="min-w-0">
                <p className="truncate font-medium" title={doc.filename}>
                  {doc.filename}
                </p>
                <p
                  className={`mt-0.5 text-[10px] ${
                    doc.status === "ready"
                      ? "text-green-600"
                      : doc.status === "failed"
                        ? "text-red-500"
                        : "text-amber-500"
                  }`}
                >
                  {doc.status === "ready"
                    ? `${doc.chunk_count} chunks`
                    : doc.status}
                </p>
              </div>
              <button
                onClick={(e) => {
                  e.stopPropagation();
                  handleDeleteDocument(doc.id);
                }}
                title="Delete document"
                className="mt-0.5 flex-shrink-0 text-slate-400 opacity-0 hover:text-red-500 group-hover:opacity-100"
              >
                ✕
              </button>
            </div>
          ))}
        </div>

        {/* Chat area */}
        <div className="flex flex-1 flex-col overflow-hidden">
          {!activeDocId ? (
            <div className="flex flex-1 items-center justify-center text-sm text-slate-400">
              Upload a PDF to start chatting
            </div>
          ) : (
            <>
              {/* Active document indicator */}
              <div className="border-b border-slate-100 bg-white px-4 py-2">
                <p className="text-xs text-slate-500">
                  Chatting with:{" "}
                  <span className="font-semibold text-slate-700">
                    {activeDoc?.filename}
                  </span>
                  {activeDoc?.status !== "ready" && (
                    <span className="ml-2 text-amber-500">
                      ({activeDoc?.status})
                    </span>
                  )}
                </p>
              </div>

              {/* Messages */}
              <div className="flex-1 overflow-y-auto px-4 py-4 space-y-4">
                {messages.length === 0 && (
                  <p className="text-center text-sm text-slate-400">
                    Ask a question about the document…
                  </p>
                )}
                {messages.map((msg, i) => (
                  <div
                    key={i}
                    className={`flex ${msg.role === "user" ? "justify-end" : "justify-start"}`}
                  >
                    <div
                      className={`max-w-[85%] rounded-xl px-4 py-2.5 text-sm leading-relaxed ${
                        msg.role === "user"
                          ? "bg-cyan-600 text-white"
                          : "border border-slate-200 bg-white text-slate-800 shadow-sm"
                      }`}
                    >
                      {msg.content || (
                        <span className="animate-pulse text-slate-400">
                          Thinking…
                        </span>
                      )}
                    </div>
                  </div>
                ))}
                {chatError && (
                  <div className="rounded-lg bg-red-50 px-4 py-2 text-sm text-red-600">
                    {chatError}
                  </div>
                )}
                <div ref={messagesEndRef} />
              </div>

              {/* Input */}
              <div className="border-t border-slate-200 bg-white p-3">
                <div className="flex gap-2">
                  <textarea
                    value={input}
                    onChange={(e) => setInput(e.target.value)}
                    onKeyDown={(e) => {
                      if (e.key === "Enter" && !e.shiftKey) {
                        e.preventDefault();
                        handleSend();
                      }
                    }}
                    placeholder="Ask a question about the document… (Enter to send)"
                    rows={2}
                    disabled={isStreaming || activeDoc?.status !== "ready"}
                    className="flex-1 resize-none rounded-lg border border-slate-300 px-3 py-2 text-sm outline-none focus:border-cyan-500 disabled:opacity-50"
                  />
                  <button
                    onClick={handleSend}
                    disabled={
                      !input.trim() ||
                      isStreaming ||
                      activeDoc?.status !== "ready"
                    }
                    className="self-end rounded-lg bg-cyan-600 px-4 py-2 text-sm font-medium text-white hover:bg-cyan-700 disabled:opacity-50"
                  >
                    {isStreaming ? "…" : "Ask"}
                  </button>
                </div>
              </div>
            </>
          )}
        </div>
      </div>
    </div>
  );
}
