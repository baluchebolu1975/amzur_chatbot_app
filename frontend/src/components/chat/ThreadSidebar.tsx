import { useState } from "react";
import type { Thread } from "../../types";
import { useChatOperations } from "../../hooks/useChatOperations";

type ThreadSidebarProps = {
  threads: Thread[];
  activeThreadId: string | null;
  onSelectThread: (threadId: string) => void;
  onCreateThread: () => Promise<void>;
};

export function ThreadSidebar({
  threads,
  activeThreadId,
  onSelectThread,
  onCreateThread,
}: ThreadSidebarProps) {
  const { updateThreadMutation, deleteThreadMutation } = useChatOperations();
  const [editingId, setEditingId] = useState<string | null>(null);
  const [editTitle, setEditTitle] = useState("");
  const [deleteConfirmId, setDeleteConfirmId] = useState<string | null>(null);

  const handleEditStart = (thread: Thread) => {
    setEditingId(thread.id);
    setEditTitle(thread.title);
  };

  const handleEditSave = async (threadId: string) => {
    if (editTitle.trim()) {
      await updateThreadMutation.mutateAsync({ threadId, newTitle: editTitle });
      setEditingId(null);
    }
  };

  const handleDeleteConfirm = async (threadId: string) => {
    await deleteThreadMutation.mutateAsync(threadId);
    setDeleteConfirmId(null);
  };

  return (
    <aside className="w-full rounded-2xl border border-slate-200/80 bg-white/85 shadow-lg shadow-slate-900/5 backdrop-blur md:w-72">
      <div className="border-b border-slate-200/80 px-4 py-4">
        <div className="flex items-center justify-between gap-3">
          <h2 className="text-xs font-semibold uppercase tracking-widest text-slate-700">
            💬 Conversation Threads
          </h2>
          <button
            onClick={() => void onCreateThread()}
            className="rounded-lg bg-gradient-to-r from-blue-600 to-cyan-500 px-3 py-1.5 text-xs font-semibold text-white shadow-md shadow-blue-500/30 transition hover:from-blue-700 hover:to-cyan-600 disabled:opacity-50"
            disabled={
              updateThreadMutation.isPending || deleteThreadMutation.isPending
            }
          >
            + New
          </button>
        </div>
      </div>
      <div className="max-h-[260px] overflow-auto md:max-h-[calc(100vh-180px)]">
        {threads.length === 0 ? (
          <div className="p-4 text-center text-sm text-slate-500">
            No conversations yet. Create one to get started!
          </div>
        ) : (
          threads.map((thread) => (
            <div
              key={thread.id}
              className={`group border-l-4 px-4 py-3 transition ${
                thread.id === activeThreadId
                  ? "border-blue-500 bg-blue-50"
                  : "border-transparent hover:bg-slate-50"
              }`}
            >
              {editingId === thread.id ? (
                <div className="space-y-2">
                  <input
                    autoFocus
                    type="text"
                    value={editTitle}
                    onChange={(e) => setEditTitle(e.target.value)}
                    className="w-full rounded-lg border border-slate-200 bg-white px-3 py-2 text-sm text-slate-900 shadow-sm focus:border-blue-400 focus:ring-2 focus:ring-blue-100"
                    onKeyDown={(e) => {
                      if (e.key === "Enter") void handleEditSave(thread.id);
                      if (e.key === "Escape") setEditingId(null);
                    }}
                  />
                  <div className="flex gap-2">
                    <button
                      onClick={() => void handleEditSave(thread.id)}
                      className="flex-1 rounded-lg bg-blue-600 px-3 py-1 text-xs font-semibold text-white hover:bg-blue-700 disabled:opacity-60"
                      disabled={updateThreadMutation.isPending}
                    >
                      Save
                    </button>
                    <button
                      onClick={() => setEditingId(null)}
                      className="flex-1 rounded-lg border border-slate-200 bg-white px-3 py-1 text-xs font-semibold text-slate-700 hover:bg-slate-50"
                    >
                      Cancel
                    </button>
                  </div>
                </div>
              ) : (
                <>
                  <button
                    onClick={() => onSelectThread(thread.id)}
                    className="block w-full text-left"
                  >
                    <p
                      className={`truncate font-medium transition ${
                        thread.id === activeThreadId
                          ? "text-slate-900"
                          : "text-slate-800 group-hover:text-slate-900"
                      }`}
                    >
                      {thread.title}
                    </p>
                    <p className="mt-1 text-xs text-slate-500">
                      {new Date(thread.updated_at).toLocaleString()}
                    </p>
                  </button>

                  <div className="mt-3 hidden gap-2 group-hover:flex">
                    <button
                      onClick={() => handleEditStart(thread)}
                      className="flex-1 rounded-lg border border-slate-200 bg-white px-2 py-1 text-xs font-medium text-slate-600 transition hover:bg-slate-50 hover:text-slate-800 disabled:opacity-50"
                      disabled={
                        updateThreadMutation.isPending ||
                        deleteThreadMutation.isPending
                      }
                      title="Rename thread"
                    >
                      ✎ Edit
                    </button>
                    <button
                      onClick={() => setDeleteConfirmId(thread.id)}
                      className="flex-1 rounded-lg border border-red-200 bg-red-50 px-2 py-1 text-xs font-medium text-red-700 transition hover:bg-red-100 disabled:opacity-50"
                      disabled={
                        updateThreadMutation.isPending ||
                        deleteThreadMutation.isPending
                      }
                      title="Delete thread"
                    >
                      🗑 Delete
                    </button>
                  </div>

                  {deleteConfirmId === thread.id && (
                    <div className="mt-3 space-y-2 rounded-lg border border-red-300 bg-red-50 p-3">
                      <p className="text-xs font-medium text-red-800">
                        Delete this thread?
                      </p>
                      <div className="flex gap-2">
                        <button
                          onClick={() => void handleDeleteConfirm(thread.id)}
                          className="flex-1 rounded-lg bg-red-600 px-2 py-1 text-xs font-semibold text-white hover:bg-red-700 disabled:opacity-50"
                          disabled={deleteThreadMutation.isPending}
                        >
                          Yes, Delete
                        </button>
                        <button
                          onClick={() => setDeleteConfirmId(null)}
                          className="flex-1 rounded-lg border border-slate-200 bg-white px-2 py-1 text-xs font-semibold text-slate-700 hover:bg-slate-50"
                        >
                          Cancel
                        </button>
                      </div>
                    </div>
                  )}
                </>
              )}
            </div>
          ))
        )}
      </div>
    </aside>
  );
}
