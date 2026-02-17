from typing import Annotated, Optional, List
from fastapi import APIRouter, Query, HTTPException, Depends, status
from pydantic import BaseModel, Field
from datetime import datetime
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from models import db_helper, Recipe

router = APIRouter(
    tags=["Recipes"],
    prefix="/recipes",
)

# модели для рецептов
class RecipeBase(BaseModel):
    title: str = Field(..., min_length=3, max_length=100, description="Название рецепта")
    description: Optional[str] = Field(None, max_length=500, description="Описание")
    ingredients: List[str] = Field(..., min_items=1, description="Список ингредиентов")
    instructions: str = Field(..., min_length=10, description="Инструкция приготовления")
    cooking_time: int = Field(..., gt=0, description="Время готовки в минутах")
    difficulty: int = Field(..., ge=1, le=5, description="Сложность от 1 до 5")

class RecipeCreate(RecipeBase):
    pass

class RecipeUpdate(BaseModel):
    title: Optional[str] = Field(None, min_length=3, max_length=100)
    description: Optional[str] = Field(None, max_length=500)
    ingredients: Optional[List[str]] = Field(None, min_items=1)
    instructions: Optional[str] = Field(None, min_length=10)
    cooking_time: Optional[int] = Field(None, gt=0)
    difficulty: Optional[int] = Field(None, ge=1, le=5)

class RecipeRead(RecipeBase):
    id: int
    
    class Config:
        from_attributes = True

# CRUD операции
@router.post("", response_model=RecipeRead, status_code=status.HTTP_201_CREATED)
async def store(
    session: Annotated[
        AsyncSession,
        Depends(db_helper.session_getter),
    ],
    recipe_create: RecipeCreate,
):
    """Создать новый рецепт"""
    recipe = Recipe(
        title=recipe_create.title,
        description=recipe_create.description,
        ingredients=recipe_create.ingredients,
        instructions=recipe_create.instructions,
        cooking_time=recipe_create.cooking_time,
        difficulty=recipe_create.difficulty
    )
    session.add(recipe)
    await session.commit()
    await session.refresh(recipe)
    return recipe


@router.get("", response_model=list[RecipeRead])
async def index(
    session: Annotated[
        AsyncSession,
        Depends(db_helper.session_getter),
    ],
    skip: int = Query(0, ge=0, description="Сколько пропустить"),
    limit: int = Query(10, ge=1, le=100, description="Сколько вернуть"),
    difficulty: Optional[int] = Query(None, ge=1, le=5, description="Фильтр по сложности")
):
    """Получить список всех рецептов"""
    stmt = select(Recipe).order_by(Recipe.id)
    
    if difficulty:
        stmt = stmt.where(Recipe.difficulty == difficulty)
    
    stmt = stmt.offset(skip).limit(limit)
    result = await session.scalars(stmt)
    return result.all()

@router.get("/{id}", response_model=RecipeRead)
async def show(
    session: Annotated[
        AsyncSession,
        Depends(db_helper.session_getter),
    ],
    id: int,
):
    """Получить рецепт по ID"""
    recipe = await session.get(Recipe, id)
    if not recipe:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Recipe with id {id} not found"
        )
    return recipe


@router.put("/{id}", response_model=RecipeRead)
async def update(
    session: Annotated[
        AsyncSession,
        Depends(db_helper.session_getter),
    ],
    id: int,
    recipe_update: RecipeUpdate,
):
    """Обновить рецепт"""
    recipe = await session.get(Recipe, id)
    if not recipe:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Recipe with id {id} not found"
        )
    
    update_data = recipe_update.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(recipe, field, value)
    
    await session.commit()
    await session.refresh(recipe)
    return recipe


@router.delete("/{id}", status_code=status.HTTP_204_NO_CONTENT)
async def destroy(
    session: Annotated[
        AsyncSession,
        Depends(db_helper.session_getter),
    ],
    id: int,
):
    """Удалить рецепт"""
    recipe = await session.get(Recipe, id)
    if not recipe:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Recipe with id {id} not found"
        )
    
    await session.delete(recipe)
    await session.commit()
    return None