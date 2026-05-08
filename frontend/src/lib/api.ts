import axios from "axios";
import { z } from "zod";

import {
  authResponseSchema,
  chatResponseSchema,
  threadDetailSchema,
  threadSchema,
  userSchema,
  type AuthResponse,
  type ChatResponse,
  type Thread,
  type ThreadDetail,
  type User,
} from "../types";

const API_BASE_URL =
  import.meta.env.VITE_API_BASE_URL ??
  `${window.location.protocol}//${window.location.hostname}:8000/api`;

const api = axios.create({
  baseURL: API_BASE_URL,
  withCredentials: true,
});

function parseWithSchema<T>(schema: z.ZodSchema<T>, data: unknown): T {
  return schema.parse(data);
}

export async function register(payload: {
  email: string;
  password: string;
  full_name?: string;
}): Promise<AuthResponse> {
  const response = await api.post("/auth/register", payload);
  return parseWithSchema(authResponseSchema, response.data);
}

export async function login(payload: {
  email: string;
  password: string;
}): Promise<AuthResponse> {
  const response = await api.post("/auth/login", payload);
  return parseWithSchema(authResponseSchema, response.data);
}

export async function googleLogin(idToken: string): Promise<AuthResponse> {
  const response = await api.post("/auth/google", { id_token: idToken });
  return parseWithSchema(authResponseSchema, response.data);
}

export async function logout(): Promise<void> {
  await api.post("/auth/logout");
}

export async function getMe(): Promise<User> {
  const response = await api.get("/auth/me");
  return parseWithSchema(userSchema, response.data);
}

export async function createThread(title: string): Promise<Thread> {
  const response = await api.post("/chat/threads", { title });
  return parseWithSchema(threadSchema, response.data);
}

export async function listThreads(): Promise<Thread[]> {
  const response = await api.get("/chat/threads");
  return z.array(threadSchema).parse(response.data);
}

export async function getThread(threadId: string): Promise<ThreadDetail> {
  const response = await api.get(`/chat/threads/${threadId}`);
  return parseWithSchema(threadDetailSchema, response.data);
}

export async function sendMessage(
  threadId: string,
  message: string,
): Promise<ChatResponse> {
  const response = await api.post("/chat/messages", {
    thread_id: threadId,
    message,
  });
  return parseWithSchema(chatResponseSchema, response.data);
}

async function consumeSseResponse(
  response: Response,
  onChunk: (chunk: string) => void,
): Promise<void> {
  if (!response.ok || !response.body) {
    throw new Error("Streaming failed");
  }

  const reader = response.body.getReader();
  const decoder = new TextDecoder("utf-8");

  let buffer = "";

  while (true) {
    const { done, value } = await reader.read();
    if (done) {
      break;
    }

    buffer += decoder.decode(value, { stream: true });
    const events = buffer.split("\n\n");
    buffer = events.pop() ?? "";

    for (const event of events) {
      const lines = event.split("\n");
      for (const line of lines) {
        if (!line.startsWith("data: ")) {
          continue;
        }
        const payload = line.slice(6);
        if (payload === "[DONE]") {
          return;
        }
        onChunk(payload.replace(/\\n/g, "\n"));
      }
    }
  }
}

export async function streamMessage(
  threadId: string,
  message: string,
  onChunk: (chunk: string) => void,
): Promise<void> {
  const response = await fetch(`${API_BASE_URL}/chat/messages/stream`, {
    method: "POST",
    credentials: "include",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify({ thread_id: threadId, message }),
  });

  await consumeSseResponse(response, onChunk);
}

export async function streamMessageWithAttachments(
  threadId: string,
  message: string,
  attachments: File[],
  onChunk: (chunk: string) => void,
): Promise<void> {
  const formData = new FormData();
  formData.append("thread_id", threadId);
  formData.append("message", message);

  for (const file of attachments) {
    formData.append("attachments", file);
  }

  const response = await fetch(
    `${API_BASE_URL}/chat/messages/stream-with-attachments`,
    {
      method: "POST",
      credentials: "include",
      body: formData,
    },
  );

  await consumeSseResponse(response, onChunk);
}

export async function updateThreadTitle(
  threadId: string,
  newTitle: string,
): Promise<Thread> {
  const response = await api.patch(`/chat/threads/${threadId}`, {
    title: newTitle,
  });
  return parseWithSchema(threadSchema, response.data);
}

export async function deleteThread(threadId: string): Promise<void> {
  await api.delete(`/chat/threads/${threadId}`);
}

export async function generateImage(
  prompt: string,
  threadId?: string,
): Promise<{ url: string; prompt: string; model: string }> {
  const response = await api.post("/chat/images/generate", {
    prompt,
    thread_id: threadId,
  });
  return response.data;
}

export interface DbQueryResponse {
  question: string;
  sql: string;
  row_count: number;
  rows: Array<Record<string, unknown>>;
  answer: string;
}

export async function askDatabaseQuestion(
  question: string,
  threadId?: string,
): Promise<DbQueryResponse> {
  const response = await api.post("/db/query", {
    question,
    thread_id: threadId,
  });
  return response.data as DbQueryResponse;
}

// ─── RAG (PDF Chat) ────────────────────────────────────────────────────────

export interface RagDocument {
  id: string;
  filename: string;
  chunk_count: number;
  status: "ready" | "processing" | "failed";
  error_message: string | null;
  created_at: string;
}

export async function uploadRagDocument(file: File): Promise<RagDocument> {
  const formData = new FormData();
  formData.append("file", file);
  const response = await api.post("/rag/documents", formData, {
    headers: { "Content-Type": "multipart/form-data" },
  });
  return response.data as RagDocument;
}

export async function listRagDocuments(): Promise<RagDocument[]> {
  const response = await api.get("/rag/documents");
  return response.data as RagDocument[];
}

export async function deleteRagDocument(docId: string): Promise<void> {
  await api.delete(`/rag/documents/${docId}`);
}

export async function streamRagAnswer(
  docId: string,
  question: string,
  conversationHistory: Array<{ role: string; content: string }>,
  onChunk: (chunk: string) => void,
  threadId?: string,
): Promise<void> {
  const response = await fetch(`${API_BASE_URL}/rag/chat/${docId}`, {
    method: "POST",
    credentials: "include",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      question,
      thread_id: threadId,
      conversation_history: conversationHistory,
    }),
  });

  if (!response.ok || !response.body) {
    const errorText = await response.text().catch(() => "Unknown error");
    throw new Error(`RAG chat failed: ${response.status} ${errorText}`);
  }

  const reader = response.body.getReader();
  const decoder = new TextDecoder("utf-8");

  while (true) {
    const { done, value } = await reader.read();
    if (done) break;
    const chunk = decoder.decode(value, { stream: true });
    if (chunk) onChunk(chunk);
  }
}
