from pydantic import BaseModel
from typing import Optional


class LoginRequest(BaseModel):
    username: str
    password: str


class UserOut(BaseModel):
    id: int
    username: str
    role: str
    created_at: str
    is_active: int


class UserCreate(BaseModel):
    username: str
    password: str
    role: str


class UserPatch(BaseModel):
    username: Optional[str] = None
    password: Optional[str] = None
    role: Optional[str] = None
    is_active: Optional[int] = None


class MkdirRequest(BaseModel):
    path: str
    name: str


class RenameRequest(BaseModel):
    path: str
    new_name: str


class MoveRequest(BaseModel):
    paths: list[str]
    destination: str


class DeleteRequest(BaseModel):
    paths: list[str]
