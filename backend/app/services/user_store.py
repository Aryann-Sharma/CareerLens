from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.app.models.user import User
from backend.app.services.passwords import hash_password, verify_password

DUMMY_PASSWORD_HASH = hash_password("not-a-real-user-password")


def normalize_email(email: str) -> str:
    return email.strip().casefold()


def get_user_by_email(session: Session, email: str) -> User | None:
    return session.scalar(
        select(User).where(User.email == normalize_email(email))
    )


def create_user(session: Session, *, email: str, password: str) -> User:
    user = User(
        email=normalize_email(email),
        password_hash=hash_password(password),
    )
    session.add(user)

    try:
        session.commit()
    except Exception:
        session.rollback()
        raise

    session.refresh(user)
    return user


def authenticate_user(
    session: Session,
    *,
    email: str,
    password: str,
) -> User | None:
    user = get_user_by_email(session, email)
    if user is None:
        verify_password(password, DUMMY_PASSWORD_HASH)
        return None
    if not verify_password(password, user.password_hash):
        return None
    return user
