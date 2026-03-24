from typing import Annotated, Optional, List
from fastapi import APIRouter, Query, HTTPException, Depends, status
from pydantic import BaseModel, Field, ConfigDict, field_validator
from datetime import datetime
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from sqlalchemy.orm import selectinload
from sqlalchemy.exc import IntegrityError
from fastapi_pagination.ext.sqlalchemy import apaginate

from models import db_helper, Recipe, Cuisine, Allergen, Ingredient, RecipeIngredient, MeasurementEnum, RecipeAllergens, User
from config import settings

from fastapi_filter import FilterDepends, with_prefix
from fastapi_filter.contrib.sqlalchemy import Filter
from fastapi_pagination import Page
from fastapi_pagination.ext.sqlalchemy import paginate
from typing import Optional, List, Annotated

from authentication.fastapi_users import current_active_user
from authentication.schemas.user import UserRead

router = APIRouter(
    tags=["Recipes"],
    prefix=settings.url.recipes,
)

# схемы для вложенных объектов
class CuisineRead(BaseModel):
    id: int
    name: str

class AllergenRead(BaseModel):
    id: int
    name: str

# для создания ингредиента в рецепте
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

# для отображения ингредиента в рецепте
class RecipeIngredientRead(BaseModel):
    id: int
    name: str
    quantity: int
    measurement: int
    
    model_config = ConfigDict(
        from_attributes=True
    )

# создание рецепта
class RecipeCreate(BaseModel):
    title: str = Field(..., min_length=3, max_length=100)
    description: Optional[str] = Field(None, max_length=500)
    instructions: str = Field(..., min_length=10)
    cooking_time: int = Field(..., gt=0)
    difficulty: int = Field(..., ge=1, le=5)
    cuisine_id: int
    allergen_ids: List[int] = Field(default_factory=list)
    ingredients: List[RecipeIngredientCreate]

# обновление рецепта (только простые поля)
class RecipeUpdate(BaseModel):
    title: Optional[str] = Field(None, min_length=3, max_length=100)
    description: Optional[str] = Field(None, max_length=500)
    instructions: Optional[str] = Field(None, min_length=10)
    cooking_time: Optional[int] = Field(None, gt=0)
    difficulty: Optional[int] = Field(None, ge=1, le=5)
    cuisine_id: Optional[int] = None

# чтение рецепта
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
    author: UserRead

    model_config = ConfigDict(from_attributes=True)

# Новая схема для базового рецепта (без связей)
class RecipeBaseRead(BaseModel):
    id: int
    title: str
    description: Optional[str]
    cooking_time: int
    difficulty: int
    
    model_config = ConfigDict(from_attributes=True)

# Схема для рецепта с кухней
class RecipeWithCuisineRead(RecipeBaseRead):
    cuisine: CuisineRead
    
    model_config = ConfigDict(from_attributes=True)

# Схема для рецепта с ингредиентами
class RecipeWithIngredientsRead(RecipeBaseRead):
    ingredients: List[RecipeIngredientRead]
    
    model_config = ConfigDict(from_attributes=True)

# Схема для рецепта со всем (как текущий RecipeRead)
class RecipeWithAllRead(RecipeBaseRead):
    cuisine: CuisineRead
    allergens: List[AllergenRead]
    ingredients: List[RecipeIngredientRead]
    
    model_config = ConfigDict(from_attributes=True)

class RecipeFilter(Filter):
    """Фильтр для рецептов"""
    title__ilike: Optional[str] = None
    difficulty: Optional[int] = None
    
    order_by: List[str] = ['-id']
    
    class Constants(Filter.Constants):
        model = Recipe
        search_model_fields = ['title']

# ----- CRUD для рецептов -----

