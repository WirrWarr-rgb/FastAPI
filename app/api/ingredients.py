from typing import Annotated, List, Optional
from fastapi import APIRouter, Depends, status, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select as sql_select
from sqlalchemy.orm import selectinload, contains_eager
from models import db_helper, Ingredient, Recipe, RecipeIngredient
from pydantic import BaseModel, ConfigDict
from sqlalchemy.exc import IntegrityError
from config import settings
from api.recipes import RecipeRead, RecipeBaseRead, RecipeWithCuisineRead, RecipeWithIngredientsRead, RecipeWithAllRead
router = APIRouter(tags=["Ingredients"], prefix=settings.url.ingredients)

class IngredientRead(BaseModel):
    id: int
    name: str

class IngredientCreate(BaseModel):
    name: str

# Новая схема для динамического выбора полей
class RecipeDynamicRead(BaseModel):
    """Динамическая модель для выборочного возврата полей"""
    id: int
    title: Optional[str] = None
    description: Optional[str] = None
    cooking_time: Optional[int] = None
    difficulty: Optional[int] = None
    cuisine: Optional[dict] = None
    allergens: Optional[List[dict]] = None
    ingredients: Optional[List[dict]] = None
    
    model_config = ConfigDict(from_attributes=True)

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
    stmt = sql_select(Ingredient).order_by(Ingredient.id).offset(skip).limit(limit)
    result = await session.scalars(stmt)
    return result.all()

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

@router.get("/{id}/recipes")
async def get_recipes_by_ingredient(
    session: Annotated[AsyncSession, Depends(db_helper.session_getter)],
    id: int,
    include: Optional[str] = Query(None, description="Подгрузить связанные данные: cuisine,ingredients,allergens (через запятую)"),
    select: Optional[str] = Query(None, description="Выбрать поля: id,title,description,cooking_time,difficulty (через запятую)"),
):
    # Проверка существования ингредиента
    ingredient = await session.get(Ingredient, id)
    if not ingredient:
        raise HTTPException(status_code=404, detail="Ingredient not found")

    # Разбираем параметр include
    include_list = include.split(',') if include else []
    include_cuisine = 'cuisine' in include_list
    include_ingredients = 'ingredients' in include_list
    include_allergens = 'allergens' in include_list
    
    # Разбираем параметр select
    select_list = select.split(',') if select else None
    all_fields = not select_list  # если select не указан, возвращаем все поля
    
    # Строим базовый запрос
    stmt = (
        sql_select(Recipe)  # используем переименованный импорт
        .distinct()
        .join(RecipeIngredient)
        .where(RecipeIngredient.ingredient_id == id)
    )
    
    # Добавляем загрузку связей в зависимости от include
    options = []
    if include_cuisine:
        options.append(selectinload(Recipe.cuisine))
    if include_ingredients:
        options.append(selectinload(Recipe.recipe_ingredients).selectinload(RecipeIngredient.ingredient))
    if include_allergens:
        options.append(selectinload(Recipe.allergens))
    
    if options:
        stmt = stmt.options(*options)
    
    result = await session.execute(stmt)
    recipes = result.unique().scalars().all()
    
    # Формируем ответ с учетом include и select
    recipes_data = []
    for recipe in recipes:
        recipe_data = {}
        
        # Основные поля (всегда включаем id)
        recipe_data["id"] = recipe.id
        
        # Добавляем поля в соответствии с select
        if all_fields or 'title' in select_list:
            recipe_data["title"] = recipe.title
        if all_fields or 'description' in select_list:
            recipe_data["description"] = recipe.description
        if all_fields or 'cooking_time' in select_list:
            recipe_data["cooking_time"] = recipe.cooking_time
        if all_fields or 'difficulty' in select_list:
            recipe_data["difficulty"] = recipe.difficulty
        
        # Добавляем связанные данные согласно include
        if include_cuisine and hasattr(recipe, 'cuisine') and recipe.cuisine:
            recipe_data["cuisine"] = {
                "id": recipe.cuisine.id,
                "name": recipe.cuisine.name
            }
        
        if include_allergens and hasattr(recipe, 'allergens'):
            recipe_data["allergens"] = [
                {"id": a.id, "name": a.name}
                for a in recipe.allergens
            ]
        
        if include_ingredients and hasattr(recipe, 'recipe_ingredients'):
            recipe_data["ingredients"] = [
                {
                    "id": ri.ingredient.id,
                    "name": ri.ingredient.name,
                    "quantity": ri.quantity,
                    "measurement": ri.measurement
                }
                for ri in recipe.recipe_ingredients
            ]
        
        recipes_data.append(recipe_data)
    
    return recipes_data