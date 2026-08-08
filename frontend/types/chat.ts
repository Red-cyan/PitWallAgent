export type AgentResponse = {
  intent: string;
  tool_name: string;
  success: boolean;
  final_answer: string;
  result: Record<string, unknown>;
  error: string | null;
  trace?: AgentTrace;
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
  title: string;
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

export type RetrievedChunk = {
  chunk_id: string;
  content: string;
  score?: number | null;
  document_title?: string;
  article?: string | null;
  section?: string | null;
  page?: number | null;
  heading_path?: string[];
  page_start?: number | null;
  page_end?: number | null;
  clause_id?: string | null;
  article_title?: string | null;
  chunk_type?: string;
  corpus_version?: string | null;
  document_key?: string | null;
  breadcrumb?: string[];
  part_ordinal?: number;
  score_components?: Record<string, number>;
};

export type AgentTrace = {
  intent?: string;
  tool_name?: string;
  action?: string;
  answer_status?: string;
  confidence?: string | null;
  evidence_count?: number;
  source_mode?: string | null;
  query_type?: string | null;
  citations?: Citation[];
  retrieved_chunks?: RetrievedChunk[];
  latency_ms_by_stage?: Record<string, number>;
  request_id?: string;
  stream_mode?: "token" | "buffered";
  plan?: PlanStep[];
  steps?: ExecutedStep[];
  judge_outcomes?: string[];
  judge_outcome?: string;
};

export type PlanStep = {
  output_key?: string;
  intent?: string;
  tool_name?: string;
  action?: string;
};

export type ExecutedStep = {
  step?: number;
  intent?: string;
  tool_name?: string;
  action?: string;
  output_key?: string;
  success?: boolean;
  error?: string | null;
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
  | { event: "session_started"; data: { session_id: string; request_id?: string } }
  | { event: "status"; data: { session_id: string; request_id?: string; message: string; stage?: string } }
  | { event: "message_delta"; data: { session_id: string; request_id?: string; delta: string } }
  | { event: "message_completed"; data: ChatResponse }
  | { event: "error"; data: { message: string; error_type?: string } };

export type RetrievalDebugResponse = {
  question: string;
  normalized_question: string;
  rewritten_queries: string[];
  retrieval_queries: string[];
  extracted_phrases: string[];
  expanded_keywords: string[];
  preferred_sections: string[];
  vector_candidates: RetrievedChunk[];
  keyword_candidates: RetrievedChunk[];
  hybrid_candidates: RetrievedChunk[];
  retrieved_chunks: RetrievedChunk[];
};

export type ActiveCorpus = {
  corpus_version: string;
  parser_version: string;
  embedding_model?: string | null;
  status: string;
  chunk_count: number;
  embedding_count: number;
  created_at: string;
  validation: {
    valid?: boolean;
    clause_missing_rate?: number;
    body_coverage_rate?: number;
    false_header_clauses?: string[];
    errors?: string[];
  };
};
