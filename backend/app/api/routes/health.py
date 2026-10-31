from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Response, status
from sqlalchemy import text

from app.api.deps import AppSettings, DbSession

router = APIRouter()


@router.get("/health", tags=["system"])
def health(db: DbSession, settings: AppSettings, response: Response) -> dict[str, object]:
    database_status = "connected"
    try:
        db.execute(text("SELECT 1"))
    except Exception:
        database_status = "unavailable"
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE

    return {
        "status": "ok" if database_status == "connected" else "degraded",
        "database": database_status,
        "app": settings.app_name,
        "version": settings.app_version,
        "environment": settings.app_env,
        "integrations": {
            "deepseek": settings.has_deepseek_key,
            "siliconflow": settings.has_siliconflow_key,
        },
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
