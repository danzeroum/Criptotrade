"""Request correlation id shared between the API middleware and logging.

Lives in ``core`` (not ``api``) so the logging config can inject the id without
importing the API layer. The API middleware sets it per request; a logging
filter reads it onto every record.
"""
from __future__ import annotations

import logging
from contextvars import ContextVar

# Default "-" so logs emitted outside a request (startup, the loop) are valid.
request_id_var: ContextVar[str] = ContextVar("request_id", default="-")


class RequestIdLogFilter(logging.Filter):
    """Attach the current request id to every log record as ``request_id``."""

    def filter(self, record: logging.LogRecord) -> bool:
        record.request_id = request_id_var.get()
        return True


__all__ = ["request_id_var", "RequestIdLogFilter"]
