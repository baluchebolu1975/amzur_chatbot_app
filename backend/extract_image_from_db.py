"""
Extract and save one generated image from Supabase to view it
"""

import asyncio
import base64
import os
import sys
from dotenv import load_dotenv

load_dotenv(dotenv_path=os.path.join(os.path.dirname(__file__), ".env"))

DATABASE_URL = os.getenv("DATABASE_URL")


async def extract_image():
    """Extract latest generated image and save to file"""
    
    if not DATABASE_URL:
        print("❌ DATABASE_URL not set")
        sys.exit(1)

    try:
        import asyncpg
    except ImportError:
        print("❌ asyncpg not installed")
        sys.exit(1)

    url = DATABASE_URL.replace("postgresql+asyncpg://", "postgresql://")

    try:
        conn = await asyncpg.connect(url, timeout=10)

        # Get the most recent generated image
        row = await conn.fetchrow("""
            SELECT 
                m.content,
                m.created_at
            FROM messages m
            WHERE m.content LIKE '%![Generated image](data:image/%'
            ORDER BY m.created_at DESC
            LIMIT 1
        """)

        if not row:
            print("❌ No generated images found")
            await conn.close()
            return

        content = row['content']
        
        # Extract data URL
        start_idx = content.find("(") + 1
        end_idx = content.find(")")
        data_url = content[start_idx:end_idx]
        
        # Extract base64 data
        b64_data = data_url.split(",")[1]
        
        # Decode
        image_bytes = base64.b64decode(b64_data)
        
        # Save to file
        output_path = os.path.join(os.path.dirname(__file__), "test-assets", "sample_generated_image.png")
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        
        with open(output_path, "wb") as f:
            f.write(image_bytes)
        
        print(f"✅ Image extracted and saved!")
        print(f"   Path: {output_path}")
        print(f"   Size: {len(image_bytes)} bytes")
        print(f"   Created: {row['created_at']}")
        print(f"\n📂 You can now open this file to view the generated image.")
        
        await conn.close()

    except Exception as e:
        print(f"❌ Error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(extract_image())
