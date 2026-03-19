from typing import Annotated
from fastapi import APIRouter, Depends, status, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from models import db_helper, Cuisine
from pydantic import BaseModel
from sqlalchemy.exc import IntegrityError
from config import settings

router = APIRouter(tags=["Cuisines"], prefix=settings.url.cuisines)

class CuisineRead(BaseModel):
    id: int
    name: str

class CuisineCreate(BaseModel):
    name: str

@router.post("", response_model=CuisineRead, status_code=status.HTTP_201_CREATED)
async def store(
    session: Annotated[AsyncSession, Depends(db_helper.session_getter)],
    cuisine_create: CuisineCreate,
):
    """
    Создать новую кухню.
    
    - **name**: уникальное название кухни (например, "Итальянская", "Японская")
    """
    cuisine = Cuisine(name=cuisine_create.name)
    session.add(cuisine)
    try:
        await session.commit()
    except IntegrityError:
        await session.rollback()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Cuisine with name '{cuisine_create.name}' already exists"
        )
    await session.refresh(cuisine)
    return cuisine

@router.get("/{id}", response_model=CuisineRead)
async def show(
    session: Annotated[AsyncSession, Depends(db_helper.session_getter)], 
    id: int
):
    """
    Получить информацию о конкретной кухне по ID.
    
    - **id**: уникальный идентификатор кухни
    """
    cuisine = await session.get(Cuisine, id)
    if not cuisine:
        raise HTTPException(status_code=404, detail="Cuisine not found")
    return cuisine

@router.get("", response_model=list[CuisineRead])
async def index(
    session: Annotated[AsyncSession, Depends(db_helper.session_getter)],
    skip: int = Query(0, ge=0, description="Сколько записей пропустить"),
    limit: int = Query(100, ge=1, le=100, description="Сколько записей вернуть"),
):
    """
    Получить список всех кухонь с пагинацией.
    
    - **skip**: количество записей для пропуска (по умолчанию 0)
    - **limit**: максимальное количество записей (по умолчанию 100, максимум 100)
    """
    stmt = select(Cuisine).order_by(Cuisine.id).offset(skip).limit(limit)
    result = await session.scalars(stmt)
    return result.all()


@router.put("/{id}", response_model=CuisineRead)
async def update(
    session: Annotated[AsyncSession, Depends(db_helper.session_getter)],
    id: int,
    cuisine_update: CuisineCreate,
):
    """
    Обновить информацию о кухне.
    
    - **id**: уникальный идентификатор кухни
    - **name**: новое название кухни
    """
    cuisine = await session.get(Cuisine, id)
    if not cuisine:
        raise HTTPException(status_code=404, detail="Cuisine not found")
    cuisine.name = cuisine_update.name
    try:
        await session.commit()
    except IntegrityError:
        await session.rollback()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Cuisine with name '{cuisine_update.name}' already exists"
        )
    await session.refresh(cuisine)
    return cuisine

@router.delete("/{id}", status_code=status.HTTP_204_NO_CONTENT)
async def destroy(
    session: Annotated[AsyncSession, Depends(db_helper.session_getter)], 
    id: int
):
    """
    Удалить кухню по ID.
    
    - **id**: уникальный идентификатор кухни
    """
    cuisine = await session.get(Cuisine, id)
    if not cuisine:
        raise HTTPException(status_code=404, detail="Cuisine not found")
    await session.delete(cuisine)
    await session.commit()
    return None