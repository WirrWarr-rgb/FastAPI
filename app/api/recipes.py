from typing import Annotated, Optional, List
from fastapi import APIRouter, Query, HTTPException, Depends, status
from pydantic import BaseModel, Field, ConfigDict, field_validator
from datetime import datetime
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import selectinload
from sqlalchemy.exc import IntegrityError

from models import db_helper, Recipe, Cuisine, Allergen, Ingredient, RecipeIngredient, MeasurementEnum
from config import settings

router = APIRouter(
    tags=["Recipes"],
    prefix=settings.url.recipes,
)

# Схемы для вложенных объектов
class CuisineRead(BaseModel):
    id: int
    name: str

class AllergenRead(BaseModel):
    id: int
    name: str

# Для создания ингредиента в рецепте
class RecipeIngredientCreate(BaseModel):
    ingredient_id: int = Field(..., alias="id")
    quantity: int
    measurement: int

    @field_validator("measurement")
    @classmethod
    def validate_measurement(cls, v):
        if v not in [item.value for item in MeasurementEnum]:
            raise ValueError(f"Measurement must be one of {[e.value for e in MeasurementEnum]}")
        return v

    model_config = ConfigDict(populate_by_name=True)

# Для отображения ингредиента в рецепте
class RecipeIngredientRead(BaseModel):
    id: int = Field(..., alias="ingredient_id")
    name: str
    quantity: int
    measurement: int
    
    model_config = ConfigDict(
        from_attributes=True,
        populate_by_name=True
    )

# Создание рецепта
class RecipeCreate(BaseModel):
    title: str = Field(..., min_length=3, max_length=100)
    description: Optional[str] = Field(None, max_length=500)
    instructions: str = Field(..., min_length=10)
    cooking_time: int = Field(..., gt=0)
    difficulty: int = Field(..., ge=1, le=5)
    cuisine_id: int
    allergen_ids: List[int] = Field(default_factory=list)
    ingredients: List[RecipeIngredientCreate]

# Обновление рецепта (только простые поля)
class RecipeUpdate(BaseModel):
    title: Optional[str] = Field(None, min_length=3, max_length=100)
    description: Optional[str] = Field(None, max_length=500)
    instructions: Optional[str] = Field(None, min_length=10)
    cooking_time: Optional[int] = Field(None, gt=0)
    difficulty: Optional[int] = Field(None, ge=1, le=5)
    cuisine_id: Optional[int] = None

# Чтение рецепта
class RecipeRead(BaseModel):
    id: int
    title: str
    description: Optional[str]
    instructions: str
    cooking_time: int
    difficulty: int
    cuisine: CuisineRead
    allergens: List[AllergenRead]
    ingredients: List[RecipeIngredientRead]
    
    model_config = ConfigDict(from_attributes=True)
    
# ----- CRUD для рецептов -----

@router.post("", response_model=RecipeRead, status_code=status.HTTP_201_CREATED)
async def store(
    session: Annotated[AsyncSession, Depends(db_helper.session_getter)],
    recipe_create: RecipeCreate,
):
    """
    Создать новый рецепт.
    
    - **title**: название рецепта
    - **description**: описание рецепта (необязательно)
    - **instructions**: инструкция по приготовлению
    - **cooking_time**: время приготовления в минутах
    - **difficulty**: сложность от 1 до 5
    - **cuisine_id**: ID кухни
    - **allergen_ids**: список ID аллергенов
    - **ingredients**: список ингредиентов с количеством и единицами измерения
    """
    # Проверка существования кухни
    cuisine = await session.get(Cuisine, recipe_create.cuisine_id)
    if not cuisine:
        raise HTTPException(status_code=404, detail="Cuisine not found")

    # Проверка аллергенов
    allergens = []
    if recipe_create.allergen_ids:
        stmt = select(Allergen).where(Allergen.id.in_(recipe_create.allergen_ids))
        result = await session.scalars(stmt)
        allergens = result.all()
        if len(allergens) != len(recipe_create.allergen_ids):
            raise HTTPException(status_code=404, detail="One or more allergens not found")

    # Проверка ингредиентов
    ingredient_ids = [item.ingredient_id for item in recipe_create.ingredients]
    stmt = select(Ingredient).where(Ingredient.id.in_(ingredient_ids))
    result = await session.scalars(stmt)
    ingredients_db = result.all()
    if len(ingredients_db) != len(ingredient_ids):
        raise HTTPException(status_code=404, detail="One or more ingredients not found")

    # Создание рецепта
    recipe = Recipe(
        title=recipe_create.title,
        description=recipe_create.description,
        instructions=recipe_create.instructions,
        cooking_time=recipe_create.cooking_time,
        difficulty=recipe_create.difficulty,
        cuisine_id=recipe_create.cuisine_id,
    )
    session.add(recipe)
    await session.flush()

    # Добавление аллергенов
    if allergens:
        recipe.allergens.extend(allergens)

    # Добавление ингредиентов
    for item in recipe_create.ingredients:
        ri = RecipeIngredient(
            recipe_id=recipe.id,
            ingredient_id=item.ingredient_id,
            quantity=item.quantity,
            measurement=item.measurement,
        )
        session.add(ri)

    try:
        await session.commit()
    except IntegrityError:
        await session.rollback()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Error creating recipe. Please check your data."
        )

    # Перезагрузка рецепта со связанными данными для ответа
    stmt = (
        select(Recipe)
        .where(Recipe.id == recipe.id)
        .options(
            selectinload(Recipe.cuisine),
            selectinload(Recipe.allergens),
            selectinload(Recipe.recipe_ingredients).selectinload(RecipeIngredient.ingredient),
        )
    )
    result = await session.execute(stmt)
    recipe = result.scalar_one()
    return recipe


