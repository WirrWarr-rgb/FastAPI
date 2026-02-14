import uvicorn
from fastapi import FastAPI, Body, Query, Path, Form, File, UploadFile, HTTPException
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field
from typing import Optional, List, Annotated
from datetime import datetime
import uuid
import shutil
from pathlib import Path
import logging
from contextlib import asynccontextmanager

from config import settings
from models import db_helper, Base
from api import router as api_router

UPLOAD_DIR = Path("uploads")
UPLOAD_DIR.mkdir(exist_ok=True)

ALLOWED_EXTENSIONS = {".png", ".jpg", ".jpeg", ".webp"}

class Item(BaseModel):
    name: str
    description: Optional[str] = None
    price: float
    tax: Optional[float] = None

class User(BaseModel):
    username: str
    full_name: Optional[str] = None

class FilterParams(BaseModel):
    model_config = {"extra": "forbid"}
    
    limit: int = Field(100, gt=0, le=100, description="Количество записей")
    offset: int = Field(0, ge=0, description="Смещение")
    order_by: str = Field("created_at", description="Поле для сортировки")
    tags: List[str] = Field([], description="Теги для фильтрации")

class Image(BaseModel):
    url: str
    name: str

class Product(BaseModel):
    name: str
    description: str
    price: float
    tags: List[str] = []
    image: Optional[Image] = None
    images: List[Image] = []

class FormData(BaseModel):
    username: str = Field(..., min_length=3, max_length=20)
    password: str = Field(..., min_length=8)
    remember_me: bool = False

# ===== МОДЕЛИ ДЛЯ РЕЦЕПТОВ =====
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

class Recipe(RecipeBase):
    id: int
    created_at: datetime
    updated_at: datetime
    
    class Config:
        from_attributes = True

recipes_db = {}
recipe_counter = 0

@asynccontextmanager
async def lifespan(app: FastAPI):
    print("🚀 Запуск приложения...")
    async with db_helper.engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    print("✅ База данных готова")
    
    yield
    print("🛑 Остановка приложения...")
    await db_helper.dispose()
    print("✅ Ресурсы освобождены")

main_app = FastAPI(
    title="API для рецептов",
    description="""
    🍳 API для управления рецептами с примерами из документации FastAPI
    
    ## Возможности:
    * Управление рецептами (CRUD)
    * Загрузка изображений
    * Различные форматы ответов (JSON/HTML)
    * Примеры из документации FastAPI
    """,
    version="1.0.0",
    lifespan=lifespan,
)

main_app.mount("/static", StaticFiles(directory="uploads"), name="static")

