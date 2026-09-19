from dataclasses import dataclass

from google.auth.transport import requests as google_requests
from google.oauth2 import id_token
from sqlalchemy.orm import Session

from app.core.security import create_access_token, hash_password, verify_password
from app.core.config import get_settings
from app.core.roles import OPERATOR
from app.models.user import User
from app.repositories.user_repository import UserRepository
from app.schemas.auth import LoginRequest, RegisterRequest


class EmailAlreadyRegisteredError(Exception):
    pass


class InvalidCredentialsError(Exception):
    pass


class GoogleAuthenticationError(Exception):
    """Google token verification failed (bad/expired token)."""
    pass


class GoogleNotConfiguredError(Exception):
    """GOOGLE_CLIENT_ID is not set — Google OAuth is disabled on this server."""
    pass


@dataclass
class GoogleProfile:
    subject: str
    email: str
    full_name: str


class AuthService:
    def __init__(self, user_repository: UserRepository | None = None) -> None:
        self.user_repository = user_repository or UserRepository()

    def register(self, db: Session, request: RegisterRequest) -> User:
        email = request.email.lower()
        if self.user_repository.get_by_email(db, email):
            raise EmailAlreadyRegisteredError

        return self.user_repository.create(
            db,
            full_name=request.full_name.strip(),
            email=email,
            password_hash=hash_password(request.password),
            role=request.role,
        )

    def authenticate(self, db: Session, request: LoginRequest) -> User:
        user = self.user_repository.get_by_email(db, request.email.lower())
        if not user or not user.is_active or not user.password_hash or not verify_password(request.password, user.password_hash):
            raise InvalidCredentialsError
        return user

    def authenticate_google(self, db: Session, id_token_value: str) -> User:
        settings = get_settings()
        if not settings.google_client_id:
            raise GoogleNotConfiguredError

        try:
            claims = id_token.verify_oauth2_token(
                id_token_value,
                google_requests.Request(),
                settings.google_client_id,
            )
            profile = GoogleProfile(
                subject=claims["sub"],
                email=claims["email"].lower(),
                full_name=claims.get("name") or claims["email"].split("@")[0],
            )
        except (ValueError, KeyError, TypeError) as error:
            raise GoogleAuthenticationError from error

        user = self.user_repository.get_by_google_subject(db, profile.subject)
        if user:
            return user

        user = self.user_repository.get_by_email(db, profile.email)
        if user:
            user.google_subject = profile.subject
            user.auth_provider = "google"
            db.commit()
            db.refresh(user)
            return user

        return self.user_repository.create(
            db,
            full_name=profile.full_name,
            email=profile.email,
            google_subject=profile.subject,
            auth_provider="google",
            role=OPERATOR,
        )

    def issue_token(self, user: User) -> str:
        return create_access_token(str(user.id))
