from __future__ import annotations

import re
from datetime import UTC, datetime
from zoneinfo import ZoneInfo
from typing import Any


class AgentResponseFormatter:
    """Build the final user-facing answer."""

    DISPLAY_TIMEZONE = ZoneInfo("Asia/Shanghai")
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
    FULL_LIST_KEYWORDS = (
        "完整",
        "全部",
        "所有",
        "全体",
        "full",
        "complete",
        "entire",
        "whole",
    )
    DRIVER_ALIASES = {
        "维斯塔潘": "Max Verstappen",
        "max verstappen": "Max Verstappen",
        "verstappen": "Max Verstappen",
        "诺里斯": "Lando Norris",
        "norris": "Lando Norris",
        "勒克莱尔": "Charles Leclerc",
        "leclerc": "Charles Leclerc",
        "拉塞尔": "George Russell",
        "george russell": "George Russell",
        "russell": "George Russell",
        "汉密尔顿": "Lewis Hamilton",
        "hamilton": "Lewis Hamilton",
        "安东内利": "Andrea Kimi Antonelli",
        "antonelli": "Andrea Kimi Antonelli",
        "kimi antonelli": "Andrea Kimi Antonelli",
        "皮亚斯特里": "Oscar Piastri",
        "piastri": "Oscar Piastri",
        "阿隆索": "Fernando Alonso",
        "alonso": "Fernando Alonso",
        "塞恩斯": "Carlos Sainz",
        "sainz": "Carlos Sainz",
    }
    TEAM_ALIASES = {
        "红牛": "Red Bull",
        "red bull": "Red Bull",
        "梅奔": "Mercedes",
        "奔驰": "Mercedes",
        "mercedes": "Mercedes",
        "法拉利": "Ferrari",
        "ferrari": "Ferrari",
        "迈凯伦": "McLaren",
        "mclaren": "McLaren",
        "威廉姆斯": "Williams",
        "williams": "Williams",
        "阿斯顿马丁": "Aston Martin",
        "aston martin": "Aston Martin",
        "哈斯": "Haas",
        "haas": "Haas",
        "索伯": "Audi",
        "奥迪": "Audi",
        "audi": "Audi",
        "alpine": "Alpine",
        "rb": "RB",
    }

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
            article = result.get("article")
            if article:
                summary = article.get("summary") or article.get("content") or "暂无摘要。"
                return f"{article['title']}：{summary}"

            insights = result.get("insights")
            if insights:
                key_points = insights.get("key_points", [])
                if key_points:
                    return f"{insights['summary']} 关键点：{'；'.join(key_points[:3])}。"
                return insights["summary"]

            rules_analysis = result.get("rules_analysis")
            if rules_analysis:
                return rules_analysis["analysis_summary"]

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

        if intent == "strategy":
            return self._build_strategy_answer(result=result)

        if intent == "general":
            response = result.get("response", {})
            answer = response.get("answer")
            if answer:
                return answer
            return "已完成通用问答。"

        return "已完成请求处理。"

    def _build_race_answer(self, *, message: str, result: dict[str, Any]) -> str:
        race = result.get("race")
        if race and race.get("grand_prix_name"):
            action = result.get("action")
            label = "上一站比赛" if action == "get_previous_race" else "下一站比赛"
            return self._format_race_weekend(
                race,
                label=label,
                include_sessions=self._wants_session_times(message),
            )

        standings = result.get("standings", [])
        if standings:
            if self._wants_full_standings(message):
                return self._format_full_standings(standings)

            subject_entry = self._find_subject_entry(message, standings)
            if subject_entry is not None:
                if "driver_name" in subject_entry:
                    return (
                        f"{subject_entry['driver_name']} 当前排在车手积分榜第 {subject_entry['position']} 名，"
                        f"所属车队 {subject_entry['team_name']}，积分 {subject_entry['points']}。"
                    )
                return (
                    f"{subject_entry['team_name']} 当前排在车队积分榜第 {subject_entry['position']} 名，"
                    f"积分 {subject_entry['points']}。"
                )

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
            return self._format_schedule(
                schedule,
                full=self._wants_full_schedule(message),
                include_sessions=self._wants_session_times(message),
            )

        return "已完成比赛信息查询。"

    def _build_strategy_answer(self, *, result: dict[str, Any]) -> str:
        response = result.get("response", {})
        recommendation = response.get("recommendation")
        confidence = response.get("confidence")
        analysis = response.get("analysis", [])

        if recommendation:
            answer = f"策略建议：{recommendation}"
            if confidence:
                answer += f" 置信度：{confidence}。"
            else:
                answer += "。"
            if analysis:
                answer += f" 关键判断：{analysis[0]}"
            return answer

        return "已完成策略分析。"

    def _wants_full_standings(self, message: str) -> bool:
        lowered = message.lower()
        has_standings_keyword = any(token in message for token in ("积分榜", "排名", "standings"))
        return has_standings_keyword and any(token in lowered or token in message for token in self.FULL_LIST_KEYWORDS)

    def _wants_full_schedule(self, message: str) -> bool:
        lowered = message.lower()
        has_schedule_keyword = any(
            token in lowered or token in message
            for token in ("赛历", "赛程", "calendar", "schedule")
        )
        full_tokens = (*self.FULL_LIST_KEYWORDS, "全年", "今年", "赛季", "season")
        return has_schedule_keyword and any(token in lowered or token in message for token in full_tokens)

    def _wants_session_times(self, message: str) -> bool:
        lowered = message.lower()
        return any(
            token in lowered or token in message
            for token in (
                "时间",
                "日期",
                "几点",
                "具体",
                "排位",
                "练习",
                "冲刺",
                "session",
                "sessions",
                "time",
                "date",
                "when",
                "qualifying",
                "practice",
                "sprint",
            )
        )

    def _format_schedule(self, schedule: list[dict[str, Any]], *, full: bool, include_sessions: bool) -> str:
        if not schedule:
            return "当前没有可用的赛历数据。"

        races = schedule if full else schedule[:3]
        title = "当前完整赛历：" if full else "近期赛历："
        lines = [
            self._format_race_summary(race, include_sessions=include_sessions)
            for race in races
        ]
        if not full and len(schedule) > len(races):
            lines.append(f"共获取 {len(schedule)} 场比赛；如需全年列表，请问“完整赛历”。")
        return title + "\n" + "\n".join(lines)

    def _format_race_weekend(self, race: dict[str, Any], *, label: str, include_sessions: bool) -> str:
        details = self._format_race_summary(race, include_sessions=include_sessions)
        return f"{label}：{details}"

    def _format_race_summary(self, race: dict[str, Any], *, include_sessions: bool) -> str:
        round_number = race.get("round_number")
        prefix = f"R{round_number} " if round_number else ""
        location_parts = [
            part
            for part in (race.get("circuit_name"), race.get("country"))
            if part
        ]
        location = f"（{'，'.join(location_parts)}）" if location_parts else ""
        race_time = self._find_session_time(race, "Race") or race.get("end_date")
        race_time_text = self._format_datetime(race_time)
        summary = f"{prefix}{race['grand_prix_name']}{location}，正赛时间 {race_time_text}"

        if include_sessions:
            session_lines = self._format_sessions(race.get("sessions", []))
            if session_lines:
                summary += "；周末安排：" + "；".join(session_lines)

        return summary + "。"

    def _format_sessions(self, sessions: list[dict[str, Any]]) -> list[str]:
        return [
            f"{session['name']} {self._format_datetime(session.get('start_time'))}"
            for session in sessions
            if session.get("name") and session.get("start_time")
        ]

    def _find_session_time(self, race: dict[str, Any], session_name: str) -> Any:
        for session in race.get("sessions", []):
            if session.get("name") == session_name:
                return session.get("start_time")
        return None

    def _format_datetime(self, value: Any) -> str:
        if value is None:
            return "时间未知"
        if isinstance(value, str):
            parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        elif isinstance(value, datetime):
            parsed = value
        else:
            return "时间未知"
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=UTC)
        local_time = parsed.astimezone(self.DISPLAY_TIMEZONE)
        return local_time.strftime("%Y-%m-%d %H:%M CST")

    def _format_full_standings(self, standings: list[dict[str, Any]]) -> str:
        if not standings:
            return "当前没有可用的积分榜数据。"

        if "driver_name" in standings[0]:
            lines = [
                f"{entry['position']}. {entry['driver_name']} | {entry['team_name']} | {entry['points']}分"
                for entry in standings
            ]
            return "当前完整车手积分榜：\n" + "\n".join(lines)

        lines = [
            f"{entry['position']}. {entry['team_name']} | {entry['points']}分"
            for entry in standings
        ]
        return "当前完整车队积分榜：\n" + "\n".join(lines)

    def _find_subject_entry(
        self,
        message: str,
        standings: list[dict[str, Any]],
    ) -> dict[str, Any] | None:
        if not standings:
            return None

        is_driver_standings = "driver_name" in standings[0]
        direct_entry = self._match_entry_in_text(message, standings, is_driver_standings=is_driver_standings)
        if direct_entry is not None:
            return direct_entry

        lines = [line.strip() for line in message.splitlines() if line.strip()]
        if len(lines) <= 1:
            return None

        for line in reversed(lines[:-1]):
            matched = self._match_entry_in_text(line, standings, is_driver_standings=is_driver_standings)
            if matched is not None:
                return matched

        return None

    def _match_entry_in_text(
        self,
        text: str,
        standings: list[dict[str, Any]],
        *,
        is_driver_standings: bool,
    ) -> dict[str, Any] | None:
        normalized = text.lower()

        for entry in standings:
            if is_driver_standings:
                driver_name = entry["driver_name"]
                if driver_name.lower() in normalized:
                    return entry
                if self._matches_alias(normalized, driver_name, self.DRIVER_ALIASES):
                    return entry
            else:
                team_name = entry["team_name"]
                if team_name.lower() in normalized:
                    return entry
                if self._matches_alias(normalized, team_name, self.TEAM_ALIASES):
                    return entry

        return None

    def _matches_alias(
        self,
        normalized_text: str,
        canonical_name: str,
        aliases: dict[str, str],
    ) -> bool:
        canonical_lower = canonical_name.lower()
        for alias, mapped_name in aliases.items():
            if alias in normalized_text and mapped_name.lower() in canonical_lower:
                return True
        return False

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
