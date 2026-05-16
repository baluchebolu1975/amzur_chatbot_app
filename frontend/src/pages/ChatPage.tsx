import { useCallback, useEffect, useMemo, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useNavigate } from "react-router-dom";

import { InputBar, type PromptMode } from "../components/chat/InputBar";
import { MessageList } from "../components/chat/MessageList";
import { ThreadSidebar } from "../components/chat/ThreadSidebar";
import { useAuthActions, useMe } from "../hooks/useAuth";
import {
  createThread,
  generateImage,
  getThread,
  listRagDocuments,
  listThreads,
  loadDataframeSheet,
  queryDataframeSheet,
  sendMessage,
  streamMessageWithAttachments,
  streamRagAnswer,
  uploadDataframeFile,
  uploadRagDocument,
} from "../lib/api";
import type { Message } from "../types";

export default function ChatPage() {
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const { data: me, isLoading: meLoading, isError: meError } = useMe();
  const { logoutMutation } = useAuthActions();

  const [activeThreadId, setActiveThreadId] = useState<string | null>(null);
  const [streamingText, setStreamingText] = useState("");
  const [mode, setMode] = useState<PromptMode>("db");
  const [selectedRagDocId, setSelectedRagDocId] = useState<string | null>(null);
  const [isSending, setIsSending] = useState(false);
  const [sendError, setSendError] = useState<string | null>(null);
  const [sheetMessagesByThread, setSheetMessagesByThread] = useState<
    Record<string, Message[]>
  >({});
  // Tracks which thread sessions already have an uploaded file loaded
  // so we don't overwrite user uploads with the default sheet on each message
  const [uploadedSheetSessions, setUploadedSheetSessions] = useState<
    Set<string>
  >(new Set());

  const threadsQuery = useQuery({
    queryKey: ["threads"],
    queryFn: listThreads,
    enabled: Boolean(me),
  });

  useEffect(() => {
    if (!activeThreadId && threadsQuery.data && threadsQuery.data.length > 0) {
      setActiveThreadId(threadsQuery.data[0].id);
    }
  }, [activeThreadId, threadsQuery.data]);

  const threadQuery = useQuery({
    queryKey: ["thread", activeThreadId],
    queryFn: async () => {
      if (!activeThreadId) {
        throw new Error("Thread id is required");
      }
      return getThread(activeThreadId);
    },
    enabled: Boolean(activeThreadId),
  });

  const ragDocsQuery = useQuery({
    queryKey: ["rag-documents"],
    queryFn: listRagDocuments,
    enabled: Boolean(me),
  });

  useEffect(() => {
    if (!selectedRagDocId && ragDocsQuery.data?.length) {
      const firstReady = ragDocsQuery.data.find(
        (doc) => doc.status === "ready",
      );
      if (firstReady) {
        setSelectedRagDocId(firstReady.id);
      }
    }
  }, [ragDocsQuery.data, selectedRagDocId]);

  const createThreadMutation = useMutation({
    mutationFn: createThread,
    onSuccess: (thread) => {
      queryClient.invalidateQueries({ queryKey: ["threads"] });
      setActiveThreadId(thread.id);
    },
  });

  const uploadRagMutation = useMutation({
    mutationFn: uploadRagDocument,
    onSuccess: async (doc) => {
      setSelectedRagDocId(doc.id);
      await queryClient.invalidateQueries({ queryKey: ["rag-documents"] });
    },
  });

  useEffect(() => {
    if (meError) {
      navigate("/login");
    }
  }, [meError, navigate]);

  const messages = useMemo(() => {
    const persistedMessages = threadQuery.data?.messages ?? [];
    const sheetMessages = activeThreadId
      ? (sheetMessagesByThread[activeThreadId] ?? [])
      : [];

    return [...persistedMessages, ...sheetMessages];
  }, [activeThreadId, sheetMessagesByThread, threadQuery.data?.messages]);

  const appendSheetMessages = useCallback(
    (threadId: string, userPrompt: string, assistantReply: string) => {
      const timestamp = new Date().toISOString();

      setSheetMessagesByThread((prev) => ({
        ...prev,
        [threadId]: [
          ...(prev[threadId] ?? []),
          {
            id: `sheet-user-${crypto.randomUUID()}`,
            thread_id: threadId,
            role: "user",
            content: userPrompt,
            created_at: timestamp,
          },
          {
            id: `sheet-assistant-${crypto.randomUUID()}`,
            thread_id: threadId,
            role: "assistant",
            content: assistantReply,
            created_at: timestamp,
          },
        ],
      }));
    },
    [],
  );

  const handleModeChange = useCallback((nextMode: PromptMode) => {
    setMode(nextMode);
    setStreamingText("");
    setSendError(null);
  }, []);

  const handleUploadRag = useCallback(
    async (file: File) => {
      setSendError(null);
      await uploadRagMutation.mutateAsync(file);
    },
    [uploadRagMutation],
  );

  const sendThroughMode = useCallback(
    async (
      threadId: string,
      message: string,
      attachments: File[],
      promptMode: PromptMode,
      ragDocId: string | null,
    ) => {
      if (promptMode === "chat") {
        if (attachments.length > 0) {
          setStreamingText("");
          await streamMessageWithAttachments(
            threadId,
            message,
            attachments,
            (chunk) => {
              setStreamingText((prev) => prev + chunk);
            },
          );
          setStreamingText("");
          return;
        }

        await sendMessage(threadId, message);
        return;
      }

      if (promptMode === "image") {
        await generateImage(message, threadId);
        return;
      }

      if (promptMode === "db") {
        if (attachments.length > 0) {
          const sheetAttachments = attachments.filter((file) =>
            /\.(csv|xlsx|xls)$/i.test(file.name),
          );

          if (sheetAttachments.length === 0) {
            throw new Error(
              "Sheet Insights accepts only CSV/XLSX/XLS attachments.",
            );
          }

          const uploadResult = await uploadDataframeFile(
            threadId,
            sheetAttachments[0],
          );

          if (uploadResult.error) {
            throw new Error(uploadResult.error);
          }

          // Mark this thread as having an uploaded file so subsequent
          // messages don't overwrite it with the default sheet
          setUploadedSheetSessions((prev) => new Set([...prev, threadId]));

          appendSheetMessages(
            threadId,
            `Loaded file: ${sheetAttachments[0].name}`,
            `Loaded ${uploadResult.rows} rows from ${sheetAttachments[0].name}.`,
          );
        } else if (!uploadedSheetSessions.has(threadId)) {
          // Only load default sheet if no custom file has been uploaded yet
          await loadDataframeSheet(threadId);
        }

        const result = await queryDataframeSheet(
          message || "Summarize the current spreadsheet data briefly.",
          threadId,
        );
        if (result.error || !result.answer) {
          throw new Error(result.error ?? "Sheet query failed");
        }
        appendSheetMessages(
          threadId,
          message || "Analyze loaded sheet",
          result.answer,
        );
        return;
      }

      if (!ragDocId) {
        throw new Error("Please select a PDF document for RAG mode.");
      }
      setStreamingText("");
      await streamRagAnswer(
        ragDocId,
        message,
        [],
        (chunk) => {
          setStreamingText((prev) => prev + chunk);
        },
        threadId,
      );
      setStreamingText("");
    },
    [appendSheetMessages, uploadedSheetSessions, setUploadedSheetSessions],
  );

  const handleSend = useCallback(
    async (
      message: string,
      attachments: File[],
      promptMode: PromptMode,
      ragDocId: string | null,
    ) => {
      setSendError(null);
      setIsSending(true);
      try {
        let threadId = activeThreadId;
        if (!threadId) {
          const thread = await createThreadMutation.mutateAsync("New Chat");
          threadId = thread.id;
          setActiveThreadId(thread.id);
        }

        await sendThroughMode(
          threadId,
          message,
          attachments,
          promptMode,
          ragDocId,
        );

        await queryClient.invalidateQueries({ queryKey: ["thread", threadId] });
        await queryClient.invalidateQueries({ queryKey: ["threads"] });
      } catch (error) {
        const messageText =
          error instanceof Error ? error.message : "Failed to process request";
        setSendError(messageText);
      } finally {
        setIsSending(false);
      }
    },
    [activeThreadId, createThreadMutation, sendThroughMode, queryClient],
  );

  if (meLoading) {
    return (
      <div className="grid min-h-screen place-items-center bg-transparent">
        <div className="flex flex-col items-center gap-4">
          <div className="spin-smooth h-12 w-12 rounded-full border-4 border-blue-100 border-t-blue-600"></div>
          <p className="text-slate-600">Loading your workspace...</p>
        </div>
      </div>
    );
  }

  return (
    <main className="min-h-screen bg-transparent">
      <header className="sticky top-0 z-20 border-b border-slate-200/80 bg-white/85 px-6 py-4 backdrop-blur-xl">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-4">
            <div className="flex h-10 w-10 items-center justify-center rounded-full bg-gradient-to-br from-blue-600 to-cyan-500 text-white font-bold shadow-md shadow-blue-500/30">
              {me?.email?.[0]?.toUpperCase()}
            </div>
            <div>
              <h1 className="text-lg font-bold tracking-tight text-slate-900">
                Amzur AI Chat
              </h1>
              <p className="text-xs text-slate-500">{me?.email}</p>
            </div>
          </div>
          <button
            onClick={() => {
              navigate("/tictactoe");
            }}
            className="rounded-lg border border-cyan-200 bg-cyan-50 px-4 py-2 text-sm font-semibold text-cyan-800 shadow-sm transition hover:bg-cyan-100"
          >
            Tic Tac Toe Agent
          </button>
          <button
            onClick={async () => {
              await logoutMutation.mutateAsync();
              navigate("/login");
            }}
            className="rounded-lg border border-slate-200 bg-white px-4 py-2 text-sm font-medium text-slate-700 shadow-sm transition hover:bg-slate-50 hover:text-slate-900"
          >
            Logout
          </button>
        </div>
      </header>

      <section className="flex min-h-[calc(100vh-73px)] flex-col gap-4 p-4 md:flex-row">
        <ThreadSidebar
          threads={threadsQuery.data ?? []}
          activeThreadId={activeThreadId}
          onSelectThread={setActiveThreadId}
          onCreateThread={async () => {
            await createThreadMutation.mutateAsync("New Chat");
          }}
        />

        <div className="flex flex-1 flex-col gap-4">
          {sendError ? (
            <div className="slide-down rounded-xl border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-800 shadow-sm">
              <p className="font-semibold">Error</p>
              <p className="mt-1 text-xs">{sendError}</p>
            </div>
          ) : null}

          {threadQuery.isLoading ? (
            <div className="grid flex-1 place-items-center text-sm text-slate-900">
              Loading conversation...
            </div>
          ) : (
            <MessageList
              messages={messages}
              streamingText={streamingText}
              isLoading={isSending}
            />
          )}
          <InputBar
            disabled={createThreadMutation.isPending || threadQuery.isLoading}
            mode={mode}
            onModeChange={handleModeChange}
            ragDocuments={ragDocsQuery.data ?? []}
            selectedRagDocId={selectedRagDocId}
            onSelectRagDoc={setSelectedRagDocId}
            onUploadRag={handleUploadRag}
            isUploadingRag={uploadRagMutation.isPending}
            isSending={isSending}
            onSend={handleSend}
          />
        </div>
      </section>
    </main>
  );
}
