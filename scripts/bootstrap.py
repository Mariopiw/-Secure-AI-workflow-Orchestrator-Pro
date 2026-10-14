from sqlalchemy import select

from app.core.config import settings
from app.core.security import hash_password
from app.db import SessionLocal
from app.models import User, UserRole


def ensure_user(db, username: str, password: str, role: UserRole):
    existing = db.scalar(select(User).where(User.username == username))
    if existing:
        return
    db.add(
        User(
            username=username,
            password_hash=hash_password(password),
            role=role,
            tenant_id=settings.bootstrap_tenant,
        )
    )


with SessionLocal() as db:
    ensure_user(db, settings.bootstrap_submitter_username, settings.bootstrap_submitter_password, UserRole.SUBMITTER)
    ensure_user(db, settings.bootstrap_approver_username, settings.bootstrap_approver_password, UserRole.APPROVER)
    ensure_user(db, settings.bootstrap_operator_username, settings.bootstrap_operator_password, UserRole.OPERATOR)
    db.commit()
    print("Bootstrap users ready")
