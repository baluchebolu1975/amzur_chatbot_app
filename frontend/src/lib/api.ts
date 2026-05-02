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
