# utils/auth.py
import os
import hashlib
from typing import Dict, List, Optional, Tuple

from sqlalchemy.orm import selectinload

from core.db import SessionLocal
from db_models.user import User
from db_models.user_company import UserCompany
from db_models.user_category import UserCategory


def _hash_password(password: str) -> str:
    """Return salted SHA256 hash for storing passwords."""
    salt = os.getenv("PASSWORD_SALT", "")
    return hashlib.sha256(f"{salt}{password}".encode("utf-8")).hexdigest()


def _verify_password(password: str, stored_hash: str) -> bool:
    """Check password against stored hash; allow plain fallback for legacy data."""
    return stored_hash in (password, _hash_password(password))


def _ensure_default_admin(session) -> None:
    """Create default admin if user table is empty, using LOGIN/PASSWORD env or 'admin'/'admin'."""
    exists = session.query(User.id).limit(1).first()
    if exists:
        return
    username = os.getenv("LOGIN", "admin")
    password = os.getenv("PASSWORD", "admin")
    admin = User(
        username=username,
        password_hash=_hash_password(password),
        role="admin",
        is_active=True,
    )
    session.add(admin)
    session.commit()


def authenticate(username: str, password: str) -> Optional[Tuple[Dict, List[int], List[int]]]:
    """Validate credentials and return (user_info, companies, categories) or None."""
    # --- Env-admin login path (does not require DB)
    env_login = os.getenv("LOGIN")
    env_password = os.getenv("PASSWORD")
    if env_login and env_password and username == env_login and password == env_password:
        user_info = {"id": "env_admin", "username": env_login, "role": "admin"}
        return user_info, None, None  # None => без ограничений

    with SessionLocal() as session:
        _ensure_default_admin(session)
        user: User | None = (
            session.query(User)
            .options(
                selectinload(User.company_links),
                selectinload(User.category_links),
            )
            .filter(User.username == username, User.is_active.is_(True))
            .first()
        )
        if not user or not _verify_password(password, user.password_hash):
            return None

        company_ids = [link.up_company_id for link in user.company_links]
        category_ids = [link.category_id for link in user.category_links]
        return _serialize_user(user), company_ids, category_ids


def load_user(user_id: int) -> Optional[Tuple[Dict, List[int], List[int]]]:
    """Load user by id from cookie and return (user_info, companies, categories) or None."""
    # Handle env-admin sideload
    if str(user_id) == "env_admin":
        env_login = os.getenv("LOGIN")
        env_password = os.getenv("PASSWORD")
        if env_login and env_password:
            return {"id": "env_admin", "username": env_login, "role": "admin"}, None, None
        return None

    with SessionLocal() as session:
        user: User | None = (
            session.query(User)
            .options(
                selectinload(User.company_links),
                selectinload(User.category_links),
            )
            .filter(User.id == user_id, User.is_active.is_(True))
            .first()
        )
        if not user:
            return None
        return _serialize_user(user), [l.up_company_id for l in user.company_links], [l.category_id for l in user.category_links]


def _serialize_user(user: User) -> Dict:
    return {"id": user.id, "username": user.username, "role": user.role}
