import os
import json
import hashlib
from graph.client import GraphClient
from ai.model_router import model_router
from memory.cache import cache_client
from ai.runtime_settings import settings

class TaskAgent:
    async def run(self, access_token: str, user_query: str, provider: str = "microsoft") -> dict:
        """
        Fetches tasks from Microsoft To-Do and Microsoft Planner (or Google Tasks), maps their attributes
        to a unified format, and identifies overdue tasks, high-priority tasks, and blockers.
        """
        try:
            processed_tasks = []
            
            if provider == "google":
                # Google Tasks API
                import httpx
                async with httpx.AsyncClient() as client:
                    # Get task lists
                    lists_resp = await client.get(
                        "https://tasks.googleapis.com/tasks/v1/users/@me/lists",
                        headers={"Authorization": f"Bearer {access_token}"}
                    )
                    task_lists = lists_resp.json().get("items", []) if lists_resp.status_code == 200 else []
                    all_tasks = []
                    for tl in task_lists[:3]:
                        tasks_resp = await client.get(
                            f"https://tasks.googleapis.com/tasks/v1/lists/{tl['id']}/tasks",
                            params={"showCompleted": False, "maxResults": 20},
                            headers={"Authorization": f"Bearer {access_token}"}
                        )
                        if tasks_resp.status_code == 200:
                            all_tasks.extend(tasks_resp.json().get("items", []))
                    tasks_data = [
                        {"title": t.get("title", ""), "due": t.get("due", ""), "status": t.get("status", "needsAction")}
                        for t in all_tasks
                    ]
            else:
                # Existing Microsoft call — keep as is
                graph = GraphClient(access_token)
                tasks_data = await graph.get_tasks()

            if provider == "google":
                for t in tasks_data:
                    status = t.get("status", "needsAction")
                    if status == "needsAction":
                        status = "notStarted"
                    elif status == "completed":
                        status = "completed"
                    processed_tasks.append({
                        "title": t.get("title", "")[:100],
                        "status": status,
                        "importance": "normal",
                        "dueDateTime": t.get("due", ""),
                        "source": "Google Tasks"
                    })
            else:
                for task in tasks_data:
                    processed_tasks.append({
                        "title": task.get("title", "")[:100],
                        "status": task.get("status", ""),
                        "importance": task.get("importance", ""),
                        "dueDateTime": task.get("dueDateTime", {}).get("dateTime", "") if task.get("dueDateTime") else "",
                        "source": "Microsoft To-Do"
                    })

                planner_tasks = []
                try:
                    planner_tasks = await graph.get_planner_tasks()
                except Exception as ex:
                    print(f"Planner tasks fetch error: {ex}")
                
                # Map Planner tasks
                for task in planner_tasks:
                    priority_val = task.get("priority", 5)
                    importance = "normal"
                    if priority_val in [1, 2, 3, 4]:
                        importance = "high"
                    elif priority_val == 9:
                        importance = "low"
                    
                    pct = task.get("percentComplete", 0)
                    status = "inProgress"
                    if pct == 100:
                        status = "completed"
                    elif pct == 0:
                        status = "notStarted"

                    processed_tasks.append({
                        "title": task.get("title", "")[:100],
                        "status": status,
                        "importance": importance,
                        "dueDateTime": task.get("dueDateTime", "") if task.get("dueDateTime") else "",
                        "source": "Microsoft Planner"
                    })

            # 2. Caching layer optimization
            raw_json = json.dumps(processed_tasks, sort_keys=True)
            data_hash = hashlib.md5(raw_json.encode('utf-8')).hexdigest()
            cache_key = f"task_agent:{data_hash}:{hashlib.md5(user_query.encode('utf-8')).hexdigest()}"
            
            cached_result = await cache_client.get(cache_key)
            if cached_result:
                return cached_result

            # 3. Prompt definition
            prompt = f"""
You are a Workload and Delivery Analyst reviewing the user's task boards (Microsoft To-Do and Microsoft Planner).
Analyze these tasks collected from the workspace:
{json.dumps(processed_tasks, indent=1)}

Based on these tasks, extract:
1) Overdue Tasks: Tasks that have passed their due date.
2) High Risk Tasks: Overdue tasks, late deliverables, or items with immediate scheduling risks.
3) Time Saved: Estimated time saved by automating this sync (e.g., 15 minutes).

Context (what the user is asking about): {user_query}
"""
            schema = {
                "overdue_tasks": [{"title": "task title", "due_date": "due date/time", "owner": "task owner name/assignee"}],
                "high_risk_tasks": ["description of high risk task"],
                "time_saved_minutes": 15
            }
            
            preferred_model = getattr(settings, "per_analyst_models", {}).get("task")
            result = await model_router.structured_extract(
                content=prompt,
                schema=schema,
                preferred_model=preferred_model
            )
            
            # Dynamically calculate time saved minutes
            calculated_time_saved = max(10, len(processed_tasks) * 5)
            time_saved_minutes = int(result.get("time_saved_minutes") or calculated_time_saved)

            structured_res = {
                "overdue_tasks": result.get("overdue_tasks", []),
                "high_risk_tasks": result.get("high_risk_tasks", []),
                "time_saved_minutes": time_saved_minutes
            }
            
            # Cache the result
            await cache_client.set(cache_key, structured_res, ttl=settings.graph_cache_ttl)
            return structured_res

        except Exception as e:
            return {
                "overdue_tasks": [],
                "high_risk_tasks": [],
                "time_saved_minutes": 0,
                "error": str(e)
            }
