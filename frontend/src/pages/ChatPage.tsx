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
  streamMessage,
  streamMessageWithAttachments,
  streamRagAnswer,
  uploadRagDocument,
} from "../lib/api";

export default function ChatPage() {
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const { data: me, isLoading: meLoading, isError: meError } = useMe();
  const { logoutMutation } = useAuthActions();

  const [activeThreadId, setActiveThreadId] = useState<string | null>(null);
  const [streamingText, setStreamingText] = useState("");
  const [mode, setMode] = useState<PromptMode>("chat");
  const [selectedRagDocId, setSelectedRagDocId] = useState<string | null>(null);
  const [isSending, setIsSending] = useState(false);
  const [sendError, setSendError] = useState<string | null>(null);

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
    queryFn: () => getThread(activeThreadId as string),
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

  const messages = useMemo(
    () => threadQuery.data?.messages ?? [],
    [threadQuery.data?.messages],
  );

  const lightweightHistory = useMemo(
    () =>
      messages
        .filter(
          (msg) => !msg.content.startsWith("![Generated image](data:image"),
        )
        .filter((msg) => msg.content.length < 5000)
        .slice(-10)
        .map((msg) => ({ role: msg.role, content: msg.content })),
    [messages],
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

        setStreamingText("");
        await streamMessage(threadId, message, (chunk) => {
          setStreamingText((prev) => prev + chunk);
        });
        setStreamingText("");
        return;
      }

      if (promptMode === "image") {
        await generateImage(message, threadId);
        return;
      }

      if (!ragDocId) {
        throw new Error("Please select a PDF document for RAG mode.");
      }
      setStreamingText("");
      await streamRagAnswer(
        ragDocId,
        message,
        lightweightHistory,
        (chunk) => {
          setStreamingText((prev) => prev + chunk);
        },
        threadId,
      );
      setStreamingText("");
    },
    [lightweightHistory],
  );

  if (meLoading) {
    return (
      <div className="grid min-h-screen place-items-center">Loading...</div>
    );
  }

  const handleUploadRag = useCallback(
    async (file: File) => {
      setSendError(null);
      await uploadRagMutation.mutateAsync(file);
    },
    [uploadRagMutation],
  );

  const handleSend = useCallback(
    async (message: string, attachments: File[], promptMode: PromptMode, ragDocId: string | null) => {
      setSendError(null);
      setIsSending(true);
      try {
        let threadId = activeThreadId;
        if (!threadId) {
          const thread = await createThreadMutation.mutateAsync("New Chat");
          threadId = thread.id;
          setActiveThreadId(thread.id);
        }

        await sendThroughMode(threadId, message, attachments, promptMode, ragDocId);

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

  return (
    <main className="min-h-screen bg-slate-100">
      <header className="flex items-center justify-between border-b border-slate-200 bg-white px-4 py-3">
        <div>
          <h1 className="text-lg font-semibold text-slate-900">
            Amzur AI Chat
          </h1>
          <p className="text-xs text-slate-600">{me?.email}</p>
        </div>
        <div className="flex gap-3">
          <button
            onClick={async () => {
              await logoutMutation.mutateAsync();
              navigate("/login");
            }}
            className="rounded-md border border-slate-300 px-3 py-1 text-sm"
          >
            Logout
          </button>
        </div>
      </header>

      <section className="flex min-h-[calc(100vh-61px)] flex-col md:flex-row">
        <ThreadSidebar
          threads={threadsQuery.data ?? []}
          activeThreadId={activeThreadId}
          onSelectThread={setActiveThreadId}
          onCreateThread={async () => {
            await createThreadMutation.mutateAsync("New Chat");
          }}
        />

        <div className="flex flex-1 flex-col">
          {sendError ? (
            <div className="border-b border-red-100 bg-red-50 px-4 py-2 text-sm text-red-700">
              {sendError}
            </div>
          ) : null}

          {threadQuery.isLoading ? (
            <div className="grid flex-1 place-items-center text-sm text-slate-500">
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
            onModeChange={setMode}
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
