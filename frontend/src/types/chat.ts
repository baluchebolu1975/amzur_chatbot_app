import { z } from "zod";

export const threadSchema = z.object({
  id: z.string(),
  title: z.string(),
  created_at: z.string(),
  updated_at: z.string(),
});

export const messageSchema = z.object({
  id: z.string(),
  thread_id: z.string(),
  role: z.string(),
  content: z.string(),
  created_at: z.string(),
});

export const threadDetailSchema = z.object({
  thread: threadSchema,
  messages: z.array(messageSchema),
});

export const chatResponseSchema = z.object({
  thread_id: z.string(),
  user_message: messageSchema,
  assistant_message: messageSchema,
});

export type Thread = z.infer<typeof threadSchema>;
export type Message = z.infer<typeof messageSchema>;
export type ThreadDetail = z.infer<typeof threadDetailSchema>;
export type ChatResponse = z.infer<typeof chatResponseSchema>;
