import { describe, expect, it } from "vitest";

import { parseSseEvent } from "@/services/api";

describe("parseSseEvent", () => {
  it("returns null for an empty event", () => {
    expect(parseSseEvent("")).toBeNull();
  });

  it("returns null when the data line is missing", () => {
    expect(parseSseEvent("event: status")).toBeNull();
  });

  it("parses a single-line event and payload", () => {
    const event = parseSseEvent('event: status\ndata: {"status":"routing"}');
    expect(event).toEqual({ event: "status", data: { status: "routing" } });
  });

  it("joins multi-line data payloads", () => {
    const event = parseSseEvent('event: message_delta\ndata: {"text":"he\\nllo"}');
    expect(event).toEqual({ event: "message_delta", data: { text: "he\nllo" } });
  });

  it("ignores leading spaces around event and data markers", () => {
    const event = parseSseEvent("event: error\ndata: {\"message\":\"boom\"}");
    expect(event).toEqual({ event: "error", data: { message: "boom" } });
  });

  it("returns null for malformed JSON instead of crashing", () => {
    expect(parseSseEvent("event: status\ndata: {not-json")).toBeNull();
  });
});
