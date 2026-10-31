from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.base import UtcSerializationModel


class LoginRequest(BaseModel):
    email: str = Field(min_length=3, max_length=190)
    password: str = Field(min_length=1, max_length=200)


class AdminPublic(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    email: str
    display_name: str


class LoginResponse(UtcSerializationModel):
    admin: AdminPublic
    expires_at: datetime


class MessageResponse(BaseModel):
    message: str
