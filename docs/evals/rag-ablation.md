# RAG Ablation Protocol

The 42-case clause-level dataset is evaluated with one schema across all retrieval modes:
Recall@1, Recall@5, MRR, section Recall@5, clause hit rate, and strong-evidence rejection rate.

| Mode | Environment | CI policy | Result artifact |
| --- | --- | --- | --- |
| keyword | Local chunk file, no model | Required on every PR | `rag-clause-keyword.json` |
| vector | PostgreSQL with pgvector and embedded chunks | Manual/integration | `rag-clause-vector.json` |
| hybrid | Same database and embedding model as vector | Manual/integration | `rag-clause-hybrid.json` |

Run the comparable jobs after importing and embedding the same regulation snapshot:

```powershell
uv run python scripts/run_rag_eval.py --mode keyword --json-output docs/evals/rag-clause-keyword.json
uv run python scripts/run_rag_eval.py --mode vector --json-output docs/evals/rag-clause-vector.json
uv run python scripts/run_rag_eval.py --mode hybrid --json-output docs/evals/rag-clause-hybrid.json
```

The current deterministic keyword baseline is Recall@1 89.74%, Recall@5 94.87%, MRR
0.9231, clause hit rate 94.87%, and strong-evidence rejection rate 100%. Vector and hybrid
figures must not be recorded until the PostgreSQL corpus contains embeddings generated from
the same `chunks.json`; an empty vector index is a failed setup, not a zero-quality result.
