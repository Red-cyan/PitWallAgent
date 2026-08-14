"""Deterministic, bounded observations for tool-calling model context."""

from __future__ import annotations

import json
from typing import Any, cast

TOOL_OBSERVATION_MAX_CHARS = 2400
PREVIOUS_OBSERVATIONS_PREFIX = "Previous tool observations:\n"


def _text(value: Any, limit: int) -> str | None:
    if not isinstance(value, str):
        return None
    value = value.strip()
    return value[:limit] if value else None


def _scalar(value: Any, limit: int = 180) -> str | int | float | bool | None:
    if isinstance(value, str):
        return _text(value, limit)
    if isinstance(value, (int, float, bool)):
        return value
    return None


def _fit(summary: dict[str, Any], max_chars: int = TOOL_OBSERVATION_MAX_CHARS) -> dict[str, Any]:
    """Keep JSON valid while enforcing the hard observation budget."""
    encoded = json.dumps(summary, ensure_ascii=False, separators=(",", ":"))
    while len(encoded) > max_chars:
        strings: list[tuple[dict[str, Any], str, int]] = []
        lists: list[list[Any]] = []

        def collect(value: Any) -> None:
            if isinstance(value, dict):
                for key, item in value.items():
                    if isinstance(item, str):
                        strings.append((value, key, len(item)))
                    else:
                        collect(item)
            elif isinstance(value, list):
                lists.append(value)
                for item in value:
                    collect(item)

        collect(summary)
        if strings:
            owner, key, length = max(strings, key=lambda item: item[2])
            if length > 40:
                owner[key] = owner[key][: max(20, length - max(40, len(encoded) - max_chars))]
            else:
                owner.pop(key, None)
        elif any(lists):
            max(lists, key=len).pop()
        elif len(summary) > 1:
            summary.pop(next(reversed(summary)))
        else:
            break
        encoded = json.dumps(summary, ensure_ascii=False, separators=(",", ":"))
    return summary


