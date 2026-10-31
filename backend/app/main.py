from __future__ import annotations

import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.router import api_router
from app.core.config import get_settings
from app.core.middleware import SecurityMiddleware
from app.core.pii import PIIRedactingFilter

settings = get_settings()
logging.basicConfig(
    level=getattr(logging, settings.log_level.upper(), logging.INFO),
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
)
if settings.pii_redaction_enabled:
    for handler in logging.getLogger().handlers:
        handler.addFilter(PIIRedactingFilter())

app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    description="电商售后问答 Agent 的后端 API。",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PATCH", "OPTIONS"],
    allow_headers=["Content-Type"],
    max_age=600,
)
app.add_middleware(SecurityMiddleware, settings=settings)

app.include_router(api_router, prefix=settings.api_prefix)


@app.get("/", tags=["system"])
def root() -> dict[str, str]:
    return {
        "name": settings.app_name,
        "version": settings.app_version,
        "docs": "/docs",
        "health": f"{settings.api_prefix}/health",
    }
