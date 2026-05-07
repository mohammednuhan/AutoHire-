from __future__ import annotations

import os
from datetime import datetime, timedelta, timezone
from typing import Annotated

import bcrypt
import jwt
from fastapi import APIRouter, Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from database.models import User
from database.session import get_db

router = APIRouter(prefix="/api/auth", tags=["auth"])
security = HTTPBearer(auto_error=False)
ALGORITHM = "HS256"


class LoginRequest(BaseModel):
    username: str
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


def error(status_code: int, code: str, message: str) -> HTTPException:
    return HTTPException(status_code=status_code, detail={"error": code, "message": message})


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt(rounds=12)).decode("utf-8")


def verify_password(password: str, hashed_password: str) -> bool:
    return bcrypt.checkpw(password.encode("utf-8"), hashed_password.encode("utf-8"))


def create_access_token(user_id: str) -> str:
    secret_key = os.environ["SECRET_KEY"]
    payload = {
        "sub": user_id,
        "exp": datetime.now(timezone.utc) + timedelta(hours=24),
    }
    return jwt.encode(payload, secret_key, algorithm=ALGORITHM)


def decode_access_token(token: str) -> str:
    try:
        payload = jwt.decode(token, os.environ["SECRET_KEY"], algorithms=[ALGORITHM])
        return str(payload["sub"])
    except jwt.PyJWTError as exc:
        raise error(401, "UNAUTHORIZED", "Invalid or expired token") from exc


async def get_current_user(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(security)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> User:
    if credentials is None:
        raise error(401, "UNAUTHORIZED", "Missing bearer token")
    user_id = decode_access_token(credentials.credentials)
    user = await db.get(User, user_id)
    if user is None:
        raise error(401, "UNAUTHORIZED", "Invalid user")
    return user


@router.post("/setup", response_model=TokenResponse)
async def setup(payload: LoginRequest, db: Annotated[AsyncSession, Depends(get_db)]) -> TokenResponse:
    user_count = await db.scalar(select(func.count()).select_from(User))
    if user_count:
        raise error(409, "ALREADY_SETUP", "User account already exists")

    user = User(username=payload.username, hashed_password=hash_password(payload.password))
    db.add(user)
    await db.commit()
    await db.refresh(user)
    return TokenResponse(access_token=create_access_token(user.id))


@router.post("/login", response_model=TokenResponse)
async def login(payload: LoginRequest, db: Annotated[AsyncSession, Depends(get_db)]) -> TokenResponse:
    user = await db.scalar(select(User).where(User.username == payload.username))
    if user is None or not verify_password(payload.password, user.hashed_password):
        raise error(401, "INVALID_CREDENTIALS", "Invalid username or password")
    return TokenResponse(access_token=create_access_token(user.id))