def summarize_tool_result(
    payload: dict[str, Any] | None,
    *,
    success: bool = True,
    error: str | None = None,
) -> dict[str, Any]:
    """Extract high-signal fields without mutating or exposing the full payload."""
    payload = payload if isinstance(payload, dict) else {}
    raw_response = payload.get("response")
    response = cast(dict[str, Any], raw_response) if isinstance(raw_response, dict) else {}
    summary: dict[str, Any] = {"success": bool(success)}
    if not success:
        if error:
            summary["error"] = _text(error, 400)
        summary["empty"] = True

    for key in ("answer_status", "confidence", "evidence_count", "source_mode", "query_type", "mode"):
        if response.get(key) is not None:
            value = _scalar(response[key])
            if value is not None:
                summary[key] = value

    for key in ("answer", "final_answer", "summary", "analysis", "recommendation"):
        value = response.get(key) or payload.get(key)
        clipped = _text(value, 500)
        if clipped:
            summary[key] = clipped

    citations = response.get("citations") or payload.get("citations") or []
    if isinstance(citations, list) and citations:
        cited: list[dict[str, Any] | str] = []
        for citation in citations[:5]:
            if isinstance(citation, dict):
                item = {
                    key: value
                    for key in ("document_title", "title", "article", "article_id", "clause", "clause_id", "clause_number", "page", "page_number")
                    if (value := _scalar(citation.get(key))) is not None
                }
                if item:
                    cited.append(item)
            else:
                label = _text(citation, 120)
                if label:
                    cited.append(label)
        if cited:
            summary["citations"] = cited

    chunks = response.get("retrieved_chunks") or payload.get("retrieved_chunks") or payload.get("evidence") or []
    if isinstance(chunks, list) and chunks:
        evidence: list[dict[str, Any]] = []
        for chunk in chunks[:5]:
            if not isinstance(chunk, dict):
                continue
            item: dict[str, Any] = {}
            for key in ("document_title", "title", "article", "clause", "clause_id", "page", "page_number"):
                if chunk.get(key) is not None:
                    value = _scalar(chunk[key])
                    if value is not None:
                        item[key] = value
            excerpt = _text(chunk.get("excerpt") or chunk.get("text") or chunk.get("content"), 220)
            if excerpt:
                item["excerpt"] = excerpt
            if item:
                evidence.append(item)
        if evidence:
            summary["evidence"] = evidence

    articles = payload.get("articles")
    if isinstance(articles, list):
        summary["article_count"] = len(articles)
        titles = [_text(article.get("title"), 180) for article in articles[:5] if isinstance(article, dict)]
        summary["article_titles"] = [title for title in titles if title]
    article = payload.get("article")
    if isinstance(article, dict):
        item: dict[str, Any] = {}
        title = _text(article.get("title"), 180)
        article_summary = _text(article.get("summary") or article.get("content"), 360)
        if title:
            item["title"] = title
        if article_summary:
            item["summary"] = article_summary
        if item:
            summary["article"] = item
    for key in ("insights", "rules_analysis"):
        value = payload.get(key)
        if isinstance(value, dict):
            text = _text(value.get("summary") or value.get("analysis_summary") or value.get("analysis"), 420)
            if text:
                summary[key] = text

    race_result = payload.get("race_result")
    if isinstance(race_result, dict):
        race_summary: dict[str, Any] = {}
        for key in ("grand_prix_name", "round_number", "race_name"):
            if race_result.get(key) is not None:
                value = _scalar(race_result[key])
                if value is not None:
                    race_summary[key] = value
        results = race_result.get("results") or []
        if isinstance(results, list):
            race_summary["results"] = [
                {key: value for key in ("position", "driver_name", "team_name") if isinstance(entry, dict) and (value := _scalar(entry.get(key))) is not None}
                for entry in results[:5]
                if isinstance(entry, dict)
            ]
        summary["race_result"] = race_summary
    for key in ("standings", "schedule"):
        entries = payload.get(key)
        if isinstance(entries, list) and entries:
            summary[key] = [
                {field: value for field in ("position", "driver_name", "team_name", "grand_prix_name", "round_number") if isinstance(entry, dict) and (value := _scalar(entry.get(field))) is not None}
                for entry in entries[:5]
                if isinstance(entry, dict)
            ]
    race: Any = payload.get("race")
    if isinstance(race, dict):
        summary["race"] = {key: value for key in ("grand_prix_name", "race_name", "round_number") if (value := _scalar(race.get(key))) is not None}

    for key in ("facts", "assumptions", "cautions"):
        values = payload.get(key) or response.get(key)
        if isinstance(values, list):
            summary[key] = [str(value)[:220] for value in values[:5]]
    if len(summary) == 1:
        summary["empty"] = True
    return _fit(summary)


def observation_json(payload: dict[str, Any] | None, *, success: bool, error: str | None = None) -> tuple[str, int, int]:
    """Return legal JSON plus serialized observation and source character counts."""
    original = json.dumps(
        {"success": success, "payload": payload or {}, "error": error},
        ensure_ascii=False,
        separators=(",", ":"),
        default=str,
    )
    summary = summarize_tool_result(payload, success=success, error=error)
    encoded = json.dumps(summary, ensure_ascii=False, separators=(",", ":"))
    return encoded, len(encoded), len(original)


def previous_observations_message(contents: list[str]) -> str:
    """Merge prior observation messages into one bounded, valid JSON context."""
    observations: list[dict[str, Any]] = []
    for content in reversed(contents):
        raw = content.removeprefix(PREVIOUS_OBSERVATIONS_PREFIX)
        try:
            parsed = json.loads(raw)
        except (json.JSONDecodeError, TypeError):
            continue
        if isinstance(parsed, dict) and isinstance(parsed.get("observations"), list):
            observations.extend(item for item in parsed["observations"] if isinstance(item, dict))
        elif isinstance(parsed, dict):
            observations.append(parsed)
    compacted = _fit({"observations": observations}, TOOL_OBSERVATION_MAX_CHARS - len(PREVIOUS_OBSERVATIONS_PREFIX))
    return PREVIOUS_OBSERVATIONS_PREFIX + json.dumps(compacted, ensure_ascii=False, separators=(",", ":"))
