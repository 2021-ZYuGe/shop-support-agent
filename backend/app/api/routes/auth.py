from __future__ import annotations

from datetime import timedelta

from fastapi import APIRouter, HTTPException, Request, Response, status
from sqlalchemy import delete, select

from app.api.deps import AppSettings, CurrentAdmin, DbSession
from app.core.security import (
    hash_password,
    hash_session_token,
    new_session_token,
    verify_password,
)
from app.db.base import utcnow
from app.db.models import Admin, AdminSession
from app.schemas.auth import (
    AdminPublic,
    LoginRequest,
    LoginResponse,
    MessageResponse,
)

router = APIRouter()


@router.post("/login", response_model=LoginResponse)
def login(
    payload: LoginRequest,
    request: Request,
    response: Response,
    db: DbSession,
    settings: AppSettings,
) -> LoginResponse:
    email = payload.email.strip().lower()
    admin = db.scalar(select(Admin).where(Admin.email == email, Admin.is_active.is_(True)))
    if admin is None or not verify_password(payload.password, admin.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="邮箱或密码错误",
        )

    now = utcnow()
    db.execute(
        delete(AdminSession).where(
            AdminSession.admin_id == admin.id,
            AdminSession.expires_at <= now,
        )
    )

    token = new_session_token()
    expires_at = now + timedelta(hours=settings.session_ttl_hours)
    db.add(
        AdminSession(
            admin_id=admin.id,
            token_hash=hash_session_token(token),
            expires_at=expires_at,
            user_agent=(request.headers.get("user-agent") or "")[:255] or None,
        )
    )
    db.commit()

    response.set_cookie(
        key=settings.session_cookie_name,
        value=token,
        max_age=settings.session_ttl_hours * 3600,
        httponly=True,
        secure=settings.session_cookie_secure,
        samesite="lax",
        path="/",
    )
    return LoginResponse(admin=AdminPublic.model_validate(admin), expires_at=expires_at)


@router.post("/logout", response_model=MessageResponse)
def logout(
    request: Request,
    response: Response,
    db: DbSession,
    settings: AppSettings,
) -> MessageResponse:
    token = request.cookies.get(settings.session_cookie_name)
    if token:
        db.execute(
            delete(AdminSession).where(
                AdminSession.token_hash == hash_session_token(token)
            )
        )
        db.commit()
    response.delete_cookie(
        key=settings.session_cookie_name,
        path="/",
        httponly=True,
        secure=settings.session_cookie_secure,
        samesite="lax",
    )
    return MessageResponse(message="已退出登录")


@router.get("/me", response_model=AdminPublic)
def me(admin: CurrentAdmin) -> AdminPublic:
    return AdminPublic.model_validate(admin)
