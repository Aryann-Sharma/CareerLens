import pytest
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from backend.app.models.user import User


def test_user_is_saved(db_session: Session) -> None:
    user = User(
        email="student@example.com",
        password_hash="$argon2id$example",
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)

    assert user.id is not None
    assert user.email == "student@example.com"
    assert user.password_hash == "$argon2id$example"
    assert user.created_at is not None


def test_email_must_be_unique(db_session: Session) -> None:
    db_session.add(
        User(email="student@example.com", password_hash="first-hash")
    )
    db_session.commit()

    db_session.add(
        User(email="student@example.com", password_hash="second-hash")
    )

    with pytest.raises(IntegrityError):
        db_session.commit()

    db_session.rollback()