@router.post("", response_model=RecipeRead, status_code=status.HTTP_201_CREATED)
async def store(
    session: Annotated[AsyncSession, Depends(db_helper.session_getter)],
    recipe_create: RecipeCreate,
    current_user: Annotated[User, Depends(current_active_user)],
):
    # проверка существования кухни
    cuisine = await session.get(Cuisine, recipe_create.cuisine_id)
    if not cuisine:
        raise HTTPException(status_code=404, detail="Cuisine not found")

    # проверка аллергенов
    allergens = []
    if recipe_create.allergen_ids:
        stmt = select(Allergen).where(Allergen.id.in_(recipe_create.allergen_ids))
        result = await session.scalars(stmt)
        allergens = result.all()
        if len(allergens) != len(recipe_create.allergen_ids):
            raise HTTPException(status_code=404, detail="One or more allergens not found")

    # проверка ингредиентов
    ingredient_ids = [item.ingredient_id for item in recipe_create.ingredients]
    stmt = select(Ingredient).where(Ingredient.id.in_(ingredient_ids))
    result = await session.scalars(stmt)
    ingredients_db = result.all()
    if len(ingredients_db) != len(ingredient_ids):
        raise HTTPException(status_code=404, detail="One or more ingredients not found")

    # создание рецепта
    recipe = Recipe(
        title=recipe_create.title,
        description=recipe_create.description,
        instructions=recipe_create.instructions,
        cooking_time=recipe_create.cooking_time,
        difficulty=recipe_create.difficulty,
        cuisine_id=recipe_create.cuisine_id,
        author_id=current_user.id,
    )
    session.add(recipe)
    await session.flush()

    # добавление аллергенов через промежуточную таблицу
    if allergens:
        for allergen in allergens:
            ra = RecipeAllergens(recipe_id=recipe.id, allergen_id=allergen.id)
            session.add(ra)

    # добавление ингредиентов
    for item in recipe_create.ingredients:
        ri = RecipeIngredient(
            recipe_id=recipe.id,
            ingredient_id=item.ingredient_id,
            quantity=item.quantity,
            measurement=item.measurement,
        )
        session.add(ri)

    await session.commit()
    
    # загрузка рецепта со всеми связями
    stmt = (
        select(Recipe)
        .where(Recipe.id == recipe.id)
        .options(
            selectinload(Recipe.cuisine),
            selectinload(Recipe.allergens),
            selectinload(Recipe.recipe_ingredients).selectinload(RecipeIngredient.ingredient),
            selectinload(Recipe.author),
        )
    )
    
    result = await session.execute(stmt)
    recipe_with_relations = result.scalar_one()
    
    # ручное преобразование данных в нужный формат
    recipe_data = {
        "id": recipe_with_relations.id,
        "title": recipe_with_relations.title,
        "description": recipe_with_relations.description,
        "instructions": recipe_with_relations.instructions,
        "cooking_time": recipe_with_relations.cooking_time,
        "difficulty": recipe_with_relations.difficulty,
        "cuisine": {
            "id": recipe_with_relations.cuisine.id,
            "name": recipe_with_relations.cuisine.name
        },
        "allergens": [
            {"id": a.id, "name": a.name} 
            for a in recipe_with_relations.allergens
        ],
        "ingredients": [
            {
                "id": ri.ingredient.id,
                "name": ri.ingredient.name,
                "quantity": ri.quantity,
                "measurement": ri.measurement
            }
            for ri in recipe_with_relations.recipe_ingredients
        ],
        "author": {
            "id": recipe_with_relations.author.id,
            "email": recipe_with_relations.author.email,
            "first_name": recipe.author.first_name,
            "last_name": recipe.author.last_name,
        } if recipe_with_relations.author else None,
    }
    
    return recipe_data


# Функция преобразования одного рецепта
def recipe_to_dict(recipe: Recipe) -> dict:
    return {
        "id": recipe.id,
        "title": recipe.title,
        "description": recipe.description,
        "instructions": recipe.instructions,
        "cooking_time": recipe.cooking_time,
        "difficulty": recipe.difficulty,
        "cuisine": {
            "id": recipe.cuisine.id,
            "name": recipe.cuisine.name
        },
        "allergens": [
            {"id": a.id, "name": a.name} for a in recipe.allergens
        ],
        "ingredients": [
            {
                "id": ri.ingredient.id,
                "name": ri.ingredient.name,
                "quantity": ri.quantity,
                "measurement": ri.measurement
            }
            for ri in recipe.recipe_ingredients
        ],
        "author": {
            "id": recipe.author.id,
            "email": recipe.author.email,
            "first_name": recipe.author.first_name,
            "last_name": recipe.author.last_name,
        } if recipe.author else None,
    }

# Функция-трансформер для всего списка
def recipe_transformer(items: List[Recipe]) -> List[dict]:
    return [recipe_to_dict(item) for item in items]

