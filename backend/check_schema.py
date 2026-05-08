import asyncio
import os
from dotenv import load_dotenv

load_dotenv(dotenv_path=os.path.join(os.path.dirname(__file__), ".env"))

DATABASE_URL = os.getenv("DATABASE_URL")

async def check_schema():
    import asyncpg
    url = DATABASE_URL.replace("postgresql+asyncpg://", "postgresql://")
    conn = await asyncpg.connect(url, timeout=10)
    
    # Check threads table
    threads_cols = await conn.fetch("""
        SELECT column_name, data_type 
        FROM information_schema.columns 
        WHERE table_name = 'threads'
        ORDER BY ordinal_position
    """)
    
    print("Threads table columns:")
    for col in threads_cols:
        print(f"  - {col['column_name']}: {col['data_type']}")
    
    await conn.close()

asyncio.run(check_schema())
