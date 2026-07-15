import uuid

from pydantic import BaseModel, EmailStr, Field


class RegisterRequest(BaseModel):
    household_name: str = Field(min_length=1, max_length=255)
    username: str = Field(min_length=3, max_length=64)
    email: EmailStr
    password: str = Field(min_length=8, max_length=255)


class LoginRequest(BaseModel):
    username: str
    password: str


class InviteRequest(BaseModel):
    username: str = Field(min_length=3, max_length=64)
    email: EmailStr
    password: str = Field(min_length=8, max_length=255)


class PasswordResetRequest(BaseModel):
    email: EmailStr


class PasswordResetConfirm(BaseModel):
    token: str
    new_password: str = Field(min_length=8, max_length=255)


class UserResponse(BaseModel):
    id: uuid.UUID
    username: str
    email: EmailStr
    role: str
    household_id: uuid.UUID

    model_config = {"from_attributes": True}
