from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime

class RecipeBase(BaseModel):
    title: str = Field(..., min_length=3, max_length=100)
    description: Optional[str] = Field(None, max_length=500)
    ingredients: List[str] = Field(..., min_items=1)
    instructions: str = Field(..., min_length=10)
    cooking_time: int = Field(..., gt=0)
    difficulty: int = Field(..., ge=1, le=5)

class RecipeCreate(RecipeBase):
    pass

class RecipeUpdate(BaseModel):
    title: Optional[str] = Field(None, min_length=3, max_length=100)
    description: Optional[str] = Field(None, max_length=500)
    ingredients: Optional[List[str]] = Field(None, min_items=1)
    instructions: Optional[str] = Field(None, min_length=10)
    cooking_time: Optional[int] = Field(None, gt=0)
    difficulty: Optional[int] = Field(None, ge=1, le=5)

class Recipe(RecipeBase):
    id: int
    created_at: datetime
    updated_at: datetime
    
    class Config:
        from_attributes = True