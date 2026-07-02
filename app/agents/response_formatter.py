from __future__ import annotations

import re
from typing import Any


class AgentResponseFormatter:
    """统一生成 Agent 的最终回答。"""

    POSITION_PATTERNS = (
        ("第一名", 1),
        ("第一", 1),
        ("第1名", 1),
        ("第1", 1),
        ("1st", 1),
        ("first", 1),
        ("第二名", 2),
        ("第二", 2),
        ("第2名", 2),
        ("第2", 2),
        ("2nd", 2),
        ("second", 2),
        ("第三名", 3),
        ("第三", 3),
        ("第3名", 3),
        ("第3", 3),
        ("3rd", 3),
        ("third", 3),
        ("第四名", 4),
        ("第四", 4),
        ("第4名", 4),
        ("第4", 4),
        ("4th", 4),
        ("fourth", 4),
        ("第五名", 5),
        ("第五", 5),
        ("第5名", 5),
        ("第5", 5),
        ("5th", 5),
        ("fifth", 5),
    )

    def build(
        self,
        *,
        message: str,
        intent: str,
        tool_name: str,
        success: bool,
        result: dict[str, Any],
        error: str | None,
    ) -> str:
        if not success:
            return error or f"{tool_name} 执行失败。"

        if intent == "news":
            articles = result.get("articles", [])
            if articles:
                titles = [article["title"] for article in articles[:3] if "title" in article]
                if titles:
                    return f"已获取最近的 F1 新闻，重点包括：{'；'.join(titles)}。"
            return "已完成新闻查询。"

        if intent == "race":
            return self._build_race_answer(message=message, result=result)

        if intent == "regulation":
            response = result.get("response", {})
            answer = response.get("answer")
            if answer:
                return answer
            return "已完成规则查询。"

        return "已完成请求处理。"

    def _build_race_answer(self, *, message: str, result: dict[str, Any]) -> str:
        race = result.get("race")
        if race and race.get("grand_prix_name"):
            action = result.get("action")
            if action == "get_previous_race":
                return f"上一站比赛是 {race['grand_prix_name']}。"
            return f"下一站比赛是 {race['grand_prix_name']}。"

        standings = result.get("standings", [])
        if standings:
            requested_position = self._extract_requested_position(message)
            entry = self._select_standing_entry(standings, requested_position)
            actual_position = entry.get("position", requested_position)

            if "driver_name" in entry:
                return (
                    f"当前车手积分榜第 {actual_position} 名是 "
                    f"{entry['driver_name']}，所属车队 {entry['team_name']}，积分 {entry['points']}。"
                )
            if "team_name" in entry:
                return (
                    f"当前车队积分榜第 {actual_position} 名是 "
                    f"{entry['team_name']}，积分 {entry['points']}。"
                )

        schedule = result.get("schedule", [])
        if schedule:
            next_round = schedule[0]
            return f"已获取赛历，最近一站是 {next_round['grand_prix_name']}。"

        return "已完成比赛信息查询。"

    def _select_standing_entry(
        self,
        standings: list[dict[str, Any]],
        requested_position: int,
    ) -> dict[str, Any]:
        for entry in standings:
            if entry.get("position") == requested_position:
                return entry

        index = requested_position - 1
        if 0 <= index < len(standings):
            return standings[index]

        return standings[0]

    def _extract_requested_position(self, message: str) -> int:
        lowered = message.lower()
        for pattern, position in self.POSITION_PATTERNS:
            if pattern in lowered or pattern in message:
                return position

        digit_match = re.search(r"第\s*(\d+)\s*名?", message)
        if digit_match:
            return int(digit_match.group(1))

        english_match = re.search(r"\b(\d+)(st|nd|rd|th)\b", lowered)
        if english_match:
            return int(english_match.group(1))

        return 1
