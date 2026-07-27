import { expect, Page, test } from "@playwright/test";

const API_PATTERN = "http://127.0.0.1:8000/**";

async function mockCommonApi(page: Page) {
  await page.route(API_PATTERN, async (route) => {
    const url = new URL(route.request().url());
    if (url.pathname === "/api/chat/sessions") {
      return route.fulfill({ json: { sessions: [] } });
    }
    if (url.pathname === "/api/rules/corpus/active") {
      return route.fulfill({ json: corpusPayload });
    }
    if (url.pathname === "/api/rules/retrieve/debug") {
      return route.fulfill({ json: retrievalPayload });
    }
    if (url.pathname === "/api/chat/stream") {
      const body = [
        sse("session_started", { session_id: "session-e2e", request_id: "req-e2e" }),
        sse("status", { session_id: "session-e2e", request_id: "req-e2e", message: "generating", stage: "generating" }),
        sse("message_delta", { session_id: "session-e2e", request_id: "req-e2e", delta: "B5.6.4 requires the start signal procedure." }),
        sse("message_completed", chatPayload),
      ].join("");
      return route.fulfill({ status: 200, contentType: "text/event-stream", body });
    }
    return route.abort();
  });
}

test.beforeEach(async ({ page }) => {
  await mockCommonApi(page);
});

test("chat streams an answer and exposes evidence", async ({ page }, testInfo) => {
  await page.goto("/");
  await page.getByLabel("Message").fill("What does B5.6.4 require?");
  await page.getByRole("button", { name: "Send" }).click();

  await expect(page.getByText("B5.6.4 requires the start signal procedure.")).toBeVisible();
  if (testInfo.project.name === "mobile") {
    await page.screenshot({ path: testInfo.outputPath("chat-workspace.png"), fullPage: true });
    await page.getByRole("button", { name: "Evidence" }).click();
  }
  await expect(page.getByRole("complementary", { name: "Answer evidence" })).toContainText("B5.6.4");
  await expect(page.getByText("Token stream complete")).toBeVisible();
  await page.screenshot({
    path: testInfo.outputPath(testInfo.project.name === "mobile" ? "evidence-drawer.png" : "chat-workspace.png"),
    fullPage: true,
  });
});

test("RAG Lab shows active corpus and retrieval stages", async ({ page }, testInfo) => {
  await page.goto("/rag");
  await expect(page.getByText("fia-2026-20260625")).toBeVisible();
  await page.getByRole("button", { name: "Retrieve" }).click();

  await expect(page.getByText("B5.6.4", { exact: true })).toBeVisible();
  await page.getByRole("tab", { name: /vector/i }).click();
  await expect(page.getByText("score", { exact: true })).toBeVisible();
  await page.screenshot({ path: testInfo.outputPath("rag-lab.png"), fullPage: true });
});

function sse(event: string, data: unknown) {
  return `event: ${event}\ndata: ${JSON.stringify(data)}\n\n`;
}

const chunk = {
  chunk_id: "corpus:b5.6.4:clause:p01",
  content: "B5.6.4 The start signal procedure applies before the formation lap.",
  score: 63.64,
  document_title: "FIA 2026 F1 Regulations - Section B",
  article: "B5.6.4",
  section: "Section B",
  page: 37,
  page_start: 37,
  page_end: 37,
  heading_path: ["Section B", "B5", "B5.6.4"],
  clause_id: "B5.6.4",
  article_title: "Formation Lap",
  chunk_type: "clause",
  corpus_version: "fia-2026-20260625",
  document_key: "fia-2026-section-b",
  breadcrumb: ["Section B", "B5 TOTAL TIME CLASSIFIED SESSIONS", "B5.6.4"],
  part_ordinal: 1,
  score_components: { keyword_bm25: 12.2, hybrid_score: 14.8, rerank_final: 63.64 },
};

const corpusPayload = {
  corpus_version: "fia-2026-20260625",
  parser_version: "clause-tree-v1",
  embedding_model: "BAAI/bge-m3",
  status: "active",
  chunk_count: 1984,
  embedding_count: 1984,
  created_at: "2026-07-27T00:00:00Z",
  validation: { valid: true, clause_missing_rate: 0, body_coverage_rate: 1, errors: [] },
};

const retrievalPayload = {
  question: "What does B5.6.4 require?",
  normalized_question: "What does B5.6.4 require?",
  rewritten_queries: [],
  retrieval_queries: ["What does B5.6.4 require?"],
  extracted_phrases: [],
  expanded_keywords: ["b5.6.4", "require"],
  preferred_sections: ["Section B"],
  vector_candidates: [chunk],
  keyword_candidates: [chunk],
  hybrid_candidates: [chunk],
  retrieved_chunks: [chunk],
};

const chatPayload = {
  session_id: "session-e2e",
  response: {
    intent: "regulation",
    tool_name: "regulation_tool",
    success: true,
    final_answer: "B5.6.4 requires the start signal procedure.",
    result: { response: { citations: [{ document_title: chunk.document_title, article: "B5.6.4", section: "Section B", page: 37, excerpt: chunk.content }] } },
    error: null,
    trace: {
      intent: "regulation",
      tool_name: "regulation_tool",
      action: "ask",
      answer_status: "answered",
      confidence: "medium",
      evidence_count: 1,
      source_mode: "regulation_rag",
      query_type: "fact_lookup",
      stream_mode: "token",
      request_id: "req-e2e",
      latency_ms_by_stage: { stream_total: 421.5 },
      retrieved_chunks: [chunk],
    },
  },
  history: [
    { role: "user", message: "What does B5.6.4 require?", created_at: "2026-07-27T00:00:00Z" },
    { role: "assistant", message: "B5.6.4 requires the start signal procedure.", created_at: "2026-07-27T00:00:01Z", intent: "regulation", tool_name: "regulation_tool" },
  ],
  session: { session_id: "session-e2e", title: "What does B5.6.4 require?", turn_count: 2, last_intent: "regulation", updated_at: "2026-07-27T00:00:01Z" },
};
