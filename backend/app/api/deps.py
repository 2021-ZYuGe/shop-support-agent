from __future__ import annotations

from typing import Annotated

from fastapi import Depends, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import Settings, get_settings
from app.core.security import hash_session_token
from app.db.base import utcnow
from app.db.models import Admin, AdminSession
from app.db.session import get_db

DbSession = Annotated[Session, Depends(get_db)]
AppSettings = Annotated[Settings, Depends(get_settings)]


def get_current_admin(request: Request, db: DbSession, settings: AppSettings) -> Admin:
    token = request.cookies.get(settings.session_cookie_name)
    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="请先登录运营后台",
        )

    token_hash = hash_session_token(token)
    row = db.execute(
        select(AdminSession, Admin)
        .join(Admin, Admin.id == AdminSession.admin_id)
        .where(
            AdminSession.token_hash == token_hash,
            AdminSession.expires_at > utcnow(),
            Admin.is_active.is_(True),
        )
    ).first()
    if row is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="登录已失效，请重新登录",
        )
    return row[1]


CurrentAdmin = Annotated[Admin, Depends(get_current_admin)]
