import {
  ChatHistoryResponse,
  ChatSessionDeleteResponse,
  ChatSessionListResponse,
  ActiveCorpus,
  RetrievalDebugResponse,
  StreamEvent,
} from "@/types/chat";

const API_BASE_URL =
  process.env.NEXT_PUBLIC_API_BASE_URL?.replace(/\/$/, "") ?? "http://127.0.0.1:8000";

const DEFAULT_TIMEOUT_MS = 30_000;

type ChatPayload = {
  message: string;
  session_id?: string | null;
  user_id?: string | null;
};

async function fetchWithTimeout(
  url: string,
  init: RequestInit = {},
  timeoutMs = DEFAULT_TIMEOUT_MS,
): Promise<Response> {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), timeoutMs);
  try {
    return await fetch(url, { ...init, signal: controller.signal });
  } finally {
    clearTimeout(timer);
  }
}

async function extractErrorMessage(response: Response): Promise<string> {
  try {
    const payload = (await response.json()) as { detail?: string };
    if (typeof payload.detail === "string") return payload.detail;
  } catch {
    // 非 JSON 错误体，回退到状态码文案。
  }
  return `请求失败（HTTP ${response.status}）。`;
}

async function ensureOk(response: Response, fallbackMessage: string): Promise<void> {
  if (response.ok) return;
  const detail = await extractErrorMessage(response);
  throw new Error(detail || fallbackMessage);
}

export async function listSessions(): Promise<ChatSessionListResponse> {
  const response = await fetchWithTimeout(`${API_BASE_URL}/api/chat/sessions?limit=50`, {
    cache: "no-store",
  });
  await ensureOk(response, "加载会话列表失败。");
  return response.json();
}

export async function getChatHistory(sessionId: string): Promise<ChatHistoryResponse> {
  const response = await fetchWithTimeout(
    `${API_BASE_URL}/api/chat/${sessionId}/history`,
    { cache: "no-store" },
  );
  await ensureOk(response, "加载会话历史失败。");
  return response.json();
}

export async function deleteSession(sessionId: string): Promise<ChatSessionDeleteResponse> {
  const response = await fetchWithTimeout(`${API_BASE_URL}/api/chat/${sessionId}`, {
    method: "DELETE",
  });
  await ensureOk(response, "删除会话失败。");
  return response.json();
}

export async function streamChatMessage(
  payload: ChatPayload,
  onEvent: (event: StreamEvent) => void,
  signal?: AbortSignal,
): Promise<void> {
  const response = await fetch(`${API_BASE_URL}/api/chat/stream`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify(payload),
    signal,
  });

  if (!response.ok) {
    await ensureOk(response, "流式连接失败。");
  }
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

export async function getActiveCorpus(): Promise<ActiveCorpus> {
  const response = await fetchWithTimeout(`${API_BASE_URL}/api/rules/corpus/active`, {
    cache: "no-store",
  });
  await ensureOk(response, "Active corpus is unavailable.");
  return response.json();
}

export async function debugRuleRetrieval(
  question: string,
  topK: number,
): Promise<RetrievalDebugResponse> {
  const response = await fetchWithTimeout(`${API_BASE_URL}/api/rules/retrieve/debug`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ question, top_k: topK }),
  });
  await ensureOk(response, "Retrieval request failed.");
  return response.json();
}

export function parseSseEvent(rawEvent: string): StreamEvent | null {
  const lines = rawEvent.split("\n");
  const eventLine = lines.find((line) => line.startsWith("event:"));
  const dataLines = lines.filter((line) => line.startsWith("data:"));

  if (!eventLine || dataLines.length === 0) {
    return null;
  }

  const event = eventLine.replace("event:", "").trim();
  const dataPayload = dataLines.map((line) => line.replace("data:", "").trim()).join("\n");

  let data: StreamEvent["data"];
  try {
    data = JSON.parse(dataPayload) as StreamEvent["data"];
  } catch {
    // 单个畸形数据块不应杀死整个流；跳过该事件，保留其余有效事件。
    return null;
  }

  return { event, data } as StreamEvent;
}
