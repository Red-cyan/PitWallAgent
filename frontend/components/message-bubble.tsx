"use client";

import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";

import { ConversationTurn } from "@/types/chat";

type MessageBubbleProps = {
  turn: ConversationTurn;
  pending?: boolean;
};

export function MessageBubble({ turn, pending = false }: MessageBubbleProps) {
  return (
    <div className={`message-row ${turn.role}`}>
      <article className="message-bubble">
        <div className="message-meta">
          <strong>{turn.role === "user" ? "You" : "PitWall"}</strong>
          {turn.intent ? <span>{turn.intent}</span> : null}
          {turn.tool_name ? <span>{turn.tool_name}</span> : null}
          {pending ? <span className="live-label">LIVE</span> : null}
        </div>
        <div className="message-markdown">
          {pending && !turn.message ? (
            <span className="typing-indicator">Working...</span>
          ) : (
            <ReactMarkdown remarkPlugins={[remarkGfm]}>{turn.message}</ReactMarkdown>
          )}
        </div>
      </article>
    </div>
  );
}
