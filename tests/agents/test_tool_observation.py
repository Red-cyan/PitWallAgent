import json

from app.agents.tool_observation import TOOL_OBSERVATION_MAX_CHARS, observation_json, summarize_tool_result


def test_regulation_observation_is_bounded_valid_json_with_evidence_metadata() -> None:
    payload = {
        "response": {
            "answer_status": "answered",
            "confidence": 0.91,
            "evidence_count": 9,
            "answer": "Cars must comply with parc ferme restrictions. " * 100,
            "citations": [
                {"article": f"Article {index}", "clause": f"40.{index}", "page": index}
                for index in range(9)
            ],
            "retrieved_chunks": [
                {
                    "title": f"Sporting Regulations {index}",
                    "clause": f"40.{index}",
                    "page": index,
                    "content": (f"UNIQUE_FULL_CHUNK_{index} " + "regulation text " * 300),
                }
                for index in range(9)
            ],
        }
    }

    encoded, summarized_chars, original_chars = observation_json(payload, success=True)
    observation = json.loads(encoded)

    assert summarized_chars <= TOOL_OBSERVATION_MAX_CHARS
    assert original_chars > summarized_chars
    assert observation["answer_status"] == "answered"
    assert observation["evidence_count"] == 9
    assert len(observation["citations"]) <= 5
    assert len(observation["evidence"]) <= 5
    assert "40.0" in encoded
    assert "UNIQUE_FULL_CHUNK_5" not in encoded


def test_observation_covers_news_race_strategy_and_failure() -> None:
    news = summarize_tool_result(
        {"articles": [{"title": f"Headline {index}"} for index in range(8)]},
    )
    race = summarize_tool_result(
        {"standings": [{"position": index, "driver_name": f"Driver {index}"} for index in range(1, 8)]},
    )
    strategy = summarize_tool_result(
        {"recommendation": "One stop", "facts": [f"Fact {index}" for index in range(8)]},
    )
    failed = summarize_tool_result({}, success=False, error="tool unavailable")

    assert news == {"success": True, "article_count": 8, "article_titles": [f"Headline {index}" for index in range(5)]}
    assert len(race["standings"]) == 5
    assert strategy["recommendation"] == "One stop"
    assert len(strategy["facts"]) == 5
    assert failed == {"success": False, "error": "tool unavailable", "empty": True}
