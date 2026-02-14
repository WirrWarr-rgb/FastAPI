from fastapi import (
    APIRouter,
)
from config import settings

router = APIRouter(
    tags=["Test"],
    prefix=settings.url.test,
)


@router.get("")
def index():
    return {"message": "Hello, World!"}
