from pydantic import BaseModel, EmailStr
from typing import Optional

class UserCreate(BaseModel):
    email: EmailStr
    password: str
    full_name: Optional[str] = None

class Token(BaseModel):
    access_token: str
    token_type: str

class TokenData(BaseModel):
    email: Optional[str] = None

class UserOut(BaseModel):
    id: int
    email: EmailStr
    full_name: Optional[str]
    plan: str

    class Config:
        orm_mode = True

class OpenAIRequest(BaseModel):
    prompt: str
    model: str = "gpt-5"
    max_tokens: int = 800
