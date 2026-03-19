import uvicorn
from fastapi import FastAPI
from contextlib import asynccontextmanager
from fastapi_pagination import add_pagination

from config import settings
from models import db_helper
from api import router as api_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Управление жизненным циклом приложения.
    Здесь можно добавить код при запуске и остановке.
    """
    # Startup
    print("Запуск приложения...")
    yield
    # Shutdown
    print("Остановка приложения...")
    await db_helper.dispose()
    print("Ресурсы освобождены")


main_app = FastAPI(
    title="API для рецептов",
    description="API для управления рецептами с примерами из документации FastAPI",
    version="1.0.0",
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
)

add_pagination(main_app)

main_app.include_router(api_router)


if __name__ == "__main__":
    print(f"Документация: http://{settings.run.host}:{settings.run.port}/docs")
    uvicorn.run(
        "main:main_app",
        host=settings.run.host,
        port=settings.run.port,
        reload=settings.run.reload,
    )