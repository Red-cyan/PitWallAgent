import { describe, expect, it } from "vitest";

import { extractCitations } from "@/lib/chat-utils";
import { ChatResponse } from "@/types/chat";

function buildResponse(citations: unknown): ChatResponse {
  return {
    session_id: "s1",
    response: {
      intent: "regulation",
      tool_name: "regulation_tool",
      success: true,
      final_answer: "answer",
      result: { response: { citations } },
      error: null,
      trace: {},
    },
    history: [],
    session: {
      session_id: "s1",
      title: "title",
      turn_count: 1,
      updated_at: "2026-01-01T00:00:00",
    },
  };
}

describe("extractCitations", () => {
  it("returns an empty array for a null response", () => {
    expect(extractCitations(null)).toEqual([]);
  });

  it("returns an empty array when no citations are present", () => {
    expect(extractCitations(buildResponse(undefined))).toEqual([]);
  });

  it("returns the citations nested under response.result.response", () => {
    const citations = [
      { document_title: "Section B", article: "B5.14.2", page: 7, excerpt: "..." },
    ];
    expect(extractCitations(buildResponse(citations))).toEqual(citations);
  });
});
