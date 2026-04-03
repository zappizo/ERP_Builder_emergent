from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class LoginRequest(BaseModel):
    email: str
    password: str


class RecordCreateRequest(BaseModel):
    values: dict[str, Any] = Field(default_factory=dict)
    note: str = ""


class RecordActionRequest(BaseModel):
    action: str
    note: str = ""


class AuthUserRead(BaseModel):
    id: str
    name: str
    email: str
    role: str


class LoginResponse(BaseModel):
    user: AuthUserRead
    headers: dict[str, str]
    message: str