from typing import Annotated
from fastapi import APIRouter, Depends, status, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from models import db_helper, Allergen
from pydantic import BaseModel
from sqlalchemy.exc import IntegrityError
from config import settings

router = APIRouter(tags=["Allergens"], prefix=settings.url.allergens)

class AllergenRead(BaseModel):
    id: int
    name: str

class AllergenCreate(BaseModel):
    name: str

@router.get("", response_model=list[AllergenRead])
async def index(
    session: Annotated[AsyncSession, Depends(db_helper.session_getter)],
    skip: int = Query(0, ge=0, description="Сколько записей пропустить"),
    limit: int = Query(100, ge=1, le=100, description="Сколько записей вернуть"),
):
    """
    Получить список всех аллергенов с пагинацией.
    
    - **skip**: количество записей для пропуска (по умолчанию 0)
    - **limit**: максимальное количество записей (по умолчанию 100, максимум 100)
    """
    stmt = select(Allergen).order_by(Allergen.id).offset(skip).limit(limit)
    result = await session.scalars(stmt)
    return result.all()

@router.post("", response_model=AllergenRead, status_code=status.HTTP_201_CREATED)
async def store(
    session: Annotated[AsyncSession, Depends(db_helper.session_getter)],
    allergen_create: AllergenCreate,
):
    """
    Создать новый аллерген.
    
    - **name**: уникальное название аллергена (например, "Глютен", "Молоко")
    """
    allergen = Allergen(name=allergen_create.name)
    session.add(allergen)
    try:
        await session.commit()
    except IntegrityError:
        await session.rollback()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Allergen with name '{allergen_create.name}' already exists"
        )
    await session.refresh(allergen)
    return allergen

@router.get("/{id}", response_model=AllergenRead)
async def show(
    session: Annotated[AsyncSession, Depends(db_helper.session_getter)], 
    id: int
):
    """
    Получить информацию о конкретном аллергене по ID.
    
    - **id**: уникальный идентификатор аллергена
    """
    allergen = await session.get(Allergen, id)
    if not allergen:
        raise HTTPException(status_code=404, detail="Allergen not found")
    return allergen

@router.put("/{id}", response_model=AllergenRead)
async def update(
    session: Annotated[AsyncSession, Depends(db_helper.session_getter)],
    id: int,
    allergen_update: AllergenCreate,
):
    """
    Обновить информацию об аллергене.
    
    - **id**: уникальный идентификатор аллергена
    - **name**: новое название аллергена
    """
    allergen = await session.get(Allergen, id)
    if not allergen:
        raise HTTPException(status_code=404, detail="Allergen not found")
    allergen.name = allergen_update.name
    try:
        await session.commit()
    except IntegrityError:
        await session.rollback()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Allergen with name '{allergen_update.name}' already exists"
        )
    await session.refresh(allergen)
    return allergen

@router.delete("/{id}", status_code=status.HTTP_204_NO_CONTENT)
async def destroy(
    session: Annotated[AsyncSession, Depends(db_helper.session_getter)], 
    id: int
):
    """
    Удалить аллерген по ID.
    
    - **id**: уникальный идентификатор аллергена
    """
    allergen = await session.get(Allergen, id)
    if not allergen:
        raise HTTPException(status_code=404, detail="Allergen not found")
    await session.delete(allergen)
    await session.commit()
    return None