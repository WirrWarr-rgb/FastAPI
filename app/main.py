import uvicorn
from fastapi import FastAPI
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from contextlib import asynccontextmanager
from pathlib import Path

from config import settings
from models import db_helper, Base
from api import router as api_router

# папка для загрузок
UPLOAD_DIR = Path("uploads")
UPLOAD_DIR.mkdir(exist_ok=True)

@asynccontextmanager
async def lifespan(app: FastAPI):
    print("Запуск приложения...")
    async with db_helper.engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    print("База данных готова")
    
    yield
    
    print("Остановка приложения...")
    await db_helper.dispose()
    print("Ресурсы освобождены")

main_app = FastAPI(
    title="API для рецептов",
    description="API для управления рецептами с примерами из документации FastAPI",
    version="1.0.0",
    lifespan=lifespan,
)

main_app.include_router(api_router)

# статические файлы
main_app.mount("/static", StaticFiles(directory="uploads"), name="static")

if __name__ == "__main__":
    print("Запуск FastAPI приложения...")
    print(f"Документация: http://{settings.run.host}:{settings.run.port}/docs")
    uvicorn.run(
        "main:main_app",
        host=settings.run.host,
        port=settings.run.port,
        reload=settings.run.reload,
    )