@main_app.get("/", response_class=HTMLResponse)
async def root():
    return """
    <!DOCTYPE html>
    <html>
    <head>
        <title>API Рецептов</title>
        <style>
            body { 
                font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; 
                line-height: 1.6;
                color: #333;
                max-width: 1200px;
                margin: 0 auto;
                padding: 20px;
                background: #f5f5f5;
            }
            .container {
                background: white;
                padding: 30px;
                border-radius: 10px;
                box-shadow: 0 2px 10px rgba(0,0,0,0.1);
            }
            h1 { color: #2c3e50; border-bottom: 3px solid #3498db; padding-bottom: 10px; }
            h2 { color: #34495e; margin-top: 30px; }
            .card {
                background: #f8f9fa;
                border-left: 4px solid #3498db;
                padding: 15px;
                margin: 15px 0;
                border-radius: 0 5px 5px 0;
            }
            .endpoint {
                background: #fff;
                border: 1px solid #ddd;
                padding: 10px 15px;
                margin: 10px 0;
                border-radius: 5px;
                font-family: monospace;
            }
            .method {
                display: inline-block;
                padding: 3px 8px;
                border-radius: 3px;
                color: white;
                font-weight: bold;
                margin-right: 10px;
            }
            .get { background: #61affe; }
            .post { background: #49cc90; }
            .put { background: #fca130; }
            .delete { background: #f93e3e; }
            a {
                color: #3498db;
                text-decoration: none;
            }
            a:hover {
                text-decoration: underline;
            }
            .button {
                display: inline-block;
                background: #3498db;
                color: white;
                padding: 10px 20px;
                border-radius: 5px;
                margin: 10px 5px 10px 0;
            }
            .button:hover {
                background: #2980b9;
                text-decoration: none;
            }
        </style>
    </head>
    <body>
        <div class="container">
            <h1>🍳 API для рецептов</h1>
            <p>Добро пожаловать в API для управления рецептами! Все маршруты успешно загружены.</p>
            
            <a href="/docs" class="button">📚 Swagger UI</a>
            <a href="/redoc" class="button">📖 ReDoc</a>
            
            <h2>📋 Часть A: Примеры из документации FastAPI</h2>
            
            <div class="card">
                <h3>Body параметры</h3>
                <div class="endpoint"><span class="method post">POST</span> /examples/body/</div>
            </div>
            
            <div class="card">
                <h3>Query параметры с валидацией</h3>
                <div class="endpoint"><span class="method get">GET</span> /examples/query-validation/</div>
            </div>
            
            <div class="card">
                <h3>Path параметры с валидацией</h3>
                <div class="endpoint"><span class="method get">GET</span> /examples/path-validation/{item_id}</div>
            </div>
            
            <div class="card">
                <h3>Query модель</h3>
                <div class="endpoint"><span class="method get">GET</span> /examples/query-model/</div>
            </div>
            
            <div class="card">
                <h3>Вложенные модели</h3>
                <div class="endpoint"><span class="method post">POST</span> /examples/nested-models/</div>
            </div>
            
            <div class="card">
                <h3>Form данные</h3>
                <div class="endpoint"><span class="method post">POST</span> /examples/form/</div>
                <div class="endpoint"><span class="method post">POST</span> /examples/form-model/</div>
            </div>
            
            <div class="card">
                <h3>Обработка формата ответа</h3>
                <div class="endpoint"><span class="method get">GET</span> /format-example/?format=json|html</div>
            </div>
            
            <div class="card">
                <h3>Загрузка изображений</h3>
                <div class="endpoint"><span class="method post">POST</span> /upload-image/</div>
            </div>
            
            <h2>📝 Часть B: CRUD для рецептов</h2>
            
            <div class="card">
                <h3>Создание рецепта</h3>
                <div class="endpoint"><span class="method post">POST</span> /recipes/</div>
            </div>
            
            <div class="card">
                <h3>Получение всех рецептов</h3>
                <div class="endpoint"><span class="method get">GET</span> /recipes/</div>
            </div>
            
            <div class="card">
                <h3>Получение рецепта по ID</h3>
                <div class="endpoint"><span class="method get">GET</span> /recipes/{recipe_id}</div>
            </div>
            
            <div class="card">
                <h3>Обновление рецепта</h3>
                <div class="endpoint"><span class="method put">PUT</span> /recipes/{recipe_id}</div>
            </div>
            
            <div class="card">
                <h3>Удаление рецепта</h3>
                <div class="endpoint"><span class="method delete">DELETE</span> /recipes/{recipe_id}</div>
            </div>
            
            <h2>🔧 Тестовые маршруты</h2>
            <div class="card">
                <div class="endpoint"><span class="method get">GET</span> /test</div>
            </div>
            
            <footer style="margin-top: 40px; text-align: center; color: #7f8c8d;">
                <p>FastAPI приложение успешно запущено! 🚀</p>
            </footer>
        </div>
    </body>
    </html>
    """

@main_app.post("/examples/body/")
async def create_item_with_body(
    item: Item, 
    user: User, 
    importance: int = Body(ge=1, le=10, description="Важность от 1 до 10")
):
    """Пример с Body параметрами: item, user и importance в теле запроса"""
    return {
        "item": item,
        "user": user,
        "importance": importance,
        "message": "Объекты успешно созданы"
    }

@main_app.get("/examples/query-validation/")
async def read_items(
    q: Annotated[
        Optional[str], 
        Query(
            min_length=3, 
            max_length=50,
            regex="^[a-zA-Z0-9 ]+$",
            description="Поисковый запрос (только буквы, цифры и пробелы)"
        )
    ] = None,
    skip: int = Query(0, ge=0, description="Сколько пропустить"),
    limit: int = Query(10, ge=1, le=100, description="Сколько вернуть")
):
    """Пример с валидацией query параметров"""
    items = [
        {"id": 1, "name": "Item 1", "price": 100},
        {"id": 2, "name": "Item 2", "price": 200},
        {"id": 3, "name": "Item 3", "price": 300},
    ]
    
    if q:
        items = [item for item in items if q.lower() in item["name"].lower()]
    
    return {
        "q": q,
        "skip": skip,
        "limit": limit,
        "items": items[skip:skip + limit],
        "total": len(items)
    }

