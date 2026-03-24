from fastapi import APIRouter, Depends, HTTPException, status
from authentication.fastapi_users import fastapi_users
from config import settings
from authentication.schemas.user import (
    UserRead,
    UserUpdate,
)
from authentication.fastapi_users import current_active_user, current_active_superuser
from models import User
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from typing import Annotated
from models import db_helper

router = APIRouter(
    prefix=settings.url.users,
    tags=["Users"],
)

# Стандартный роутер от fastapi-users
router.include_router(
    router=fastapi_users.get_users_router(
        UserRead,
        UserUpdate,
    ),
)

# кастомный эндпоинт для суперпользователя
@router.get("/admin/{user_id}", response_model=UserRead)
async def get_user_by_id_admin(
    user_id: int,
    session: Annotated[AsyncSession, Depends(db_helper.session_getter)],
    current_user: Annotated[User, Depends(current_active_superuser)],  # только суперпользователь
):
    """
    Получить пользователя по ID (только для суперпользователей).
    """
    user = await session.get(User, user_id)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    return user