from __future__ import annotations

from datetime import timedelta

from fastapi import APIRouter, Depends, HTTPException, Request, status
from jose import JWTError, jwt
from sqlalchemy.orm import Session

from ..config import get_settings
from ..db import get_db
from ..deps import ensure_active_user, utc_now
from ..models import User, UserSession
from ..schemas import LoginRequest, RefreshRequest, RegisterRequest, TokenResponse, UserRead
from ..security import (
    create_access_token,
    create_refresh_token,
    hash_password,
    hash_token,
    verify_password,
)


router = APIRouter(prefix="/auth", tags=["auth"])
settings = get_settings()


def _request_ip(request: Request) -> str | None:
    return request.client.host if request.client else None


def _create_session_tokens(db: Session, user: User, request: Request) -> tuple[str, str]:
    session = UserSession(
        user_id=user.id,
        refresh_token_hash="pending",
        user_agent=request.headers.get("user-agent"),
        ip_address=_request_ip(request),
        expires_at=utc_now() + timedelta(minutes=settings.refresh_token_expire_minutes),
    )
    db.add(session)
    db.flush()

    access_token = create_access_token(user.id)
    refresh_token = create_refresh_token(user.id, session.id)
    session.refresh_token_hash = hash_token(refresh_token)
    return access_token, refresh_token


def _token_response(user: User, access_token: str, refresh_token: str) -> TokenResponse:
    return TokenResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        expires_in=settings.access_token_expire_minutes * 60,
        user=UserRead.model_validate(user),
    )


@router.post("/register", response_model=TokenResponse)
def register(payload: RegisterRequest, request: Request, db: Session = Depends(get_db)) -> TokenResponse:
    existing = db.query(User).filter(User.email == payload.email, User.deleted_at.is_(None)).first()
    if existing:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Email is already registered")

    user = User(
        email=payload.email,
        full_name=payload.full_name,
        password_hash=hash_password(payload.password),
        is_active=True,
        is_superuser=False,
    )
    db.add(user)
    db.flush()

    access_token, refresh_token = _create_session_tokens(db, user, request)
    db.commit()
    db.refresh(user)
    return _token_response(user, access_token, refresh_token)


@router.post("/login", response_model=TokenResponse)
def login(payload: LoginRequest, request: Request, db: Session = Depends(get_db)) -> TokenResponse:
    user = db.query(User).filter(User.email == payload.email, User.deleted_at.is_(None)).first()
    if not user or not verify_password(payload.password, user.password_hash):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid email or password")
    if not user.is_active:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="User is inactive")

    access_token, refresh_token = _create_session_tokens(db, user, request)
    db.commit()
    db.refresh(user)
    return _token_response(user, access_token, refresh_token)


@router.post("/refresh", response_model=TokenResponse)
def refresh_token(payload: RefreshRequest, request: Request, db: Session = Depends(get_db)) -> TokenResponse:
    try:
        token_data = jwt.decode(
            payload.refresh_token,
            settings.jwt_secret_key,
            algorithms=[settings.jwt_algorithm],
        )
    except JWTError as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid refresh token") from exc

    if token_data.get("type") != "refresh":
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token type")

    session_id = token_data.get("sid")
    user_id = token_data.get("sub")
    if not session_id or not user_id:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Malformed refresh token")

    session = (
        db.query(UserSession)
        .filter(
            UserSession.id == session_id,
            UserSession.user_id == user_id,
            UserSession.deleted_at.is_(None),
            UserSession.revoked_at.is_(None),
        )
        .first()
    )
    if not session or session.expires_at <= utc_now():
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Session expired")
    if session.refresh_token_hash != hash_token(payload.refresh_token):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Refresh token mismatch")

    user = db.query(User).filter(User.id == user_id, User.deleted_at.is_(None)).first()
    if not user or not user.is_active:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found or inactive")

    access_token = create_access_token(user.id)
    refresh_token = create_refresh_token(user.id, session.id)
    session.refresh_token_hash = hash_token(refresh_token)
    session.user_agent = request.headers.get("user-agent")
    session.ip_address = _request_ip(request)
    session.expires_at = utc_now() + timedelta(minutes=settings.refresh_token_expire_minutes)
    db.commit()
    db.refresh(user)
    return _token_response(user, access_token, refresh_token)


@router.post("/logout")
def logout(payload: RefreshRequest, db: Session = Depends(get_db)) -> dict[str, str]:
    hashed = hash_token(payload.refresh_token)
    session = (
        db.query(UserSession)
        .filter(
            UserSession.refresh_token_hash == hashed,
            UserSession.deleted_at.is_(None),
            UserSession.revoked_at.is_(None),
        )
        .first()
    )
    if session:
        session.revoked_at = utc_now()
        db.commit()
    return {"status": "ok", "message": "Logged out"}


@router.get("/me", response_model=UserRead)
def me(user: User = Depends(ensure_active_user)) -> UserRead:
    return UserRead.model_validate(user)
