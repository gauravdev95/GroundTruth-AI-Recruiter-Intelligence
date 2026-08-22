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
    """Student signup. Email and password, and nothing else.

    WHY THIS IS TWO FIELDS AND THE RECRUITER FORM IS SIX

    Every field on a signup form is a place to abandon it, and a student
    arriving from the landing page has not yet been shown anything worth
    six fields of effort. Name, phone and the profile itself are collected
    *inside* onboarding, where the student can already see what they are
    building and each question has visible context.

    A recruiter registering a company is a different transaction — a
    company name and a work email are load-bearing there — so
    `RecruiterRegisterRequest` deliberately keeps its fields.

    WHAT MOVED, AND WHERE IT WENT

    * `full_name`  -> `BasicInfoRequest`, the first onboarding section.
      `User.full_name` is nullable until then, and `User.display_name`
      supplies a neutral fallback for anything (email greetings) that
      needs a name before the student has given one.
    * `phone_number` -> optional profile data, stored `""` until supplied.
      This is the same representation the Google OAuth signup path has
      always written, so it is an existing pattern rather than a new one.
    * `confirm_password` -> a client-side concern. A server that receives
      two copies of a password learns nothing from comparing them that a
      form cannot check on the keystroke, and the redesigned form uses a
      reveal toggle plus live strength feedback instead.
    * `accept_terms` -> the signup control now carries the consent line
      ("By continuing you agree to..."), which is sign-in-wrap rather than
      clickwrap. See the note in `router.py::candidate_register`.
    """

    email: EmailStr
    password: str
    #: Accepted for backwards compatibility with older clients. CAPTCHA is no
    #: longer verified for registration.
    captcha_token: str = ""

    @field_validator("email")
    @classmethod
    def normalize_email(cls, v: str) -> str:
        return _normalize_email(v)

    @field_validator("password")
    @classmethod
    def validate_password(cls, v: str) -> str:
        return _validate_password_strength(v)


class RecruiterRegisterRequest(BaseModel):
    full_name: str = Field(min_length=2, max_length=200)
    company_name: str = Field(min_length=2, max_length=200)
    company_email: EmailStr
    password: str
    confirm_password: str
    #: Accepted for backwards compatibility with older clients. CAPTCHA is no
    #: longer verified for registration.
    captcha_token: str = ""
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


class LoginRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=1)
    #: Accepted for backwards compatibility with older clients. CAPTCHA is no
    #: longer verified for login.
    captcha_token: str = ""
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
    # NULL for a student between signup and their first section save — see
    # `User.full_name`. The client renders `email` in the header until then
    # rather than inventing a name from the address.
    full_name: str | None
    role: UserRole

    model_config = {"from_attributes": True}


class AccessTokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int
    user: UserResponse


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
