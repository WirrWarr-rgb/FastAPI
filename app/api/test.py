from fastapi import APIRouter
from datetime import datetime

router = APIRouter(
    tags=["Test"],
    prefix="/test",
)

@router.get("")
def index():
    return {"message": "Hello, World!"}

@router.get("/status")
async def test_endpoint():
    """Простой тестовый маршрут"""
    return {
        "message": "API работает правильно!",
        "status": "ok",
        "timestamp": datetime.now().isoformat(),
        "endpoints": {
            "docs": "/docs",
            "redoc": "/redoc",
            "recipes": "/recipes/",
            "examples": "/examples/"
        }
    }