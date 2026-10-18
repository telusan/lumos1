from pydantic import BaseModel, EmailStr
from typing import Optional
from app.models.models import RoleEnum

class LoginRequest(BaseModel):
    school_slug: str
    email: EmailStr
    password: str

class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: dict

class UserOut(BaseModel):
    id: int
    email: str
    full_name: str
    role: RoleEnum
    school_id: int
    preferred_lang: str = "ru"

    class Config:
        from_attributes = True
