from sqlalchemy.orm import Mapped
from sqlalchemy.orm import mapped_column
from sqlalchemy import String, Text, Integer, CheckConstraint
from sqlalchemy.dialects.sqlite import JSON

from .base import Base


class Recipe(Base):
    __tablename__ = "recipes"

    id: Mapped[int] = mapped_column(primary_key=True)
    title: Mapped[str] = mapped_column(String(255))
    ingredients: Mapped[dict] = mapped_column(JSON)
    instructions: Mapped[str] = mapped_column(Text)
    description: Mapped[str] = mapped_column(Text)
    cooking_time: Mapped[int] = mapped_column(Integer)
    difficulty: Mapped[int] = mapped_column(Integer, default=1)

    def __repr__(self):
        return f"Recipe(id={self.id}, title={self.title})"
