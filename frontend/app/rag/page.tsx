"use client";

import { CheckCircle2, Database, Search, SlidersHorizontal } from "lucide-react";
import { useEffect, useMemo, useState } from "react";

import { WorkspaceNav } from "@/components/workspace-nav";
import { debugRuleRetrieval, getActiveCorpus } from "@/services/api";
import { ActiveCorpus, RetrievalDebugResponse, RetrievedChunk } from "@/types/chat";

type Stage = "final" | "keyword" | "vector" | "hybrid";

export default function RagLabPage() {
  const [corpus, setCorpus] = useState<ActiveCorpus | null>(null);
  const [question, setQuestion] = useState("What does B5.6.4 require?");
  const [topK, setTopK] = useState(5);
  const [stage, setStage] = useState<Stage>("final");
  const [result, setResult] = useState<RetrievalDebugResponse | null>(null);
  const [pending, setPending] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    getActiveCorpus().then(setCorpus).catch((reason) => setError(reason instanceof Error ? reason.message : "Corpus unavailable."));
  }, []);

  const chunks = useMemo(() => {
    if (!result) return [];
    if (stage === "keyword") return result.keyword_candidates;
    if (stage === "vector") return result.vector_candidates;
    if (stage === "hybrid") return result.hybrid_candidates;
    return result.retrieved_chunks;
  }, [result, stage]);

  async function handleSubmit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!question.trim() || pending) return;
    setPending(true);
    setError(null);
    try {
      setResult(await debugRuleRetrieval(question.trim(), topK));
      setStage("final");
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Retrieval failed.");
    } finally {
      setPending(false);
    }
  }

  return (
    <div className="app-frame">
      <WorkspaceNav />
      <main className="rag-workspace">
        <header className="rag-header">
          <div><span>Retrieval inspection</span><h1>RAG Lab</h1></div>
          {corpus ? (
            <div className="corpus-state"><CheckCircle2 size={16} /><span>{corpus.corpus_version}</span><strong>{corpus.chunk_count.toLocaleString()} chunks</strong></div>
          ) : <div className="corpus-state muted"><Database size={16} />Corpus unavailable</div>}
        </header>

        <section className="query-band">
          <form className="rag-query" onSubmit={handleSubmit}>
            <label htmlFor="rag-question">Query</label>
            <div className="query-row">
              <input id="rag-question" value={question} onChange={(event) => setQuestion(event.target.value)} />
              <label className="top-k-control"><SlidersHorizontal size={15} /><span>Top K</span>
                <select value={topK} onChange={(event) => setTopK(Number(event.target.value))}>
                  {[3, 5, 8, 10, 15, 20].map((value) => <option key={value} value={value}>{value}</option>)}
                </select>
              </label>
              <button className="primary-button" type="submit" disabled={pending || !question.trim()}><Search size={15} />{pending ? "Running" : "Retrieve"}</button>
            </div>
          </form>
          {corpus ? (
            <div className="corpus-detail">
              <span>Parser <strong>{corpus.parser_version}</strong></span>
              <span>Embeddings <strong>{corpus.embedding_count.toLocaleString()}</strong></span>
              <span>Model <strong>{corpus.embedding_model ?? "none"}</strong></span>
              <span>Coverage <strong>{formatPercent(corpus.validation.body_coverage_rate)}</strong></span>
            </div>
          ) : null}
        </section>

        {error ? <div className="inline-error">{error}</div> : null}
        {result ? (
          <section className="retrieval-output">
            <div className="retrieval-toolbar">
              <div className="stage-tabs" role="tablist" aria-label="Retrieval stage">
                <StageButton stage="final" active={stage} count={result.retrieved_chunks.length} onSelect={setStage} />
                <StageButton stage="keyword" active={stage} count={result.keyword_candidates.length} onSelect={setStage} />
                <StageButton stage="vector" active={stage} count={result.vector_candidates.length} onSelect={setStage} />
                <StageButton stage="hybrid" active={stage} count={result.hybrid_candidates.length} onSelect={setStage} />
              </div>
              <div className="routing-hints">
                {result.preferred_sections.map((section) => <span key={section}>{section}</span>)}
                {result.rewritten_queries.length ? <span>{result.rewritten_queries.length} rewrites</span> : null}
              </div>
            </div>
            <div className="result-list">
              {chunks.length ? chunks.map((chunk, index) => <RetrievalResult chunk={chunk} index={index} key={`${chunk.chunk_id}-${index}`} />) : <div className="panel-empty">No candidates at this stage.</div>}
            </div>
          </section>
        ) : (
          <div className="rag-empty"><Search size={24} /><strong>No retrieval run</strong><span>Submit a query to inspect candidate generation and reranking.</span></div>
        )}
      </main>
    </div>
  );
}

function StageButton({ stage, active, count, onSelect }: { stage: Stage; active: Stage; count: number; onSelect: (stage: Stage) => void }) {
  return <button type="button" role="tab" aria-selected={stage === active} onClick={() => onSelect(stage)}>{stage}<span>{count}</span></button>;
}

function RetrievalResult({ chunk, index }: { chunk: RetrievedChunk; index: number }) {
  const pages = chunk.page_start ? `p.${chunk.page_start}${chunk.page_end && chunk.page_end !== chunk.page_start ? `-${chunk.page_end}` : ""}` : null;
  return (
    <article className="retrieval-result">
      <div className="result-rank">{index + 1}</div>
      <div className="result-body">
        <div className="result-title"><strong>{chunk.clause_id ?? chunk.article ?? "Unnumbered"}</strong><span>{chunk.article_title}</span></div>
        <div className="result-meta">
          {[chunk.section, chunk.chunk_type, pages, chunk.corpus_version].filter(Boolean).map((value) => <span key={value}>{value}</span>)}
        </div>
        {chunk.breadcrumb?.length ? <div className="breadcrumb">{chunk.breadcrumb.join(" > ")}</div> : null}
        <p>{chunk.content}</p>
      </div>
      <div className="score-column"><strong>{chunk.score?.toFixed(2) ?? "-"}</strong><span>score</span>
        {Object.entries(chunk.score_components ?? {}).slice(-3).map(([name, value]) => <small key={name}>{name.replace("rerank_", "")}: {value.toFixed(1)}</small>)}
      </div>
    </article>
  );
}

function formatPercent(value?: number) {
  return typeof value === "number" ? `${(value * 100).toFixed(1)}%` : "n/a";
}
