import asyncio
from supabase import create_client
import os
from dotenv import load_dotenv

load_dotenv('backend/.env')

url = os.environ.get("SUPABASE_URL")
key = os.environ.get("SUPABASE_SERVICE_ROLE_KEY")

if not url or not key:
    print("Missing env vars")
    exit(1)

supabase = create_client(url, key)

async def check():
    # Attempt a manual raw insert to test permissions once and for all
    test_task = {
        "task_id": "test-id-" + str(os.urandom(4).hex()),
        "task": "Diagnostic Test Task",
        "owner": "Agent",
        "priority": "low",
        "status": "pending",
        "deadline": "2026-12-31"
    }
    try:
        res_ins = supabase.table("tasks").insert(test_task).execute()
        print(f"Insert Res: {res_ins.data}")
    except Exception as e:
        print(f"Insert Error: {e}")

    res = supabase.from_('tasks').select('*').limit(5).execute()
    print(f"Tasks in DB: {len(res.data)}")
    for t in res.data:
        print(f"User: {t.get('user_id')} - Task: {t.get('task')}")

asyncio.run(check())
