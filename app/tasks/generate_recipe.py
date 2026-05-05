from typing import Annotated
import json

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from taskiq import TaskiqDepends
from openai import AsyncOpenAI
from pydantic import BaseModel, Field
from tenacity import retry, stop_after_attempt, wait_exponential

from task_queue import broker
from models import db_helper, Recipe, Cuisine, Allergen, Ingredient, RecipeIngredient, RecipeAllergens
from config import settings

# cоздаем клиент OpenRouter
client = AsyncOpenAI(
    api_key=settings.api.router_key,
    base_url="https://openrouter.ai/api/v1",
)


# ============ Pydantic схемы для Structured Output ============

class LLMIngredient(BaseModel):
    """
    Схема ингредиента от LLM.
    measurement должен быть одним из значений enum:
    GRAMS, PIECES, MILLILITERS
    """
    name: str = Field(description="Название ингредиента")
    quantity: int = Field(description="Количество")
    measurement: str = Field(description="Единица измерения: GRAMS, PIECES или MILLILITERS")


class LLMRecipeResponse(BaseModel):
    """
    Схема ответа от LLM.
    Содержит все необходимые поля для создания рецепта.
    """
    title: str = Field(description="Название рецепта")
    description: str = Field(description="Краткое описание рецепта")
    instructions: str = Field(description="Пошаговая инструкция приготовления")
    cooking_time: int = Field(description="Время приготовления в минутах")
    difficulty: int = Field(description="Сложность от 1 до 5", ge=1, le=5)
    cuisine: str = Field(description="Название кухни (например, Итальянская, Японская)")
    allergens: list[str] = Field(description="Список аллергенов")
    ingredients: list[LLMIngredient] = Field(description="Список ингредиентов")


# ============ бизнес-логика ============

async def get_or_create_cuisine(session: AsyncSession, name: str) -> Cuisine:
    """
    Получить существующую кухню или создать новую.
    """
    stmt = select(Cuisine).where(Cuisine.name == name)
    result = await session.scalars(stmt)
    cuisine = result.first()
    
    if not cuisine:
        cuisine = Cuisine(name=name)
        session.add(cuisine)
        await session.flush()
    
    return cuisine


async def get_or_create_allergens(session: AsyncSession, names: list[str]) -> list[Allergen]:
    """
    Получить существующие аллергены или создать новые.
    """
    allergens = []
    for name in names:
        stmt = select(Allergen).where(Allergen.name == name)
        result = await session.scalars(stmt)
        allergen = result.first()
        
        if not allergen:
            allergen = Allergen(name=name)
            session.add(allergen)
            await session.flush()
        
        allergens.append(allergen)
    
    return allergens


async def get_or_create_ingredients(
    session: AsyncSession, 
    ingredients_data: list[LLMIngredient]
) -> list[tuple[Ingredient, int, str]]:
    """
    Получить существующие ингредиенты или создать новые.
    Возвращает список кортежей: (ингредиент, количество, измерение)
    """
    result = []
    for ing_data in ingredients_data:
        stmt = select(Ingredient).where(Ingredient.name == ing_data.name)
        db_result = await session.scalars(stmt)
        ingredient = db_result.first()
        
        if not ingredient:
            ingredient = Ingredient(name=ing_data.name)
            session.add(ingredient)
            await session.flush()
        
        result.append((ingredient, ing_data.quantity, ing_data.measurement))
    
    return result


def measurement_str_to_enum(measurement: str) -> int:
    """
    Преобразует строковое значение измерения в числовое значение enum.
    """
    mapping = {
        "GRAMS": 1,
        "PIECES": 2,
        "MILLILITERS": 3,
    }
    return mapping.get(measurement.upper(), 1)  # по умолчанию GRAMS


@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=2, max=10),
)
async def call_llm(prompt: str) -> LLMRecipeResponse:
    """
    Вызов LLM через OpenRouter с retry логикой.
    """
    # формируем JSON схему из Pydantic модели
    schema = {
        "name": "recipe",
        "strict": True,
        "schema": LLMRecipeResponse.model_json_schema(),
    }
    
    response = await client.chat.completions.create(
        model="google/gemini-2.0-flash-001",
        messages=[
            {
                "role": "system",
                "content": (
                    "Ты - шеф-повар. Возвращай ТОЛЬКО валидный JSON, "
                    "соответствующий схеме. Не добавляй никаких пояснений. "
                    "Для measurement используй ТОЛЬКО значения: GRAMS, PIECES, MILLILITERS."
                ),
            },
            {
                "role": "user", 
                "content": f"Сгенерируй рецепт по запросу: {prompt}"
            },
        ],
        response_format={
            "type": "json_schema",
            "json_schema": schema,
        },
    )
    
    content = response.choices[0].message.content
    data = json.loads(content)
    recipe = LLMRecipeResponse.model_validate(data)
    return recipe


# ============ основная задача ============

@broker.task(retry_on_error=True)
async def generate_recipe_task(
    prompt: str,
    user_id: int,
    session: Annotated[
        AsyncSession,
        TaskiqDepends(db_helper.session_getter),
    ],
) -> None:
    """
    Задача для генерации рецепта:
    1. Вызывает LLM
    2. Валидирует результат
    3. Сохраняет в БД
    """
    print(f"🚀 Начинаю генерацию рецепта для пользователя {user_id}")
    print(f"📝 Промпт: {prompt}")
    
    try:
        # 1. вызов LLM
        llm_recipe = await call_llm(prompt)
        print(f"✅ LLM вернул рецепт: {llm_recipe.title}")
        
        # 2. получаем или создаем кухню
        cuisine = await get_or_create_cuisine(session, llm_recipe.cuisine)
        
        # 3. получаем или создаем аллергены
        allergens = await get_or_create_allergens(session, llm_recipe.allergens)
        
        # 4. получаем или создаем ингредиенты
        ingredients_data = await get_or_create_ingredients(session, llm_recipe.ingredients)
        
        # 5. создаем рецепт
        recipe = Recipe(
            title=llm_recipe.title,
            description=llm_recipe.description,
            instructions=llm_recipe.instructions,
            cooking_time=llm_recipe.cooking_time,
            difficulty=llm_recipe.difficulty,
            cuisine_id=cuisine.id,
            author_id=user_id,
        )
        session.add(recipe)
        await session.flush()
        
        # 6. связываем аллергены
        for allergen in allergens:
            ra = RecipeAllergens(recipe_id=recipe.id, allergen_id=allergen.id)
            session.add(ra)
        
        # 7. добавляем ингредиенты
        for ingredient, quantity, measurement_str in ingredients_data:
            measurement_value = measurement_str_to_enum(measurement_str)
            ri = RecipeIngredient(
                recipe_id=recipe.id,
                ingredient_id=ingredient.id,
                quantity=quantity,
                measurement=measurement_value,
            )
            session.add(ri)
        
        await session.commit()
        print(f"🎉 Рецепт '{recipe.title}' успешно сохранен! ID: {recipe.id}")
        
    except Exception as e:
        await session.rollback()
        print(f"❌ Ошибка при генерации рецепта: {str(e)}")
        raise  # пробрасываем ошибку для retry механизма