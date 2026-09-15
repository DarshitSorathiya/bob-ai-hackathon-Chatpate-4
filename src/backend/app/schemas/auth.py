from typing import Annotated

from pydantic import AliasChoices, BaseModel, ConfigDict, EmailStr, Field, model_validator


class RegisterRequest(BaseModel):
    full_name: Annotated[str, Field(
        min_length=2,
        max_length=120,
        validation_alias=AliasChoices("fullName", "full_name"),
    )]
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)
    confirm_password: Annotated[str, Field(
        min_length=8,
        max_length=128,
        validation_alias=AliasChoices("confirmPassword", "confirm_password"),
    )]

    @model_validator(mode="after")
    def passwords_match(self) -> "RegisterRequest":
        if self.password != self.confirm_password:
            raise ValueError("Passwords do not match")
        return self


class LoginRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=1, max_length=128)


class GoogleLoginRequest(BaseModel):
    id_token: str = Field(min_length=1)


class ForgotPasswordRequest(BaseModel):
    email: EmailStr


class UserResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    full_name: str
    email: EmailStr
    is_active: bool
    role: str


class AuthResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserResponse


class MessageResponse(BaseModel):
    message: str
