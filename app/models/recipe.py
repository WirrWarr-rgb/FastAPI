from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy import String, Text, Integer, ForeignKey
from .base import Base

class RecipeAllergens(Base):
    __tablename__ = "recipe_allergens"

    recipe_id: Mapped[int] = mapped_column(
        ForeignKey("recipes.id", ondelete="CASCADE"), 
        primary_key=True
    )
    allergen_id: Mapped[int] = mapped_column(
        ForeignKey("allergens.id", ondelete="CASCADE"), 
        primary_key=True
    )

class RecipeIngredient(Base):
    __tablename__ = "recipe_ingredients"

    id: Mapped[int] = mapped_column(primary_key=True)
    recipe_id: Mapped[int] = mapped_column(
        ForeignKey("recipes.id", ondelete="CASCADE"), 
        nullable=False
    )
    ingredient_id: Mapped[int] = mapped_column(
        ForeignKey("ingredients.id", ondelete="CASCADE"), 
        nullable=False
    )
    quantity: Mapped[int] = mapped_column(Integer, nullable=False)
    measurement: Mapped[int] = mapped_column(Integer, nullable=False)

    recipe: Mapped["Recipe"] = relationship(
        back_populates="recipe_ingredients"
    )
    ingredient: Mapped["Ingredient"] = relationship(
        back_populates="recipe_ingredients"
    )

class Recipe(Base):
    __tablename__ = "recipes"

    id: Mapped[int] = mapped_column(primary_key=True)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=True)
    instructions: Mapped[str] = mapped_column(Text, nullable=False)
    cooking_time: Mapped[int] = mapped_column(Integer, nullable=False)
    difficulty: Mapped[int] = mapped_column(Integer, nullable=False, default=1)

    cuisine_id: Mapped[int] = mapped_column(
        ForeignKey("cuisines.id", ondelete="CASCADE"), 
        nullable=False
    )

    cuisine: Mapped["Cuisine"] = relationship(
        back_populates="recipes"
    )
    allergens: Mapped[list["Allergen"]] = relationship(
        secondary="recipe_allergens",
        back_populates="recipes"
    )
    recipe_ingredients: Mapped[list["RecipeIngredient"]] = relationship(
        back_populates="recipe",
        cascade="all, delete-orphan"
    )

    def __repr__(self):
        return f"<Recipe(id={self.id}, title={self.title})>"