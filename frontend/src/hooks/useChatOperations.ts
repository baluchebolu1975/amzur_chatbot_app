import { useMutation, useQueryClient } from "@tanstack/react-query";

import { deleteThread, updateThreadTitle } from "../lib/api";

export function useChatOperations() {
  const client = useQueryClient();

  const updateThreadMutation = useMutation({
    mutationFn: ({
      threadId,
      newTitle,
    }: {
      threadId: string;
      newTitle: string;
    }) => updateThreadTitle(threadId, newTitle),
    onSuccess: () => {
      client.invalidateQueries({ queryKey: ["threads"] });
    },
  });

  const deleteThreadMutation = useMutation({
    mutationFn: (threadId: string) => deleteThread(threadId),
    onSuccess: () => {
      client.invalidateQueries({ queryKey: ["threads"] });
    },
  });

  return { updateThreadMutation, deleteThreadMutation };
}
