"use client";

import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";

import { AgentTrace, Citation, ConversationTurn, RetrievedChunk } from "@/types/chat";

type MessageBubbleProps = {
  turn: ConversationTurn;
  citations?: Citation[];
  trace?: AgentTrace | null;
  pending?: boolean;
};

export function MessageBubble({
  turn,
  citations = [],
  trace = null,
  pending = false,
}: MessageBubbleProps) {
  const traceCitations = trace?.citations?.length ? trace.citations : citations;
  const retrievedChunks = trace?.retrieved_chunks ?? [];
  const latency = trace?.latency_ms_by_stage?.agent_total ?? trace?.latency_ms_by_stage?.total_before_stream;

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
        {trace && turn.role === "assistant" ? (
          <details className="trace-panel">
            <summary>调试 / 证据</summary>
            <div className="trace-grid">
              <TraceItem label="intent" value={trace.intent} />
              <TraceItem label="tool" value={trace.tool_name} />
              <TraceItem label="action" value={trace.action} />
              <TraceItem label="status" value={trace.answer_status} />
              <TraceItem label="confidence" value={trace.confidence} />
              <TraceItem label="evidence" value={trace.evidence_count?.toString()} />
              <TraceItem label="source" value={trace.source_mode} />
              <TraceItem label="query" value={trace.query_type} />
              <TraceItem label="latency" value={latency !== undefined ? `${latency} ms` : undefined} />
            </div>
            {traceCitations.length > 0 ? (
              <div className="trace-section">
                <div className="trace-section-title">citations</div>
                {traceCitations.map((citation, index) => (
                  <CitationCard citation={citation} index={index} key={`${citation.document_title}-${index}`} />
                ))}
              </div>
            ) : null}
            {retrievedChunks.length > 0 ? (
              <div className="trace-section">
                <div className="trace-section-title">retrieved chunks</div>
                {retrievedChunks.slice(0, 5).map((chunk, index) => (
                  <RetrievedChunkCard chunk={chunk} index={index} key={`${chunk.chunk_id ?? chunk.document_title}-${index}`} />
                ))}
              </div>
            ) : null}
          </details>
        ) : null}
        {!trace && citations.length > 0 ? (
          <div className="citations">
            {citations.map((citation, index) => (
              <CitationCard citation={citation} index={index} key={`${citation.document_title}-${index}`} />
            ))}
          </div>
        ) : null}
      </article>
    </div>
  );
}

function TraceItem({ label, value }: { label: string; value?: string | null }) {
  if (!value) {
    return null;
  }

  return (
    <div className="trace-item">
      <span>{label}</span>
      <strong>{value}</strong>
    </div>
  );
}

function CitationCard({ citation, index }: { citation: Citation; index: number }) {
  return (
    <section className="citation-card" key={`${citation.document_title}-${index}`}>
      <div className="citation-title">{citation.document_title}</div>
      <div className="citation-meta">
        {[citation.article, citation.section, citation.page ? `p.${citation.page}` : null].filter(Boolean).join(" | ")}
      </div>
      {citation.excerpt ? <div className="citation-excerpt">{truncate(citation.excerpt, 260)}</div> : null}
    </section>
  );
}

function RetrievedChunkCard({ chunk, index }: { chunk: RetrievedChunk; index: number }) {
  const title = chunk.document_title ?? `chunk ${index + 1}`;
  const score = typeof chunk.score === "number" ? chunk.score.toFixed(2) : null;

  return (
    <section className="citation-card">
      <div className="citation-title">{title}</div>
      <div className="citation-meta">
        {[chunk.article, chunk.section, chunk.page ? `p.${chunk.page}` : null, score ? `score ${score}` : null]
          .filter(Boolean)
          .join(" | ")}
      </div>
      {chunk.content ? <div className="citation-excerpt">{truncate(chunk.content, 220)}</div> : null}
    </section>
  );
}

function truncate(value: string, maxLength: number) {
  return value.length > maxLength ? `${value.slice(0, maxLength).trim()}...` : value;
}
