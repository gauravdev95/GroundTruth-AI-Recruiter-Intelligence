"""Pydantic request/response schemas for the authentication domain.

These are the authoritative validation layer — the frontend mirrors the
same rules with zod for UX, but the server never trusts the client.
"""

from __future__ import annotations

import re
import uuid
from datetime import datetime

from pydantic import BaseModel, EmailStr, Field, field_validator, model_validator

from src.domains.auth.models import UserRole

_PHONE_RE = re.compile(r"^\+?[1-9]\d{7,14}$")
_UPPER_RE = re.compile(r"[A-Z]")
_LOWER_RE = re.compile(r"[a-z]")
_DIGIT_RE = re.compile(r"\d")
_SPECIAL_RE = re.compile(r"[^\w\s]")


def _validate_password_strength(password: str) -> str:
    if len(password) < 8 or len(password) > 128:
        raise ValueError("Password must be between 8 and 128 characters")
    if not _UPPER_RE.search(password):
        raise ValueError("Password must contain at least one uppercase letter")
    if not _LOWER_RE.search(password):
        raise ValueError("Password must contain at least one lowercase letter")
    if not _DIGIT_RE.search(password):
        raise ValueError("Password must contain at least one number")
    if not _SPECIAL_RE.search(password):
        raise ValueError("Password must contain at least one special character")
    return password


def _normalize_email(email: str) -> str:
    return email.strip().lower()


class CandidateRegisterRequest(BaseModel):
    full_name: str = Field(min_length=2, max_length=200)
    email: EmailStr
    phone_number: str
    password: str
    confirm_password: str
    captcha_token: str = Field(min_length=1)
    accept_terms: bool

    @field_validator("email")
    @classmethod
    def normalize_email(cls, v: str) -> str:
        return _normalize_email(v)

    @field_validator("full_name")
    @classmethod
    def strip_name(cls, v: str) -> str:
        return v.strip()

    @field_validator("phone_number")
    @classmethod
    def validate_phone(cls, v: str) -> str:
        cleaned = v.strip().replace(" ", "").replace("-", "")
        if not _PHONE_RE.match(cleaned):
            raise ValueError("Enter a valid phone number (8-15 digits, optional leading +)")
        return cleaned

    @field_validator("password")
    @classmethod
    def validate_password(cls, v: str) -> str:
        return _validate_password_strength(v)

    @model_validator(mode="after")
    def validate_confirm_password(self) -> "CandidateRegisterRequest":
        if self.password != self.confirm_password:
            raise ValueError("Passwords do not match")
        if not self.accept_terms:
            raise ValueError("You must accept the Terms & Conditions")
        return self


class RecruiterRegisterRequest(BaseModel):
    full_name: str = Field(min_length=2, max_length=200)
    company_name: str = Field(min_length=2, max_length=200)
    company_email: EmailStr
    password: str
    confirm_password: str
    captcha_token: str = Field(min_length=1)
    accept_terms: bool

    @field_validator("company_email")
    @classmethod
    def normalize_email(cls, v: str) -> str:
        return _normalize_email(v)

    @field_validator("full_name", "company_name")
    @classmethod
    def strip_text(cls, v: str) -> str:
        return v.strip()

    @field_validator("password")
    @classmethod
    def validate_password(cls, v: str) -> str:
        return _validate_password_strength(v)

    @model_validator(mode="after")
    def validate_confirm_password(self) -> "RecruiterRegisterRequest":
        if self.password != self.confirm_password:
            raise ValueError("Passwords do not match")
        if not self.accept_terms:
            raise ValueError("You must accept the Terms & Conditions")
        return self


class RegisterResponse(BaseModel):
    message: str
    email: str
    otp_expires_in_seconds: int


class LoginRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=1)
    captcha_token: str = Field(min_length=1)
    remember_me: bool = False
    # Optional since the sign-in page became a single role-agnostic `/login`:
    # the caller no longer declares which lane it thinks the account is in, and
    # the role is read off the issued session instead. Still honoured when
    # supplied — a role-specific entry point (a deep link into the recruiter
    # lane, say) can still assert its expectation and get the explicit
    # "this account is a Candidate" message rather than a silent cross-lane
    # login.
    expected_role: UserRole | None = None

    @field_validator("email")
    @classmethod
    def normalize_email(cls, v: str) -> str:
        return _normalize_email(v)


class UserResponse(BaseModel):
    id: uuid.UUID
    email: str
    full_name: str
    role: UserRole
    is_email_verified: bool

    model_config = {"from_attributes": True}


class AccessTokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int
    user: UserResponse


class VerifyEmailConfirmRequest(BaseModel):
    email: EmailStr
    otp: str = Field(min_length=6, max_length=6, pattern=r"^\d{6}$")

    @field_validator("email")
    @classmethod
    def normalize_email(cls, v: str) -> str:
        return _normalize_email(v)


class VerifyEmailResendRequest(BaseModel):
    email: EmailStr

    @field_validator("email")
    @classmethod
    def normalize_email(cls, v: str) -> str:
        return _normalize_email(v)


class ForgotPasswordRequest(BaseModel):
    email: EmailStr

    @field_validator("email")
    @classmethod
    def normalize_email(cls, v: str) -> str:
        return _normalize_email(v)


class ResetPasswordRequest(BaseModel):
    token: str = Field(min_length=1)
    new_password: str
    confirm_password: str

    @field_validator("new_password")
    @classmethod
    def validate_password(cls, v: str) -> str:
        return _validate_password_strength(v)

    @model_validator(mode="after")
    def validate_confirm_password(self) -> "ResetPasswordRequest":
        if self.new_password != self.confirm_password:
            raise ValueError("Passwords do not match")
        return self


class GenericMessageResponse(BaseModel):
    message: str


class OtpExpiryResponse(BaseModel):
    message: str
    otp_expires_in_seconds: int