@router.get("", response_model=list[RecipeRead])
async def index(
    session: Annotated[AsyncSession, Depends(db_helper.session_getter)],
    skip: int = Query(0, ge=0, description="Сколько записей пропустить"),
    limit: int = Query(10, ge=1, le=100, description="Сколько записей вернуть"),
    difficulty: Optional[int] = Query(None, ge=1, le=5, description="Фильтр по сложности"),
):
    """
    Получить список всех рецептов с пагинацией и фильтрацией.
    
    - **skip**: количество записей для пропуска (по умолчанию 0)
    - **limit**: максимальное количество записей (по умолчанию 10, максимум 100)
    - **difficulty**: фильтр по сложности (от 1 до 5)
    """
    stmt = (
        select(Recipe)
        .options(
            selectinload(Recipe.cuisine),
            selectinload(Recipe.allergens),
            selectinload(Recipe.recipe_ingredients),
        )
        .order_by(Recipe.id)
    )
    if difficulty is not None:
        stmt = stmt.where(Recipe.difficulty == difficulty)
    stmt = stmt.offset(skip).limit(limit)
    result = await session.scalars(stmt)
    return result.all()


@router.get("/{id}", response_model=RecipeRead)
async def show(
    session: Annotated[AsyncSession, Depends(db_helper.session_getter)],
    id: int,
):
    """
    Получить информацию о конкретном рецепте по ID.
    
    - **id**: уникальный идентификатор рецепта
    """
    stmt = (
        select(Recipe)
        .where(Recipe.id == id)
        .options(
            selectinload(Recipe.cuisine),
            selectinload(Recipe.allergens),
            selectinload(Recipe.recipe_ingredients),
        )
    )
    result = await session.execute(stmt)
    recipe = result.scalar_one_or_none()
    if not recipe:
        raise HTTPException(status_code=404, detail="Recipe not found")
    return recipe


@router.put("/{id}", response_model=RecipeRead)
async def update(
    session: Annotated[AsyncSession, Depends(db_helper.session_getter)],
    id: int,
    recipe_update: RecipeUpdate,
):
    """
    Обновить информацию о рецепте.
    
    - **id**: уникальный идентификатор рецепта
    - **title**: новое название (необязательно)
    - **description**: новое описание (необязательно)
    - **instructions**: новая инструкция (необязательно)
    - **cooking_time**: новое время приготовления (необязательно)
    - **difficulty**: новая сложность (необязательно)
    - **cuisine_id**: новый ID кухни (необязательно)
    """
    # Получаем рецепт с загруженными связями
    stmt = (
        select(Recipe)
        .where(Recipe.id == id)
        .options(
            selectinload(Recipe.cuisine),
            selectinload(Recipe.allergens),
            selectinload(Recipe.recipe_ingredients),
        )
    )
    result = await session.execute(stmt)
    recipe = result.scalar_one_or_none()
    
    if not recipe:
        raise HTTPException(status_code=404, detail="Recipe not found")

    # Если обновляем cuisine_id, проверяем существование кухни
    if recipe_update.cuisine_id is not None and recipe_update.cuisine_id != recipe.cuisine_id:
        cuisine = await session.get(Cuisine, recipe_update.cuisine_id)
        if not cuisine:
            raise HTTPException(
                status_code=404, 
                detail=f"Cuisine with id {recipe_update.cuisine_id} not found"
            )
        recipe.cuisine_id = recipe_update.cuisine_id

    # Обновляем только переданные поля
    update_data = recipe_update.model_dump(exclude_unset=True, exclude={'cuisine_id'})
    for field, value in update_data.items():
        setattr(recipe, field, value)

    try:
        await session.commit()
    except IntegrityError:
        await session.rollback()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Error updating recipe. Please check your data."
        )
    
    # Перезагружаем рецепт со всеми связями для ответа
    stmt = (
        select(Recipe)
        .where(Recipe.id == id)
        .options(
            selectinload(Recipe.cuisine),
            selectinload(Recipe.allergens),
            selectinload(Recipe.recipe_ingredients).selectinload(RecipeIngredient.ingredient),
        )
    )
    result = await session.execute(stmt)
    recipe = result.scalar_one()
    return recipe


@router.delete("/{id}", status_code=status.HTTP_204_NO_CONTENT)
async def destroy(
    session: Annotated[AsyncSession, Depends(db_helper.session_getter)],
    id: int,
):
    """
    Удалить рецепт по ID.
    
    - **id**: уникальный идентификатор рецепта
    """
    recipe = await session.get(Recipe, id)
    if not recipe:
        raise HTTPException(status_code=404, detail="Recipe not found")
    
    try:
        await session.delete(recipe)
        await session.commit()
    except IntegrityError:
        await session.rollback()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot delete recipe because it is referenced by other records."
        )
    return None