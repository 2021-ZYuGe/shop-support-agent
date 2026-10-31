from __future__ import annotations

from starlette.datastructures import Headers, MutableHeaders
from starlette.responses import JSONResponse
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from app.core.config import Settings

_UNSAFE_METHODS = {"POST", "PUT", "PATCH"}
_UPLOAD_PATH = "/api/admin/knowledge/documents"


class SecurityMiddleware:
    """Add baseline security headers and reject oversized JSON requests."""

    def __init__(self, app: ASGIApp, settings: Settings) -> None:
        self.app = app
        self.settings = settings

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        headers = Headers(scope=scope)
        path = scope.get("path", "")
        method = scope.get("method", "GET").upper()
        content_length = headers.get("content-length")
        if (
            method in _UNSAFE_METHODS
            and not path.startswith(_UPLOAD_PATH)
            and content_length
            and content_length.isdigit()
            and int(content_length) > self.settings.max_api_body_bytes
        ):
            response = JSONResponse(
                status_code=413,
                content={"detail": "请求体过大，请缩短内容后重试。"},
            )
            await response(scope, receive, send)
            return

        async def send_with_headers(message: Message) -> None:
            if message["type"] == "http.response.start":
                response_headers = MutableHeaders(scope=message)
                if self.settings.security_headers_enabled:
                    response_headers.setdefault("X-Content-Type-Options", "nosniff")
                    response_headers.setdefault("X-Frame-Options", "DENY")
                    response_headers.setdefault("Referrer-Policy", "no-referrer")
                    response_headers.setdefault(
                        "Permissions-Policy",
                        "camera=(), microphone=(), geolocation=()",
                    )
                    response_headers.setdefault(
                        "Cross-Origin-Opener-Policy", "same-origin"
                    )
                    response_headers.setdefault(
                        "X-Permitted-Cross-Domain-Policies", "none"
                    )
                    if path.startswith("/api/"):
                        response_headers.setdefault(
                            "Content-Security-Policy",
                            "default-src 'none'; frame-ancestors 'none'; base-uri 'none'",
                        )
                    if path.startswith("/api/auth/"):
                        response_headers.setdefault("Cache-Control", "no-store")
                    if (
                        self.settings.is_production
                        or self.settings.session_cookie_secure
                    ):
                        response_headers.setdefault(
                            "Strict-Transport-Security",
                            "max-age=31536000; includeSubDomains",
                        )
            await send(message)

        await self.app(scope, receive, send_with_headers)
