from __future__ import annotations

import json
import logging
from datetime import UTC, datetime
from typing import Any

from app.config.settings import settings
from app.core.request_context import get_request_id


def configure_logging() -> None:
    """初始化应用日志配置。"""

    level_name = settings.app_log_level.upper()
    level = getattr(logging, level_name, logging.INFO)
    logging.basicConfig(level=level, format="%(message)s")


def log_structured(logger: logging.Logger, event: str, **fields: Any) -> None:
    """输出结构化日志。"""

    payload = {
        "timestamp": datetime.now(UTC).isoformat(),
        "level": logging.getLevelName(logger.getEffectiveLevel()),
        "event": event,
        "request_id": get_request_id(),
        **fields,
    }
    logger.info(json.dumps(payload, ensure_ascii=False, default=str))
