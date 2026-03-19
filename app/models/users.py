from fastapi_users.db import SQLAlchemyBaseUserTable
from sqlalchemy import Integer
from sqlalchemy.orm import Mapped, mapped_column, relationship
from .base import Base
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .recipe import Recipe

class User(SQLAlchemyBaseUserTable[int], Base):
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    
    # связь с рецептами пользователя
    recipes: Mapped[list["Recipe"]] = relationship(
        "Recipe", 
        back_populates="author",
        cascade="all, delete-orphan"
    )