@main_app.get("/examples/path-validation/{item_id}")
async def read_item(
    item_id: Annotated[
        int, 
        Path(
            title="ID товара",
            ge=1, 
            le=1000,
            description="ID товара должен быть от 1 до 1000"
        )
    ]
):
    """Пример с валидацией path параметров"""
    return {
        "item_id": item_id,
        "name": f"Item {item_id}",
        "price": item_id * 100,
        "description": f"Описание товара {item_id}"
    }

@main_app.get("/examples/query-model/")
async def read_items_with_model(
    filter_query: Annotated[FilterParams, Query()]
):
    """Пример с моделью для query параметров"""
    return {
        "applied_filters": filter_query,
        "message": f"Получено {filter_query.limit} записей со смещением {filter_query.offset}",
        "items": [f"Item {i}" for i in range(filter_query.offset, filter_query.offset + filter_query.limit)]
    }

@main_app.post("/examples/nested-models/")
async def create_product(product: Product):
    """Пример с вложенными моделями"""
    return {
        "product": product,
        "message": "Продукт успешно создан",
        "total_images": len(product.images) + (1 if product.image else 0)
    }

@main_app.post("/examples/form/")
async def handle_form(
    username: str = Form(..., min_length=3, max_length=20, description="Имя пользователя"),
    password: str = Form(..., min_length=8, description="Пароль"),
    age: int = Form(18, ge=18, le=120, description="Возраст")
):
    """Пример с Form данными"""
    return {
        "username": username,
        "age": age,
        "message": "Форма успешно отправлена"
    }

@main_app.post("/examples/form-model/")
async def handle_form_model(form_data: Annotated[FormData, Form()]):
    """Пример с моделью для Form данных"""
    return {
        "received_data": form_data,
        "message": "Модель формы успешно обработана"
    }

