"""
Supabase Connection Test
Run this from inside the backend/ folder with your venv activated:
  python test_supabase.py
"""

import asyncio
import os
import sys
from dotenv import load_dotenv

# Load .env from the same folder as this script
load_dotenv(dotenv_path=os.path.join(os.path.dirname(__file__), ".env"))

DATABASE_URL = os.getenv("DATABASE_URL")


def check_env():
    """Make sure DATABASE_URL is set before attempting connection."""
    if not DATABASE_URL:
        print("❌ DATABASE_URL is not set in your .env file.")
        print("   Make sure the .env file is in the same folder as this script.")
        sys.exit(1)

    if "YOUR-PASSWORD" in DATABASE_URL or DATABASE_URL.endswith("="):
        print("❌ DATABASE_URL looks incomplete — password placeholder not replaced.")
        sys.exit(1)

    print(f"✅ DATABASE_URL found in .env")
    # Show a masked version so you can verify the host without exposing the password
    masked = DATABASE_URL.split("@")[-1]
    print(f"   Connecting to: {masked}")


async def test_connection():
    """Attempt to connect to Supabase and run basic checks."""
    try:
        import asyncpg
    except ImportError:
        print("\n❌ asyncpg is not installed.")
        print("   Run: pip install asyncpg")
        sys.exit(1)

    # asyncpg expects postgresql:// not postgresql+asyncpg://
    url = DATABASE_URL.replace("postgresql+asyncpg://", "postgresql://")

    print("\n⏳ Connecting to Supabase...")

    try:
        conn = await asyncpg.connect(url, timeout=10)

        # Test 1 — Basic connectivity
        version = await conn.fetchval("SELECT version()")
        print(f"\n✅ Connection successful!")
        print(f"   PostgreSQL: {version.split(',')[0]}")

        # Test 2 — Check which tables exist
        tables = await conn.fetch("""
            SELECT table_name
            FROM information_schema.tables
            WHERE table_schema = 'public'
            ORDER BY table_name
        """)

        if tables:
            table_names = [t["table_name"] for t in tables]
            print(f"\n✅ Tables found in database: {table_names}")
            if "users" in table_names and "messages" in table_names:
                print("   ✅ 'users' and 'messages' tables exist — migrations already run!")
            else:
                print("   ℹ️  Core tables not yet created — run 'alembic upgrade head' when course code arrives.")
        else:
            print("\n   ℹ️  No tables yet — this is expected before running migrations.")
            print("   Run 'alembic upgrade head' once you have the P2.1 course code.")

        # Test 3 — Check connection count (Supabase free tier limit: 20)
        conn_count = await conn.fetchval(
            "SELECT count(*) FROM pg_stat_activity WHERE datname = current_database()"
        )
        print(f"\n✅ Active connections: {conn_count} / 20 (free tier limit)")

        await conn.close()
        print("\n🎉 All checks passed — Supabase is configured correctly!\n")

    except asyncpg.InvalidPasswordError:
        print("\n❌ Wrong password — check your DATABASE_URL in .env")
        print("   Make sure special characters are URL-encoded (@=%%40, #=%%23)")

    except asyncpg.InvalidCatalogNameError:
        print("\n❌ Database not found — check the database name in your connection string")

    except (OSError, asyncpg.CannotConnectNowError, Exception) as e:
        if "getaddrinfo" in str(e) or "Name or service not known" in str(e):
            print(f"\n❌ Cannot reach Supabase host — check your internet connection")
        else:
            print(f"\n❌ Connection failed: {e}")


if __name__ == "__main__":
    print("=" * 55)
    print("   Supabase Connection Test")
    print("=" * 55)
    check_env()
    asyncio.run(test_connection())