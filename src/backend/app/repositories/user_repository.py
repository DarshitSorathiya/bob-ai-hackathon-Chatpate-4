from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.user import User
from app.core.roles import OPERATOR


class UserRepository:
    def get_by_email(self, db: Session, email: str) -> User | None:
        return db.scalar(select(User).where(User.email == email))

    def get_by_id(self, db: Session, user_id: int) -> User | None:
        return db.get(User, user_id)

    def get_by_google_subject(self, db: Session, google_subject: str) -> User | None:
        return db.scalar(select(User).where(User.google_subject == google_subject))

    def create(
        self,
        db: Session,
        *,
        full_name: str,
        email: str,
        password_hash: str | None = None,
        google_subject: str | None = None,
        auth_provider: str = "password",
        role: str = OPERATOR,
    ) -> User:
        user = User(
            full_name=full_name,
            email=email,
            password_hash=password_hash,
            google_subject=google_subject,
            auth_provider=auth_provider,
            role=role,
        )
        db.add(user)
        db.commit()
        db.refresh(user)
        return user
