import {
  ChatHistoryResponse,
  ChatResponse,
  ChatSessionDeleteResponse,
  ChatSessionListResponse,
  StreamEvent,
} from "@/types/chat";

const API_BASE_URL =
  process.env.NEXT_PUBLIC_API_BASE_URL?.replace(/\/$/, "") ?? "http://127.0.0.1:8000";

type ChatPayload = {
  message: string;
  session_id?: string | null;
};

export async function listSessions(): Promise<ChatSessionListResponse> {
  const response = await fetch(`${API_BASE_URL}/api/chat/sessions?limit=50`, {
    cache: "no-store",
  });

  if (!response.ok) {
    throw new Error("加载会话列表失败。");
  }

  return response.json();
}

export async function getChatHistory(sessionId: string): Promise<ChatHistoryResponse> {
  const response = await fetch(`${API_BASE_URL}/api/chat/${sessionId}/history`, {
    cache: "no-store",
  });

  if (!response.ok) {
    throw new Error("加载会话历史失败。");
  }

  return response.json();
}

export async function deleteSession(sessionId: string): Promise<ChatSessionDeleteResponse> {
  const response = await fetch(`${API_BASE_URL}/api/chat/${sessionId}`, {
    method: "DELETE",
  });

  if (!response.ok) {
    throw new Error("删除会话失败。");
  }

  return response.json();
}

export async function sendChatMessage(payload: ChatPayload): Promise<ChatResponse> {
  const response = await fetch(`${API_BASE_URL}/api/chat`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify(payload),
  });

  if (!response.ok) {
    throw new Error("发送消息失败。");
  }

  return response.json();
}

export async function streamChatMessage(
  payload: ChatPayload,
  onEvent: (event: StreamEvent) => void,
): Promise<void> {
  const response = await fetch(`${API_BASE_URL}/api/chat/stream`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify(payload),
  });

  if (!response.ok || !response.body) {
    throw new Error("流式连接失败。");
  }

  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";

  while (true) {
    const { value, done } = await reader.read();
    if (done) {
      break;
    }

    buffer += decoder.decode(value, { stream: true });
    const parts = buffer.split("\n\n");
    buffer = parts.pop() ?? "";

    for (const part of parts) {
      const parsed = parseSseEvent(part);
      if (parsed) {
        onEvent(parsed);
      }
    }
  }

  if (buffer.trim()) {
    const parsed = parseSseEvent(buffer);
    if (parsed) {
      onEvent(parsed);
    }
  }
}

function parseSseEvent(rawEvent: string): StreamEvent | null {
  const lines = rawEvent.split("\n");
  const eventLine = lines.find((line) => line.startsWith("event:"));
  const dataLine = lines.find((line) => line.startsWith("data:"));

  if (!eventLine || !dataLine) {
    return null;
  }

  const event = eventLine.replace("event:", "").trim();
  const data = JSON.parse(dataLine.replace("data:", "").trim()) as StreamEvent["data"];

  return { event, data } as StreamEvent;
}
