from typing import Annotated, List
from fastapi import APIRouter, Depends, status, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import selectinload
from models import db_helper, Ingredient, Recipe, RecipeIngredient
from pydantic import BaseModel
from api.recipes import RecipeRead  # импортируем схему чтения рецепта

router = APIRouter(tags=["Ingredients"], prefix="/ingredients")

class IngredientRead(BaseModel):
    id: int
    name: str

class IngredientCreate(BaseModel):
    name: str

@router.get("", response_model=list[IngredientRead])
async def index(session: Annotated[AsyncSession, Depends(db_helper.session_getter)]):
    stmt = select(Ingredient).order_by(Ingredient.id)
    result = await session.scalars(stmt)
    return result.all()

@router.post("", response_model=IngredientRead, status_code=status.HTTP_201_CREATED)
async def store(
    session: Annotated[AsyncSession, Depends(db_helper.session_getter)],
    ingredient_create: IngredientCreate,
):
    ingredient = Ingredient(name=ingredient_create.name)
    session.add(ingredient)
    await session.commit()
    await session.refresh(ingredient)
    return ingredient

@router.get("/{id}", response_model=IngredientRead)
async def show(session: Annotated[AsyncSession, Depends(db_helper.session_getter)], id: int):
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
    ingredient = await session.get(Ingredient, id)
    if not ingredient:
        raise HTTPException(status_code=404, detail="Ingredient not found")
    ingredient.name = ingredient_update.name
    await session.commit()
    await session.refresh(ingredient)
    return ingredient

@router.delete("/{id}", status_code=status.HTTP_204_NO_CONTENT)
async def destroy(session: Annotated[AsyncSession, Depends(db_helper.session_getter)], id: int):
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