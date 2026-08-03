from __future__ import annotations

import base64
import hashlib
import hmac
import os
from datetime import datetime, timedelta, timezone
from typing import Annotated

from fastapi import Cookie, Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError, jwt
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database import SessionLocal, get_db
from app.domain_models import AuditLog, User
from app.settings import get_settings

ALGORITHM = "HS256"
bearer = HTTPBearer(auto_error=False)


def hash_password(password: str, *, iterations: int = 390_000) -> str:
    salt = os.urandom(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, iterations)
    return f"pbkdf2_sha256${iterations}${base64.b64encode(salt).decode()}${base64.b64encode(digest).decode()}"


def verify_password(password: str, encoded: str) -> bool:
    try:
        scheme, raw_iterations, raw_salt, raw_digest = encoded.split("$", 3)
        if scheme != "pbkdf2_sha256":
            return False
        digest = hashlib.pbkdf2_hmac(
            "sha256", password.encode(), base64.b64decode(raw_salt), int(raw_iterations)
        )
        return hmac.compare_digest(digest, base64.b64decode(raw_digest))
    except (ValueError, TypeError):
        return False


def create_token(user: User, token_type: str) -> str:
    settings = get_settings()
    lifetime = (
        timedelta(minutes=settings.access_token_minutes)
        if token_type == "access"
        else timedelta(days=settings.refresh_token_days)
    )
    now = datetime.now(timezone.utc)
    return jwt.encode(
        {"sub": user.id, "username": user.username, "roles": user.roles, "type": token_type, "iat": now, "exp": now + lifetime},
        settings.jwt_secret,
        algorithm=ALGORITHM,
    )


def decode_token(token: str, expected_type: str) -> dict:
    try:
        payload = jwt.decode(token, get_settings().jwt_secret, algorithms=[ALGORITHM])
        if payload.get("type") != expected_type:
            raise JWTError("incorrect token type")
        return payload
    except JWTError as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="登录状态已失效") from exc


def get_current_user(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer)],
    db: Annotated[Session, Depends(get_db)],
) -> User:
    if credentials is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="请先登录")
    payload = decode_token(credentials.credentials, "access")
    user = db.get(User, payload["sub"])
    if user is None or not user.is_active:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="账号不存在或已停用")
    return user


def get_refresh_user(
    refresh_token: Annotated[str | None, Cookie(alias="wildlife_refresh")] = None,
    db: Session = Depends(get_db),
) -> User:
    if not refresh_token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="刷新令牌不存在")
    payload = decode_token(refresh_token, "refresh")
    user = db.get(User, payload["sub"])
    if user is None or not user.is_active:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="账号不存在或已停用")
    return user


def require_roles(*allowed_roles: str):
    def dependency(user: User = Depends(get_current_user)) -> User:
        if not set(user.roles).intersection(allowed_roles):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="没有执行此操作的权限")
        return user

    return dependency


def audit(db: Session, user: User | None, action: str, target_type: str, target_id: str | None, **details: object) -> None:
    db.add(AuditLog(actor_id=user.id if user else None, action=action, target_type=target_type, target_id=target_id, details=details))


def bootstrap_admin() -> None:
    settings = get_settings()
    with SessionLocal() as db:
        existing = db.scalar(select(User).where(User.username == settings.bootstrap_admin_username))
        if existing is not None:
            return
        admin = User(
            username=settings.bootstrap_admin_username,
            display_name="系统管理员",
            password_hash=hash_password(settings.bootstrap_admin_password),
            roles=["system_admin"],
        )
        db.add(admin)
        db.commit()
