"use client";

import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";

import { Citation, ConversationTurn } from "@/types/chat";

type MessageBubbleProps = {
  turn: ConversationTurn;
  citations?: Citation[];
  pending?: boolean;
};

export function MessageBubble({
  turn,
  citations = [],
  pending = false,
}: MessageBubbleProps) {
  return (
    <div className={`message-row ${turn.role}`}>
      <article className="message-bubble">
        <div className="message-meta">
          <strong>{turn.role === "user" ? "你" : "PitWall"}</strong>
          {turn.intent ? <span>{turn.intent}</span> : null}
          {turn.tool_name ? <span>{turn.tool_name}</span> : null}
          {pending ? <span>streaming...</span> : null}
        </div>
        <div className="message-markdown">
          {pending && !turn.message ? (
            <span className="typing-indicator">思考中...</span>
          ) : (
            <ReactMarkdown remarkPlugins={[remarkGfm]}>{turn.message}</ReactMarkdown>
          )}
        </div>
        {citations.length > 0 ? (
          <div className="citations">
            {citations.map((citation, index) => (
              <section className="citation-card" key={`${citation.document_title}-${index}`}>
                <div className="citation-title">{citation.document_title}</div>
                <div className="citation-meta">
                  {[citation.article, citation.section, citation.page ? `p.${citation.page}` : null]
                    .filter(Boolean)
                    .join(" · ")}
                </div>
                {citation.excerpt ? (
                  <div className="citation-excerpt">{citation.excerpt}</div>
                ) : null}
              </section>
            ))}
          </div>
        ) : null}
      </article>
    </div>
  );
}
