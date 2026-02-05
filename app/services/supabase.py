"""Supabase client initialization."""
import os
from supabase import create_client, Client

url = os.getenv("SUPABASE_URL")
key = os.getenv("SUPABASE_KEY")

if not url or not key:
    import os
    env_path = os.path.join(os.getcwd(), ".env")
    env_exists = os.path.exists(env_path)
    raise ValueError(
        f"Missing SUPABASE_URL or SUPABASE_KEY environment variables. "
        f"Current working directory: {os.getcwd()}. "
        f".env file exists: {env_exists}"
    )

supabase: Client = create_client(url, key)
