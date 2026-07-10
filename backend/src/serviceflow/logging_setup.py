"""Structured logging: single-line key=value records, stdlib only (pragmatism directive).

Rule from docs/11_SECURITY_MODEL.md par.3: log ids, never names/phones/PII.
"""

import logging
import sys


class KeyValueFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        base = (
            f"ts={self.formatTime(record, '%Y-%m-%dT%H:%M:%S%z')} "
            f"level={record.levelname} logger={record.name} msg={record.getMessage()!r}"
        )
        request_id = getattr(record, "request_id", None)
        if request_id:
            base += f" request_id={request_id}"
        if record.exc_info:
            base += f" exc={self.formatException(record.exc_info)!r}"
        return base


def setup_logging(level: str = "INFO") -> None:
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(KeyValueFormatter())
    root = logging.getLogger()
    root.handlers = [handler]
    root.setLevel(level.upper())