@router.get("", response_model=Page[RecipeRead])
async def index(
    session: Annotated[AsyncSession, Depends(db_helper.session_getter)],
    filter: Annotated[RecipeFilter, FilterDepends(RecipeFilter)],
    page: int = Query(1, ge=1, description="Номер страницы"),
    size: int = Query(10, ge=1, le=100, description="Размер страницы"),
    ingredient_id: Optional[str] = Query(None, description="ID ингредиентов через запятую"),
):
    # Формируем запрос с подгрузкой связей
    stmt = (
        select(Recipe)
        .options(
            selectinload(Recipe.cuisine),
            selectinload(Recipe.allergens),
            selectinload(Recipe.recipe_ingredients).selectinload(RecipeIngredient.ingredient),
            selectinload(Recipe.author),
        )
    )
    
    # Применяем фильтры и сортировку
    stmt = filter.filter(stmt)
    
    if ingredient_id:
        try:
            ingredient_ids = [int(x.strip()) for x in ingredient_id.split(',') if x.strip()]
            if ingredient_ids:
                stmt = (
                    stmt.join(RecipeIngredient)
                    .where(RecipeIngredient.ingredient_id.in_(ingredient_ids))
                    .distinct()
                )
        except ValueError:
            pass

    if filter.order_by:
        stmt = filter.sort(stmt)
    else:
        stmt = stmt.order_by(Recipe.id.desc())
    
    # Используем apaginate с transformer
    paginated_result = await apaginate(session, stmt, transformer=recipe_transformer)
    return paginated_result


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
            selectinload(Recipe.recipe_ingredients).selectinload(RecipeIngredient.ingredient),
            selectinload(Recipe.author),
        )
    )
    result = await session.execute(stmt)
    recipe = result.scalar_one_or_none()
    if not recipe:
        raise HTTPException(status_code=404, detail="Recipe not found")
    
    # ручное преобразование данных
    recipe_data = {
        "id": recipe.id,
        "title": recipe.title,
        "description": recipe.description,
        "instructions": recipe.instructions,
        "cooking_time": recipe.cooking_time,
        "difficulty": recipe.difficulty,
        "cuisine": {
            "id": recipe.cuisine.id,
            "name": recipe.cuisine.name
        },
        "allergens": [
            {"id": a.id, "name": a.name} 
            for a in recipe.allergens
        ],
        "ingredients": [
            {
                "id": ri.ingredient.id,
                "name": ri.ingredient.name,
                "quantity": ri.quantity,
                "measurement": ri.measurement
            }
            for ri in recipe.recipe_ingredients
        ],
        "author": {
            "id": recipe.author.id,
            "email": recipe.author.email,
            "first_name": recipe.author.first_name,
            "last_name": recipe.author.last_name,
        } if recipe.author else None,
    }
    
    return recipe_data


@router.put("/{id}", response_model=RecipeRead)
async def update(
    session: Annotated[AsyncSession, Depends(db_helper.session_getter)],
    id: int,
    recipe_update: RecipeUpdate,
    current_user: Annotated[User, Depends(current_active_user)],
):
    """
    Обновить информацию о рецепте.
    """
    # получаем рецепт с загруженными связями
    stmt = (
        select(Recipe)
        .where(Recipe.id == id)
        .options(
            selectinload(Recipe.cuisine),
            selectinload(Recipe.allergens),
            selectinload(Recipe.recipe_ingredients).selectinload(RecipeIngredient.ingredient),
            selectinload(Recipe.author),
        )
    )
    result = await session.execute(stmt)
    recipe = result.scalar_one_or_none()
    
    if not recipe:
        raise HTTPException(status_code=404, detail="Recipe not found")

    # только автор может обновлять
    if recipe.author_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You are not the author of this recipe"
        )

    # если обновляем cuisine_id, проверяем существование кухни
    if recipe_update.cuisine_id is not None and recipe_update.cuisine_id != recipe.cuisine_id:
        cuisine = await session.get(Cuisine, recipe_update.cuisine_id)
        if not cuisine:
            raise HTTPException(
                status_code=404, 
                detail=f"Cuisine with id {recipe_update.cuisine_id} not found"
            )
        recipe.cuisine_id = recipe_update.cuisine_id

    # обновление только переданных полей
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
    
    # перезагрузка рецепта со всеми связями для ответа
    stmt = (
        select(Recipe)
        .where(Recipe.id == id)
        .options(
            selectinload(Recipe.cuisine),
            selectinload(Recipe.allergens),
            selectinload(Recipe.recipe_ingredients).selectinload(RecipeIngredient.ingredient),
            selectinload(Recipe.author),
        )
    )
    result = await session.execute(stmt)
    recipe = result.scalar_one()
    
    # ручное преобразование данных
    recipe_data = {
        "id": recipe.id,
        "title": recipe.title,
        "description": recipe.description,
        "instructions": recipe.instructions,
        "cooking_time": recipe.cooking_time,
        "difficulty": recipe.difficulty,
        "cuisine": {
            "id": recipe.cuisine.id,
            "name": recipe.cuisine.name
        },
        "allergens": [
            {"id": a.id, "name": a.name} 
            for a in recipe.allergens
        ],
        "ingredients": [
            {
                "id": ri.ingredient.id,
                "name": ri.ingredient.name,
                "quantity": ri.quantity,
                "measurement": ri.measurement
            }
            for ri in recipe.recipe_ingredients
        ],
        "author": {
            "id": recipe.author.id,
            "email": recipe.author.email,
            "first_name": recipe.author.first_name,
            "last_name": recipe.author.last_name,
        } if recipe.author else None,
    }
    
    return recipe_data


@router.delete("/{id}", status_code=status.HTTP_204_NO_CONTENT)
async def destroy(
    session: Annotated[AsyncSession, Depends(db_helper.session_getter)],
    id: int,
    current_user: Annotated[User, Depends(current_active_user)],
):
    """
    Удалить рецепт по ID.
    
    - **id**: уникальный идентификатор рецепта
    """
    recipe = await session.get(Recipe, id)
    if not recipe:
        raise HTTPException(status_code=404, detail="Recipe not found")
    
    # только автор может удалять
    if recipe.author_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You are not the author of this recipe"
        )

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