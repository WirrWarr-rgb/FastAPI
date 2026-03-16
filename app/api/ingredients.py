from typing import Annotated, List
from fastapi import APIRouter, Depends, status, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import selectinload
from models import db_helper, Ingredient, Recipe, RecipeIngredient
from pydantic import BaseModel
from api.recipes import RecipeRead
from sqlalchemy.exc import IntegrityError
from config import settings

router = APIRouter(tags=["Ingredients"], prefix=settings.url.ingredients)

class IngredientRead(BaseModel):
    id: int
    name: str

class IngredientCreate(BaseModel):
    name: str

@router.get("", response_model=list[IngredientRead])
async def index(
    session: Annotated[AsyncSession, Depends(db_helper.session_getter)],
    skip: int = Query(0, ge=0, description="Сколько записей пропустить"),
    limit: int = Query(100, ge=1, le=100, description="Сколько записей вернуть"),
):
    """
    Получить список всех ингредиентов с пагинацией.
    
    - **skip**: количество записей для пропуска (по умолчанию 0)
    - **limit**: максимальное количество записей (по умолчанию 100, максимум 100)
    """
    stmt = select(Ingredient).order_by(Ingredient.id).offset(skip).limit(limit)
    result = await session.scalars(stmt)
    return result.all()

@router.post("", response_model=IngredientRead, status_code=status.HTTP_201_CREATED)
async def store(
    session: Annotated[AsyncSession, Depends(db_helper.session_getter)],
    ingredient_create: IngredientCreate,
):
    """
    Создать новый ингредиент.
    
    - **name**: уникальное название ингредиента (например, "Мука", "Сахар")
    """
    ingredient = Ingredient(name=ingredient_create.name)
    session.add(ingredient)
    try:
        await session.commit()
    except IntegrityError:
        await session.rollback()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Ingredient with name '{ingredient_create.name}' already exists"
        )
    await session.refresh(ingredient)
    return ingredient

@router.get("/{id}", response_model=IngredientRead)
async def show(
    session: Annotated[AsyncSession, Depends(db_helper.session_getter)], 
    id: int
):
    """
    Получить информацию о конкретном ингредиенте по ID.
    
    - **id**: уникальный идентификатор ингредиента
    """
    ingredient = await session.get(Ingredient, id)
    if not ingredient:
        raise HTTPException(status_code=404, detail="Ingredient not found")
    return ingredient

@router.put("/{id}", response_model=IngredientRead)
async def update(
    session: Annotated[AsyncSession, Depends(db_helper.session_getter)],
    id: int,
    ingredient_update: IngredientCreate,
):
    """
    Обновить информацию об ингредиенте.
    
    - **id**: уникальный идентификатор ингредиента
    - **name**: новое название ингредиента
    """
    ingredient = await session.get(Ingredient, id)
    if not ingredient:
        raise HTTPException(status_code=404, detail="Ingredient not found")
    ingredient.name = ingredient_update.name
    try:
        await session.commit()
    except IntegrityError:
        await session.rollback()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Ingredient with name '{ingredient_update.name}' already exists"
        )
    await session.refresh(ingredient)
    return ingredient

@router.delete("/{id}", status_code=status.HTTP_204_NO_CONTENT)
async def destroy(
    session: Annotated[AsyncSession, Depends(db_helper.session_getter)], 
    id: int
):
    """
    Удалить ингредиент по ID.
    
    - **id**: уникальный идентификатор ингредиента
    """
    ingredient = await session.get(Ingredient, id)
    if not ingredient:
        raise HTTPException(status_code=404, detail="Ingredient not found")
    await session.delete(ingredient)
    await session.commit()
    return None

# Задача D: получить все рецепты, содержащие данный ингредиент
@router.get("/{id}/recipes", response_model=List[RecipeRead])
async def get_recipes_by_ingredient(
    session: Annotated[AsyncSession, Depends(db_helper.session_getter)],
    id: int,
):
    """
    Получить все рецепты, содержащие указанный ингредиент.
    
    - **id**: уникальный идентификатор ингредиента
    
    Возвращает список рецептов с полной информацией о кухне, аллергенах и ингредиентах.
    """
    # Проверяем существование ингредиента
    ingredient = await session.get(Ingredient, id)
    if not ingredient:
        raise HTTPException(status_code=404, detail="Ingredient not found")

    # Ищем рецепты через recipe_ingredients
    stmt = (
        select(Recipe)
        .join(RecipeIngredient)
        .where(RecipeIngredient.ingredient_id == id)
        .options(
            selectinload(Recipe.cuisine),
            selectinload(Recipe.allergens),
            selectinload(Recipe.recipe_ingredients),
        )
        .distinct()
    )
    result = await session.scalars(stmt)
    return result.all()