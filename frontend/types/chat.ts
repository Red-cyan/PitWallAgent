export type AgentResponse = {
  intent: string;
  tool_name: string;
  success: boolean;
  final_answer: string;
  result: Record<string, unknown>;
  error: string | null;
};

export type ConversationTurn = {
  role: "user" | "assistant";
  message: string;
  created_at: string;
  intent?: string | null;
  tool_name?: string | null;
};

export type ChatSessionSummary = {
  session_id: string;
  turn_count: number;
  last_intent?: string | null;
  updated_at: string;
};

export type Citation = {
  document_title: string;
  article?: string | null;
  section?: string | null;
  page?: number | null;
  excerpt?: string | null;
};

export type ChatResponse = {
  session_id: string;
  response: AgentResponse;
  history: ConversationTurn[];
  session: ChatSessionSummary;
};

export type ChatHistoryResponse = {
  session: ChatSessionSummary;
  history: ConversationTurn[];
};

export type ChatSessionListResponse = {
  sessions: ChatSessionSummary[];
};

export type ChatSessionDeleteResponse = {
  session_id: string;
  deleted: boolean;
};

export type StreamEvent =
  | { event: "session_started"; data: { session_id: string } }
  | { event: "message_delta"; data: { session_id: string; delta: string } }
  | { event: "message_completed"; data: ChatResponse }
  | { event: "error"; data: { message: string; error_type?: string } };
