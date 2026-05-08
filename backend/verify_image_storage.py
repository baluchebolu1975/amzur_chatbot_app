"""
Verify that generated images are stored in Supabase as base64 data URLs
"""

import asyncio
import os
import sys
from dotenv import load_dotenv

# Load .env
load_dotenv(dotenv_path=os.path.join(os.path.dirname(__file__), ".env"))

DATABASE_URL = os.getenv("DATABASE_URL")


async def verify_image_storage():
    """Query Supabase and verify base64 image storage"""
    
    if not DATABASE_URL:
        print("❌ DATABASE_URL not set")
        sys.exit(1)

    try:
        import asyncpg
    except ImportError:
        print("❌ asyncpg not installed. Run: pip install asyncpg")
        sys.exit(1)

    # Convert to sync PostgreSQL URL
    url = DATABASE_URL.replace("postgresql+asyncpg://", "postgresql://")

    print("=" * 70)
    print("VERIFYING GENERATED IMAGES IN SUPABASE")
    print("=" * 70)

    try:
        conn = await asyncpg.connect(url, timeout=10)

        # Query for messages containing generated images
        rows = await conn.fetch("""
            SELECT 
                m.id,
                m.thread_id,
                m.role,
                m.content,
                m.created_at,
                LENGTH(m.content) as content_length
            FROM messages m
            WHERE m.content LIKE '%![Generated image](data:image/%'
            ORDER BY m.created_at DESC
            LIMIT 10
        """)

        if not rows:
            print("\n⚠️  No generated images found in messages table")
            print("\nThis could mean:")
            print("  1. Images haven't been generated yet")
            print("  2. Images were stored differently")
            await conn.close()
            return

        print(f"\n✅ Found {len(rows)} generated image messages in Supabase!\n")

        for i, row in enumerate(rows, 1):
            print(f"\n{'─' * 70}")
            print(f"Image #{i}")
            print(f"{'─' * 70}")
            print(f"Message ID:      {row['id']}")
            print(f"Thread ID:       {row['thread_id']}")
            print(f"Role:            {row['role']}")
            print(f"Created At:      {row['created_at']}")
            print(f"Content Length:  {row['content_length']} characters")
            
            content = row['content']
            
            # Extract and verify base64 format
            if "![Generated image](data:image/" in content:
                print(f"✅ Markdown image format detected")
                
                # Extract data URL
                start_idx = content.find("(") + 1
                end_idx = content.find(")")
                data_url = content[start_idx:end_idx]
                
                print(f"\n📊 Data URL Preview:")
                print(f"  Format: {data_url[:50]}...")
                
                # Validate base64
                if ";base64," in data_url:
                    mime_type = data_url.split(";")[0].replace("data:", "")
                    b64_data = data_url.split(",")[1]
                    
                    print(f"  MIME Type: {mime_type}")
                    print(f"  Base64 Length: {len(b64_data)} characters")
                    print(f"✅ Base64 format confirmed!")
                    
                    # Verify base64 validity
                    try:
                        import base64
                        decoded = base64.b64decode(b64_data)
                        print(f"✅ Base64 decode successful: {len(decoded)} bytes")
                        
                        # Try to detect image type from header
                        if decoded[:8] == b'\x89PNG\r\n\x1a\n':
                            print(f"✅ Valid PNG image detected")
                        elif decoded[:3] == b'\xff\xd8\xff':
                            print(f"✅ Valid JPEG image detected")
                        elif decoded[:4] == b'GIF8':
                            print(f"✅ Valid GIF image detected")
                        else:
                            print(f"⚠️  Unknown image format (first 4 bytes: {decoded[:4]})")
                    except Exception as e:
                        print(f"❌ Base64 decode failed: {e}")
                else:
                    print(f"❌ Not in base64 format - missing ';base64,' separator")
            else:
                print(f"❌ Not in markdown image format")

        print(f"\n{'=' * 70}")
        print("✅ VERIFICATION COMPLETE")
        print("=" * 70)
        
        await conn.close()

    except Exception as e:
        print(f"\n❌ Error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(verify_image_storage())
