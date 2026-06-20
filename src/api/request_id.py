"""X-Request-ID correlation middleware.

Propagates an inbound ``X-Request-ID`` (or mints one), exposes it on the response,
and binds it to the logging context for the duration of the request — so logs
from any replica can be correlated to a single request (scale-ready tracing).
"""
from __future__ import annotations

import uuid

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request

from src.core.request_context import request_id_var

_HEADER = "X-Request-ID"


class RequestIdMiddleware(BaseHTTPMiddleware):
    """Bind a request id to the log context and echo it on the response."""

    async def dispatch(self, request: Request, call_next):
        rid = request.headers.get(_HEADER) or uuid.uuid4().hex
        token = request_id_var.set(rid)
        try:
            response = await call_next(request)
        finally:
            request_id_var.reset(token)
        response.headers[_HEADER] = rid
        return response


__all__ = ["RequestIdMiddleware"]
