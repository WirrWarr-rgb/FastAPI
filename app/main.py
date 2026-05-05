import uvicorn
from fastapi import FastAPI
from contextlib import asynccontextmanager
from fastapi_pagination import add_pagination

from config import settings
from models import db_helper
from api import router as api_router
from task_queue import broker


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Управление жизненным циклом приложения.
    """
    # Startup
    print("🚀 Запуск приложения...")
    
    # запускаем брокер, если это не воркер
    if not broker.is_worker_process:
        await broker.startup()
    
    yield
    
    # Shutdown
    print("🛑 Остановка приложения...")
    await db_helper.dispose()
    
    # останавливаем брокер
    if not broker.is_worker_process:
        await broker.shutdown()
    
    print("✅ Ресурсы освобождены")


main_app = FastAPI(
    title="API для рецептов",
    description="API для управления рецептами с AI-генерацией",
    version="1.0.0",
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
)

add_pagination(main_app)

main_app.include_router(api_router)


if __name__ == "__main__":
    print(f"📚 Документация: http://{settings.run.host}:{settings.run.port}/docs")
    uvicorn.run(
        "main:main_app",
        host=settings.run.host,
        port=settings.run.port,
        reload=settings.run.reload,
    )