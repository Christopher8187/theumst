"""The application's gzip middleware: Starlette's, deciding by the same reading of
Accept-Encoding as the whole-book reads (book_read.accepts_gzip).

Starlette chooses gzip whenever the header holds the letters "gzip", so "gzip;q=0", which
refuses it, still got a gzipped body. For the whole-book reads that meant building gzip twice:
the route decompressed its stored gzip for a client refusing it, and the middleware compressed
the JSON again, about 0.8 s of CPU for Boyce's answer (the check of 0.0.16). Here a client that
refuses gzip gets an uncompressed body from every route, and one that accepts it gets what
Starlette gave it before: a response that already names its Content-Encoding, as a stored
whole-book read does, passes through untouched, and any other is compressed once. A header
allowing only "*" now gets gzip as well, as the whole-book reads already gave it.
"""
from __future__ import annotations

from starlette.datastructures import Headers
from starlette.middleware.gzip import GZipMiddleware as StarletteGZipMiddleware
from starlette.middleware.gzip import GZipResponder, IdentityResponder
from starlette.types import Receive, Scope, Send

from .services.book_read import accepts_gzip


class GZipMiddleware(StarletteGZipMiddleware):
    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":  # pragma: no cover - websockets and lifespan pass through
            await self.app(scope, receive, send)
            return
        if accepts_gzip(Headers(scope=scope).get("Accept-Encoding")):
            responder = GZipResponder(self.app, self.minimum_size, compresslevel=self.compresslevel)
        else:
            responder = IdentityResponder(self.app, self.minimum_size)
        await responder(scope, receive, send)
