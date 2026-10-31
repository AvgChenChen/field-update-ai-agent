"""JSON-lines logging. Callers pass metadata via `extra`; message text is never logged."""

from __future__ import annotations

import json
import logging

_STANDARD = set(vars(logging.makeLogRecord({})).keys()) | {"message", "asctime"}


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload = {"level": record.levelname.lower(), "event": record.getMessage()}
        payload.update({k: v for k, v in record.__dict__.items() if k not in _STANDARD})
        return json.dumps(payload, default=str)


def configure_logging(level: int = logging.INFO) -> None:
    logger = logging.getLogger("field_agent")
    if logger.handlers:
        return
    handler = logging.StreamHandler()
    handler.setFormatter(JsonFormatter())
    logger.addHandler(handler)
    logger.setLevel(level)
    logger.propagate = False
