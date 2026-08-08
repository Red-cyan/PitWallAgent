import { Activity, BookOpenText, Clock3, Database, GitBranch, ListChecks, X } from "lucide-react";

import { AgentTrace, Citation, RetrievedChunk } from "@/types/chat";

type EvidencePanelProps = {
  trace: AgentTrace | null;
  citations: Citation[];
  openOnMobile?: boolean;
  onClose?: () => void;
};

export function EvidencePanel({ trace, citations, openOnMobile = false, onClose }: EvidencePanelProps) {
  const resolvedCitations = trace?.citations?.length ? trace.citations : citations;
  const chunks = trace?.retrieved_chunks ?? [];
  const latency = trace?.latency_ms_by_stage?.stream_total ?? trace?.latency_ms_by_stage?.agent_total;

  return (
    <aside className="evidence-panel" data-open={openOnMobile} aria-label="Answer evidence">
      <div className="panel-heading">
        <BookOpenText size={17} />
        <h2>Evidence</h2>
        <button className="evidence-close" type="button" title="Close evidence" onClick={onClose}><X size={17} /></button>
      </div>
      {!trace ? (
        <div className="panel-empty">Select or complete an answer to inspect its evidence.</div>
      ) : (
        <>
          <div className="trace-summary">
            <TraceStat icon={<Activity size={14} />} label="Status" value={trace.answer_status ?? "answered"} />
            <TraceStat icon={<Database size={14} />} label="Evidence" value={`${trace.evidence_count ?? 0} chunks`} />
            <TraceStat icon={<Clock3 size={14} />} label="Latency" value={latency ? `${latency} ms` : "n/a"} />
            <TraceStat icon={<Activity size={14} />} label="Stream" value={trace.stream_mode ?? "n/a"} />
          </div>
          <Metadata trace={trace} />
          <AgentSteps trace={trace} />
          {resolvedCitations.length > 0 ? (
            <section className="evidence-section">
              <h3>Citations</h3>
              {resolvedCitations.map((citation, index) => (
                <CitationItem key={`${citation.document_title}-${index}`} citation={citation} />
              ))}
            </section>
          ) : null}
          {chunks.length > 0 ? (
            <section className="evidence-section">
              <h3>Retrieved chunks</h3>
              {chunks.slice(0, 5).map((chunk, index) => (
                <ChunkItem key={`${chunk.chunk_id}-${index}`} chunk={chunk} />
              ))}
            </section>
          ) : null}
        </>
      )}
    </aside>
  );
}

function TraceStat({ icon, label, value }: { icon: React.ReactNode; label: string; value: string }) {
  return <div className="trace-stat"><span>{icon}{label}</span><strong>{value}</strong></div>;
}

function Metadata({ trace }: { trace: AgentTrace }) {
  const values = [trace.intent, trace.tool_name, trace.action, trace.query_type, trace.confidence].filter(Boolean);
  return <div className="metadata-row">{values.map((value) => <span key={value}>{value}</span>)}</div>;
}

function AgentSteps({ trace }: { trace: AgentTrace }) {
  const plan = trace.plan ?? [];
  const steps = trace.steps ?? [];
  if (plan.length === 0 && steps.length === 0) {
    return null;
  }
  return (
    <section className="evidence-section">
      <h3><GitBranch size={13} /> Agent steps</h3>
      {plan.length > 1 ? (
        <div className="agent-plan">
          {plan.map((step, index) => (
            <span key={`${step.output_key ?? index}-${index}`} className="agent-plan-step">
              {index + 1}. {step.tool_name ?? ""}{step.action ? `:${step.action}` : ""}
            </span>
          ))}
        </div>
      ) : null}
      {steps.length > 0 ? (
        <div className="agent-steps">
          {steps.map((step, index) => (
            <article key={`${step.output_key ?? index}-${index}`} className={`agent-step-row ${step.success === false ? "is-error" : ""}`}>
              <span className="agent-step-index">{step.step ?? index + 1}</span>
              <div className="agent-step-body">
                <strong>{step.tool_name ?? ""}{step.action ? `:${step.action}` : ""}</strong>
                <span>{[step.intent, step.output_key].filter(Boolean).join(" · ")}</span>
                {step.success === false ? <small>{step.error ?? "step failed"}</small> : null}
              </div>
            </article>
          ))}
        </div>
      ) : null}
      {trace.judge_outcomes?.length ? (
        <div className="agent-judge">
          <span><ListChecks size={13} /> Judge</span>
          <strong>{trace.judge_outcome ?? trace.judge_outcomes[trace.judge_outcomes.length - 1]}</strong>
        </div>
      ) : null}
    </section>
  );
}

function CitationItem({ citation }: { citation: Citation }) {
  return (
    <article className="evidence-item">
      <strong>{citation.article ?? citation.document_title}</strong>
      <span>{[citation.section, citation.page ? `p.${citation.page}` : null].filter(Boolean).join(" | ")}</span>
      {citation.excerpt ? <p>{truncate(citation.excerpt, 260)}</p> : null}
    </article>
  );
}

function ChunkItem({ chunk }: { chunk: RetrievedChunk }) {
  const pages = chunk.page_start
    ? `p.${chunk.page_start}${chunk.page_end && chunk.page_end !== chunk.page_start ? `-${chunk.page_end}` : ""}`
    : null;
  return (
    <article className="evidence-item">
      <strong>{chunk.clause_id ?? chunk.article ?? chunk.chunk_id}</strong>
      <span>{[chunk.chunk_type, pages, chunk.score?.toFixed(2)].filter(Boolean).join(" | ")}</span>
      {chunk.breadcrumb?.length ? <small>{chunk.breadcrumb.join(" > ")}</small> : null}
      <p>{truncate(chunk.content, 220)}</p>
    </article>
  );
}

function truncate(value: string, maxLength: number) {
  return value.length > maxLength ? `${value.slice(0, maxLength).trim()}...` : value;
}
