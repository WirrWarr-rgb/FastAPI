from fastapi import APIRouter

from config import settings

from .test import router as test_router
from .posts import router as posts_router
from .recipes import router as recipes_router
from .examples import router as examples_router

router = APIRouter(
    prefix=settings.url.prefix,
)
router.include_router(test_router)
router.include_router(posts_router)
router.include_router(recipes_router)
router.include_router(examples_router)