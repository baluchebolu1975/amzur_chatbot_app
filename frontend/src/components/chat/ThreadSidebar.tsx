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
    <aside className="w-full border-b border-slate-200 bg-white md:w-72 md:border-b-0 md:border-r">
      <div className="flex items-center justify-between p-4">
        <h2 className="text-sm font-semibold uppercase tracking-wide text-slate-600">
          Threads
        </h2>
        <button
          onClick={() => void onCreateThread()}
          className="rounded-md bg-cyan-700 px-3 py-1 text-sm text-white hover:bg-cyan-800 disabled:opacity-60"
          disabled={
            updateThreadMutation.isPending || deleteThreadMutation.isPending
          }
        >
          New
        </button>
      </div>
      <div className="max-h-[260px] overflow-auto md:max-h-[calc(100vh-120px)]">
        {threads.map((thread) => (
          <div
            key={thread.id}
            className={`group border-l-2 px-4 py-3 ${
              thread.id === activeThreadId
                ? "border-cyan-700 bg-cyan-50"
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
                  className="w-full rounded border border-cyan-600 px-2 py-1 text-sm"
                  onKeyDown={(e) => {
                    if (e.key === "Enter") void handleEditSave(thread.id);
                    if (e.key === "Escape") setEditingId(null);
                  }}
                />
                <div className="flex gap-2">
                  <button
                    onClick={() => void handleEditSave(thread.id)}
                    className="flex-1 rounded bg-cyan-600 px-2 py-1 text-xs text-white hover:bg-cyan-700 disabled:opacity-60"
                    disabled={updateThreadMutation.isPending}
                  >
                    Save
                  </button>
                  <button
                    onClick={() => setEditingId(null)}
                    className="flex-1 rounded bg-slate-300 px-2 py-1 text-xs text-slate-700 hover:bg-slate-400"
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
                    className={`truncate font-medium ${thread.id === activeThreadId ? "text-cyan-900" : ""}`}
                  >
                    {thread.title}
                  </p>
                  <p className="text-xs text-slate-500">
                    {new Date(thread.updated_at).toLocaleString()}
                  </p>
                </button>

                <div className="mt-2 hidden gap-2 group-hover:flex">
                  <button
                    onClick={() => handleEditStart(thread)}
                    className="flex-1 rounded bg-slate-200 px-2 py-1 text-xs text-slate-700 hover:bg-slate-300 disabled:opacity-60"
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
                    className="flex-1 rounded bg-red-100 px-2 py-1 text-xs text-red-700 hover:bg-red-200 disabled:opacity-60"
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
                  <div className="mt-2 space-y-2 rounded bg-red-50 p-2">
                    <p className="text-xs text-red-700">Delete this thread?</p>
                    <div className="flex gap-2">
                      <button
                        onClick={() => void handleDeleteConfirm(thread.id)}
                        className="flex-1 rounded bg-red-600 px-2 py-1 text-xs text-white hover:bg-red-700 disabled:opacity-60"
                        disabled={deleteThreadMutation.isPending}
                      >
                        Yes
                      </button>
                      <button
                        onClick={() => setDeleteConfirmId(null)}
                        className="flex-1 rounded bg-slate-300 px-2 py-1 text-xs text-slate-700 hover:bg-slate-400"
                      >
                        No
                      </button>
                    </div>
                  </div>
                )}
              </>
            )}
          </div>
        ))}
      </div>
    </aside>
  );
}
