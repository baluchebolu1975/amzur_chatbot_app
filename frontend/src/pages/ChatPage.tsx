import { useEffect, useMemo, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useNavigate } from "react-router-dom";

import { InputBar } from "../components/chat/InputBar";
import { MessageList } from "../components/chat/MessageList";
import { ThreadSidebar } from "../components/chat/ThreadSidebar";
import { useAuthActions, useMe } from "../hooks/useAuth";
import {
  createThread,
  getThread,
  listThreads,
  streamMessage,
} from "../lib/api";

export default function ChatPage() {
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const { data: me, isLoading: meLoading, isError: meError } = useMe();
  const { logoutMutation } = useAuthActions();

  const [activeThreadId, setActiveThreadId] = useState<string | null>(null);
  const [streamingText, setStreamingText] = useState("");

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

  const createThreadMutation = useMutation({
    mutationFn: createThread,
    onSuccess: (thread) => {
      queryClient.invalidateQueries({ queryKey: ["threads"] });
      setActiveThreadId(thread.id);
    },
  });

  const sendMutation = useMutation({
    mutationFn: async (message: string) => {
      if (!activeThreadId) {
        throw new Error("No active thread");
      }
      setStreamingText("");
      await streamMessage(activeThreadId, message, (chunk) => {
        setStreamingText((prev) => prev + chunk);
      });
      setStreamingText("");
      await queryClient.invalidateQueries({
        queryKey: ["thread", activeThreadId],
      });
      await queryClient.invalidateQueries({ queryKey: ["threads"] });
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

  if (meLoading) {
    return (
      <div className="grid min-h-screen place-items-center">Loading...</div>
    );
  }

  return (
    <main className="min-h-screen bg-slate-100">
      <header className="flex items-center justify-between border-b border-slate-200 bg-white px-4 py-3">
        <div>
          <h1 className="text-lg font-semibold text-slate-900">
            Amzur AI Chat
          </h1>
          <p className="text-xs text-slate-600">{me?.email}</p>
        </div>
        <button
          onClick={async () => {
            await logoutMutation.mutateAsync();
            navigate("/login");
          }}
          className="rounded-md border border-slate-300 px-3 py-1 text-sm"
        >
          Logout
        </button>
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
          <MessageList messages={messages} streamingText={streamingText} />
          <InputBar
            disabled={!activeThreadId || sendMutation.isPending}
            onSend={async (message) => {
              if (!activeThreadId) {
                const thread =
                  await createThreadMutation.mutateAsync("New Chat");
                setActiveThreadId(thread.id);
                await streamMessage(thread.id, message, (chunk) => {
                  setStreamingText((prev) => prev + chunk);
                });
                setStreamingText("");
                await queryClient.invalidateQueries({
                  queryKey: ["thread", thread.id],
                });
                await queryClient.invalidateQueries({ queryKey: ["threads"] });
                return;
              }
              await sendMutation.mutateAsync(message);
            }}
          />
        </div>
      </section>
    </main>
  );
}
