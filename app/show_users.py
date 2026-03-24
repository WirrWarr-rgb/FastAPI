import asyncio
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from sqlalchemy import select
from config import settings
from models import User

async def show_users():
    engine = create_async_engine(str(settings.db.url))
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    
    async with async_session() as session:
        result = await session.execute(select(User))
        users = result.scalars().all()
        
        print("\n" + "="*60)
        print("СПИСОК ПОЛЬЗОВАТЕЛЕЙ")
        print("="*60)
        
        if not users:
            print("Нет пользователей в базе данных")
        else:
            for u in users:
                print(f"ID: {u.id}")
                print(f"  Email: {u.email}")
                print(f"  Активен: {u.is_active}")
                print(f"  Суперпользователь: {u.is_superuser}")
                print(f"  Верифицирован: {u.is_verified}")
                print("-"*40)
    
    await engine.dispose()

if __name__ == "__main__":
    asyncio.run(show_users())