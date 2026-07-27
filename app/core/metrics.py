from prometheus_client import CONTENT_TYPE_LATEST, Counter, Histogram, generate_latest


HTTP_REQUESTS = Counter(
    "pitwall_http_requests_total",
    "HTTP requests handled by the API.",
    ("method", "route", "status"),
)
HTTP_DURATION = Histogram(
    "pitwall_http_request_duration_seconds",
    "HTTP request duration in seconds.",
    ("method", "route"),
)
TOOL_CALLS = Counter(
    "pitwall_tool_calls_total",
    "Agent tool calls.",
    ("tool", "action", "outcome"),
)
TOOL_DURATION = Histogram(
    "pitwall_tool_duration_seconds",
    "Agent tool execution duration in seconds.",
    ("tool", "action"),
)
LLM_CALLS = Counter(
    "pitwall_llm_calls_total",
    "LLM calls.",
    ("model", "outcome"),
)
LLM_DURATION = Histogram(
    "pitwall_llm_duration_seconds",
    "LLM call duration in seconds.",
    ("model",),
)
RAG_RETRIEVALS = Counter(
    "pitwall_rag_retrievals_total",
    "Regulation retrieval operations.",
    ("query_type", "outcome"),
)
RAG_DURATION = Histogram(
    "pitwall_rag_retrieval_duration_seconds",
    "Regulation retrieval duration in seconds.",
    ("query_type",),
)
UPSTREAM_REQUESTS = Counter(
    "pitwall_upstream_requests_total",
    "Outbound requests to news and race providers.",
    ("provider", "outcome"),
)
UPSTREAM_RETRIES = Counter(
    "pitwall_upstream_retries_total",
    "Retries of idempotent upstream GET requests.",
    ("provider",),
)
UPSTREAM_DURATION = Histogram(
    "pitwall_upstream_request_duration_seconds",
    "Outbound provider request duration in seconds.",
    ("provider",),
)


def render_metrics() -> tuple[bytes, str]:
    return generate_latest(), CONTENT_TYPE_LATEST
