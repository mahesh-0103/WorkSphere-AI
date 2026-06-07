import os
from supabase import create_client, Client

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

async def save_briefing(user_email: str, query: str, preview: str, full_briefing: str):
    try:
        supabase.table("briefing_history").insert({
            "user_email": user_email,
            "query": query,
            "preview": preview,
            "full_briefing": full_briefing
        }).execute()
    except Exception as e:
        print(f"Supabase briefing save error: {e}")

async def get_briefing_history(user_email: str) -> list:
    try:
        result = supabase.table("briefing_history")\
            .select("id,query,preview,full_briefing,created_at")\
            .eq("user_email", user_email)\
            .order("created_at", desc=True)\
            .limit(20)\
            .execute()
        return result.data
    except Exception as e:
        print(f"Supabase briefing fetch error: {e}")
        return []

async def save_indexed_source(user_email: str, name: str, source_type: str, summary: str, keywords: list):
    try:
        supabase.table("indexed_sources").insert({
            "user_email": user_email,
            "name": name,
            "type": source_type,
            "summary": summary,
            "keywords": keywords
        }).execute()
    except Exception as e:
        print(f"Supabase source save error: {e}")

async def get_indexed_sources(user_email: str, query: str = "") -> list:
    try:
        q = supabase.table("indexed_sources").select("*").eq("user_email", user_email)
        if query:
            q = q.ilike("name", f"%{query}%")
        result = q.order("created_at", desc=True).execute()
        return result.data
    except Exception as e:
        print(f"Supabase source fetch error: {e}")
        return []