@main_app.get("/format-example/")
async def format_response(
    format: str = Query(
        "json", 
        regex="^(json|html)$",
        description="Формат ответа: json (JSON данные) или html (HTML страница)"
    )
):
    """Маршрут, возвращающий данные в JSON или HTML формате"""
    data = {
        "title": "Пример данных",
        "description": "Это тестовые данные для демонстрации разных форматов ответа",
        "items": [
            {"id": 1, "name": "Первый элемент", "value": 100},
            {"id": 2, "name": "Второй элемент", "value": 200},
            {"id": 3, "name": "Третий элемент", "value": 300},
            {"id": 4, "name": "Четвертый элемент", "value": 400},
            {"id": 5, "name": "Пятый элемент", "value": 500}
        ],
        "created_at": datetime.now().isoformat()
    }
    
    if format == "html":
        items_html = ""
        for item in data["items"]:
            items_html += f"""
            <tr>
                <td>{item['id']}</td>
                <td>{item['name']}</td>
                <td>{item['value']}</td>
            </tr>
            """
        
        html_content = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <title>{data['title']}</title>
            <style>
                body {{ 
                    font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
                    max-width: 800px;
                    margin: 0 auto;
                    padding: 20px;
                    background: #f5f5f5;
                }}
                .container {{
                    background: white;
                    padding: 30px;
                    border-radius: 10px;
                    box-shadow: 0 2px 10px rgba(0,0,0,0.1);
                }}
                h1 {{ color: #2c3e50; }}
                .date {{ color: #7f8c8d; font-size: 0.9em; }}
                table {{
                    width: 100%;
                    border-collapse: collapse;
                    margin-top: 20px;
                }}
                th {{
                    background: #3498db;
                    color: white;
                    padding: 10px;
                    text-align: left;
                }}
                td {{
                    padding: 10px;
                    border-bottom: 1px solid #ddd;
                }}
                tr:hover {{ background: #f5f5f5; }}
            </style>
        </head>
        <body>
            <div class="container">
                <h1>{data['title']}</h1>
                <p>{data['description']}</p>
                <p class="date">Дата создания: {data['created_at']}</p>
                
                <h3>Список элементов:</h3>
                <table>
                    <thead>
                        <tr>
                            <th>ID</th>
                            <th>Название</th>
                            <th>Значение</th>
                        </tr>
                    </thead>
                    <tbody>
                        {items_html}
                    </tbody>
                </table>
            </div>
        </body>
        </html>
        """
        return HTMLResponse(content=html_content, status_code=200)
    
    return JSONResponse(content=data)

@main_app.post("/upload-image/")
async def upload_image(
    file: UploadFile = File(..., description="Изображение для загрузки (PNG, JPG, WEBP)")
):
    """Маршрут для загрузки изображений"""
    file_extension = Path(file.filename).suffix.lower()
    if file_extension not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail=f"Файл должен быть изображением. Разрешенные форматы: {ALLOWED_EXTENSIONS}"
        )
    
    file_size = 0
    chunk_size = 1024
    while chunk := await file.read(chunk_size):
        file_size += len(chunk)
        if file_size > 10 * 1024 * 1024:  # 10MB
            raise HTTPException(
                status_code=400,
                detail="Файл слишком большой. Максимальный размер: 10MB"
            )
    
    await file.seek(0)
    
    unique_filename = f"{uuid.uuid4()}{file_extension}"
    file_path = UPLOAD_DIR / unique_filename
    
    try:
        with open(file_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Ошибка при сохранении файла: {str(e)}")
    finally:
        await file.close()
    
    file_url = f"/static/{unique_filename}"
    
    return {
        "filename": unique_filename,
        "original_filename": file.filename,
        "url": file_url,
        "size": file_size,
        "content_type": file.content_type,
        "message": "Файл успешно загружен"
    }

@main_app.post("/recipes/", response_model=Recipe, status_code=201)
async def create_recipe(recipe: RecipeCreate):
    """Создать новый рецепт"""
    global recipe_counter
    recipe_counter += 1
    
    recipe_dict = recipe.model_dump()
    recipe_dict["id"] = recipe_counter
    recipe_dict["created_at"] = datetime.now()
    recipe_dict["updated_at"] = datetime.now()
    
    new_recipe = Recipe(**recipe_dict)
    recipes_db[recipe_counter] = new_recipe
    
    return new_recipe

@main_app.get("/recipes/", response_model=List[Recipe])
async def get_all_recipes(
    skip: int = Query(0, ge=0, description="Сколько пропустить"),
    limit: int = Query(10, ge=1, le=100, description="Сколько вернуть"),
    difficulty: Optional[int] = Query(None, ge=1, le=5, description="Фильтр по сложности")
):
    """Получить список всех рецептов с возможностью фильтрации"""
    all_recipes = list(recipes_db.values())
    
    if difficulty:
        all_recipes = [r for r in all_recipes if r.difficulty == difficulty]
    
    return all_recipes[skip:skip + limit]

@main_app.get("/recipes/{recipe_id}", response_model=Recipe)
async def get_recipe(recipe_id: int):
    """Получить рецепт по ID"""
    if recipe_id not in recipes_db:
        raise HTTPException(
            status_code=404, 
            detail=f"Рецепт с ID {recipe_id} не найден"
        )
    return recipes_db[recipe_id]

@main_app.put("/recipes/{recipe_id}", response_model=Recipe)
async def update_recipe(recipe_id: int, recipe_update: RecipeUpdate):
    """Обновить рецепт"""
    if recipe_id not in recipes_db:
        raise HTTPException(
            status_code=404, 
            detail=f"Рецепт с ID {recipe_id} не найден"
        )
    
    current_recipe = recipes_db[recipe_id]
    update_data = recipe_update.model_dump(exclude_unset=True)
    updated_recipe = current_recipe.model_copy(update=update_data)
    updated_recipe.updated_at = datetime.now()
    
    recipes_db[recipe_id] = updated_recipe
    
    return updated_recipe

@main_app.delete("/recipes/{recipe_id}", status_code=204)
async def delete_recipe(recipe_id: int):
    """Удалить рецепт"""
    if recipe_id not in recipes_db:
        raise HTTPException(
            status_code=404, 
            detail=f"Рецепт с ID {recipe_id} не найден"
        )
    
    del recipes_db[recipe_id]
    return None

@main_app.get("/test")
async def test_endpoint():
    """Простой тестовый маршрут"""
    return {
        "message": "✅ API работает правильно!",
        "status": "ok",
        "timestamp": datetime.now().isoformat(),
        "endpoints": {
            "docs": "/docs",
            "redoc": "/redoc",
            "recipes": "/recipes/",
            "examples": "/examples/query-validation/"
        }
    }

main_app.include_router(api_router)

if __name__ == "__main__":
    print("🚀 Запуск FastAPI приложения...")
    print(f"📚 Документация будет доступна по адресу: http://{settings.run.host}:{settings.run.port}/docs")
    uvicorn.run(
        "main:main_app",
        host=settings.run.host,
        port=settings.run.port,
        reload=settings.run.reload,
    )