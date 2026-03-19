from fastapi import APIRouter, Depends
from fastapi.security import HTTPBearer

from config import settings

from .recipes import router as recipes_router
from .cuisines import router as cuisines_router
from .allergens import router as allergens_router
from .ingredients import router as ingredients_router
from .auth import router as auth_router
from .users import router as users_router 

http_bearer = HTTPBearer(auto_error=False)

router = APIRouter(
    prefix=settings.url.prefix,
    dependencies=[Depends(http_bearer)],
)
router.include_router(recipes_router)
router.include_router(cuisines_router)
router.include_router(allergens_router)
router.include_router(ingredients_router)
router.include_router(auth_router)
router.include_router(users_router)