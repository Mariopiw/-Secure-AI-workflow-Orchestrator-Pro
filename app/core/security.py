from datetime import datetime, timedelta, timezone
import hashlib
import hmac

import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jwt.exceptions import InvalidTokenError
from pwdlib import PasswordHash
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.db import get_db
from app.models import User, UserRole

password_hash = PasswordHash.recommended()
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/token")


def hash_password(password: str) -> str:
    return password_hash.hash(password)


def verify_password(plain: str, hashed: str) -> bool:
    return password_hash.verify(plain, hashed)


def create_access_token(user: User) -> str:
    exp = datetime.now(timezone.utc) + timedelta(minutes=settings.access_token_expire_minutes)
    return jwt.encode(
        {"sub": str(user.id), "tenant_id": user.tenant_id, "role": user.role.value, "exp": exp},
        settings.jwt_secret,
        algorithm=settings.jwt_algorithm,
    )


def authenticate(db: Session, username: str, password: str) -> User | None:
    user = db.scalar(select(User).where(User.username == username, User.is_active.is_(True)))
    if not user or not verify_password(password, user.password_hash):
        return None
    return user


def current_user(token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)) -> User:
    error = HTTPException(status_code=401, detail="Invalid or expired credentials")
    try:
        payload = jwt.decode(token, settings.jwt_secret, algorithms=[settings.jwt_algorithm])
        user_id = int(payload["sub"])
    except (InvalidTokenError, KeyError, TypeError, ValueError):
        raise error
    user = db.get(User, user_id)
    if not user or not user.is_active:
        raise error
    if payload.get("tenant_id") != user.tenant_id or payload.get("role") != user.role.value:
        raise error
    return user


def require_roles(*roles: UserRole):
    def dependency(user: User = Depends(current_user)) -> User:
        if user.role not in roles and user.role != UserRole.ADMIN:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Insufficient role")
        return user
    return dependency


def webhook_signature(timestamp: str, body: bytes) -> str:
    signed = timestamp.encode("utf-8") + b"." + body
    return hmac.new(
        settings.webhook_signing_secret.encode("utf-8"), signed, hashlib.sha256
    ).hexdigest()


def verify_webhook_signature(timestamp: str, body: bytes, signature: str) -> bool:
    return hmac.compare_digest(webhook_signature(timestamp, body), signature)
