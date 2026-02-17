from fastapi import APIRouter, Body, Query, Path, Form, File, UploadFile, HTTPException
from fastapi.responses import HTMLResponse, JSONResponse
from pydantic import BaseModel, Field
from typing import Optional, List, Annotated
from datetime import datetime
import uuid
import shutil
from pathlib import Path

from config import settings

router = APIRouter(
    tags=["Examples"],
    prefix="/examples",
)

UPLOAD_DIR = Path("uploads")
UPLOAD_DIR.mkdir(exist_ok=True)
ALLOWED_EXTENSIONS = {".png", ".jpg", ".jpeg", ".webp"}

# модели для примеров
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

# Body
@router.post("/body/")
async def create_item_with_body(
    item: Item, 
    user: User, 
    importance: int = Body(ge=1, le=10, description="Важность от 1 до 10")
):
    """Пример с Body параметрами"""
    return {
        "item": item,
        "user": user,
        "importance": importance,
        "message": "Объекты успешно созданы"
    }

# Query Parameters and String Validations
@router.get("/query-validation/")
async def read_items(
    q: Annotated[
        Optional[str], 
        Query(
            min_length=3, 
            max_length=50,
            regex="^[a-zA-Z0-9 ]+$",
            description="Поисковый запрос"
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

# Path Parameters and Numeric Validations
@router.get("/path-validation/{item_id}")
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

# Query Parameter Models
@router.get("/query-model/")
async def read_items_with_model(
    filter_query: Annotated[FilterParams, Query()]
):
    """Пример с моделью для query параметров"""
    return {
        "applied_filters": filter_query,
        "message": f"Получено {filter_query.limit} записей со смещением {filter_query.offset}",
        "items": [f"Item {i}" for i in range(filter_query.offset, filter_query.offset + filter_query.limit)]
    }

# Nested Models
@router.post("/nested-models/")
async def create_product(product: Product):
    """Пример с вложенными моделями"""
    return {
        "product": product,
        "message": "Продукт успешно создан",
        "total_images": len(product.images) + (1 if product.image else 0)
    }

# Request Forms
@router.post("/form/")
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

# Request Form Models
@router.post("/form-model/")
async def handle_form_model(form_data: Annotated[FormData, Form()]):
    """Пример с моделью для Form данных"""
    return {
        "received_data": form_data,
        "message": "Модель формы успешно обработана"
    }

# Обработка query-параметра format
@router.get("/format-example/")
async def format_response(
    format: str = Query(
        "json", 
        regex="^(json|html)$",
        description="Формат ответа: json или html"
    )
):
    """Маршрут, возвращающий данные в JSON или HTML формате"""
    data = {
        "title": "Пример данных",
        "description": "Это тестовые данные",
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

# Загрузка изображений
@router.post("/upload-image/")
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
        if file_size > 10 * 1024 * 1024:
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