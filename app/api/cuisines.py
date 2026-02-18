from typing import Annotated
from fastapi import APIRouter, Depends, status, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from models import db_helper, Cuisine
from pydantic import BaseModel

router = APIRouter(tags=["Cuisines"], prefix="/cuisines")

class CuisineRead(BaseModel):
    id: int
    name: str

class CuisineCreate(BaseModel):
    name: str

@router.get("", response_model=list[CuisineRead])
async def index(session: Annotated[AsyncSession, Depends(db_helper.session_getter)]):
    stmt = select(Cuisine).order_by(Cuisine.id)
    result = await session.scalars(stmt)
    return result.all()

@router.post("", response_model=CuisineRead, status_code=status.HTTP_201_CREATED)
async def store(
    session: Annotated[AsyncSession, Depends(db_helper.session_getter)],
    cuisine_create: CuisineCreate,
):
    cuisine = Cuisine(name=cuisine_create.name)
    session.add(cuisine)
    await session.commit()
    await session.refresh(cuisine)
    return cuisine

@router.get("/{id}", response_model=CuisineRead)
async def show(session: Annotated[AsyncSession, Depends(db_helper.session_getter)], id: int):
    cuisine = await session.get(Cuisine, id)
    if not cuisine:
        raise HTTPException(status_code=404, detail="Cuisine not found")
    return cuisine

@router.put("/{id}", response_model=CuisineRead)
async def update(
    session: Annotated[AsyncSession, Depends(db_helper.session_getter)],
    id: int,
    cuisine_update: CuisineCreate,
):
    cuisine = await session.get(Cuisine, id)
    if not cuisine:
        raise HTTPException(status_code=404, detail="Cuisine not found")
    cuisine.name = cuisine_update.name
    await session.commit()
    await session.refresh(cuisine)
    return cuisine

@router.delete("/{id}", status_code=status.HTTP_204_NO_CONTENT)
async def destroy(session: Annotated[AsyncSession, Depends(db_helper.session_getter)], id: int):
    cuisine = await session.get(Cuisine, id)
    if not cuisine:
        raise HTTPException(status_code=404, detail="Cuisine not found")
    await session.delete(cuisine)
    await session.commit()
    return None