import re


class RegulationTextCleaner:
    def clean(self, text: str) -> str:
        cleaned = text.replace("\r", "\n")
        cleaned = cleaned.replace("\u00a0", " ")

        lines = [self._clean_line(line) for line in cleaned.splitlines()]
        lines = [line for line in lines if line]

        return "\n".join(lines).strip()

    def _clean_line(self, line: str) -> str:
        normalized = " ".join(line.split()).strip()
        if not normalized:
            return ""

        upper_line = normalized.upper()
        if upper_line == "SECTION A: GENERAL REGULATORY PROVISIONS":
            return ""

        if normalized.startswith("2026 Formula 1: General Regulatory Provisions"):
            return ""

        if normalized.startswith("Issue 03"):
            return ""

        if normalized.startswith("Status:"):
            return ""

        if normalized.startswith("Date:"):
            return ""

        if normalized.startswith("WMSC approval date:"):
            return ""

        if re.fullmatch(r"A\d+", normalized):
            return ""

        if re.fullmatch(r"\d+", normalized):
            return ""

        return normalized
