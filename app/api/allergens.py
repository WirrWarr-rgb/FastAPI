from typing import Annotated
from fastapi import APIRouter, Depends, status, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from models import db_helper, Allergen
from pydantic import BaseModel

router = APIRouter(tags=["Allergens"], prefix="/Allergens")

class AllergenRead(BaseModel):
    id: int
    name: str

class AllergenCreate(BaseModel):
    name: str

@router.get("", response_model=list[AllergenRead])
async def index(session: Annotated[AsyncSession, Depends(db_helper.session_getter)]):
    stmt = select(Allergen).order_by(Allergen.id)
    result = await session.scalars(stmt)
    return result.all()

@router.post("", response_model=AllergenRead, status_code=status.HTTP_201_CREATED)
async def store(
    session: Annotated[AsyncSession, Depends(db_helper.session_getter)],
    Allergen_create: AllergenCreate,
):
    Allergen = Allergen(name=Allergen_create.name)
    session.add(Allergen)
    await session.commit()
    await session.refresh(Allergen)
    return Allergen

@router.get("/{id}", response_model=AllergenRead)
async def show(session: Annotated[AsyncSession, Depends(db_helper.session_getter)], id: int):
    Allergen = await session.get(Allergen, id)
    if not Allergen:
        raise HTTPException(status_code=404, detail="Allergen not found")
    return Allergen

@router.put("/{id}", response_model=AllergenRead)
async def update(
    session: Annotated[AsyncSession, Depends(db_helper.session_getter)],
    id: int,
    Allergen_update: AllergenCreate,
):
    Allergen = await session.get(Allergen, id)
    if not Allergen:
        raise HTTPException(status_code=404, detail="Allergen not found")
    Allergen.name = Allergen_update.name
    await session.commit()
    await session.refresh(Allergen)
    return Allergen

@router.delete("/{id}", status_code=status.HTTP_204_NO_CONTENT)
async def destroy(session: Annotated[AsyncSession, Depends(db_helper.session_getter)], id: int):
    Allergen = await session.get(Allergen, id)
    if not Allergen:
        raise HTTPException(status_code=404, detail="Allergen not found")
    await session.delete(Allergen)
    await session.commit()
    return None