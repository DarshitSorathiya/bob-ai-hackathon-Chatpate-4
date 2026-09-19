from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.exc import IntegrityError

from app.api.deps import CurrentUser, DbSession, require_roles
from app.core.roles import ADMIN
from app.repositories.user_repository import UserRepository
from app.schemas.auth import (
    AuthResponse,
    ForgotPasswordRequest,
    GoogleLoginRequest,
    LoginRequest,
    MessageResponse,
    RegisterRequest,
    RoleUpdateRequest,
    UserResponse,
)
from app.services.auth_service import (
    AuthService,
    EmailAlreadyRegisteredError,
    InvalidCredentialsError,
    GoogleAuthenticationError,
    GoogleNotConfiguredError,
)


router = APIRouter(prefix="/auth", tags=["Authentication"])
auth_service = AuthService()
_user_repo = UserRepository()


@router.post("/register", response_model=AuthResponse, status_code=status.HTTP_201_CREATED)
def register(request: RegisterRequest, db: DbSession) -> AuthResponse:
    try:
        user = auth_service.register(db, request)
    except EmailAlreadyRegisteredError as error:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Email is already registered") from error
    except IntegrityError as error:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Email is already registered") from error

    return AuthResponse(access_token=auth_service.issue_token(user), user=user)


@router.post("/login", response_model=AuthResponse)
def login(request: LoginRequest, db: DbSession) -> AuthResponse:
    try:
        user = auth_service.authenticate(db, request)
    except InvalidCredentialsError as error:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
            headers={"WWW-Authenticate": "Bearer"},
        ) from error

    return AuthResponse(access_token=auth_service.issue_token(user), user=user)


@router.post("/google", response_model=AuthResponse)
def google_login(request: GoogleLoginRequest, db: DbSession) -> AuthResponse:
    try:
        user = auth_service.authenticate_google(db, request.id_token)
    except GoogleNotConfiguredError as error:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Google OAuth is not configured on this server. Set GOOGLE_CLIENT_ID in the environment.",
        ) from error
    except GoogleAuthenticationError as error:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid Google identity token",
        ) from error

    return AuthResponse(access_token=auth_service.issue_token(user), user=user)


@router.get("/me", response_model=UserResponse)
def get_me(current_user: CurrentUser) -> UserResponse:
    return current_user


@router.post("/forgot-password", response_model=MessageResponse)
def forgot_password(_: ForgotPasswordRequest, db: DbSession) -> MessageResponse:
    return MessageResponse(message="If the email is registered, a password reset link will be sent.")


# ─── Admin: user management ───────────────────────────────────────────────────

@router.get(
    "/admin/users",
    response_model=list[UserResponse],
    summary="List all users (admin only)",
    dependencies=[Depends(require_roles(ADMIN))],
)
def list_users(db: DbSession, _admin: CurrentUser, skip: int = 0, limit: int = 200) -> list[UserResponse]:
    users = _user_repo.list_all(db, skip=skip, limit=limit)
    return [UserResponse.model_validate(u) for u in users]


@router.patch(
    "/admin/users/{user_id}/role",
    response_model=UserResponse,
    summary="Change a user's role (admin only)",
    dependencies=[Depends(require_roles(ADMIN))],
)
def update_user_role(user_id: int, body: RoleUpdateRequest, db: DbSession, _admin: CurrentUser) -> UserResponse:
    user = _user_repo.get_by_id(db, user_id)
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    updated = _user_repo.update_role(db, user, body.role)
    return UserResponse.model_validate(updated)
