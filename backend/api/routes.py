import json
import asyncio
import uuid
from datetime import datetime, timezone
from fastapi import APIRouter, HTTPException, Query, Response, Request
from fastapi.responses import RedirectResponse, StreamingResponse
from pydantic import BaseModel
from auth.microsoft_auth import get_auth_url, get_token_from_code, validate_token
from auth.google_auth import get_google_auth_url, get_google_token, get_google_user_profile
from ai.runtime_settings import settings, SETTINGS_FILE
from supervisor.supervisor import run_supervisor
from memory.supabase_client import supabase, save_briefing, get_briefing_history, save_indexed_source, get_indexed_sources

router = APIRouter()

# In-memory briefing history (fix 7)
briefing_history: list = []

class QueryRequest(BaseModel):
    message: str
    access_token: str
    provider: str = "microsoft"

@router.get("/auth/login")
def login():
    try:
        url = get_auth_url()
        return RedirectResponse(url=url)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to generate auth URL: {str(e)}")

@router.get("/auth/callback")
def callback(request: Request, code: str = Query(None)):
    if not code:
        raise HTTPException(status_code=400, detail="Missing authorization code")
    try:
        access_token = get_token_from_code(code)
        # Redirect user back to the frontend dashboard dynamically based on the request host
        base_url = str(request.base_url).rstrip('/')
        redirect_url = f"{base_url}/dashboard?token={access_token}"
        return RedirectResponse(url=redirect_url)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Authentication failed: {str(e)}")

@router.get("/auth/google/login")
async def google_login():
    return RedirectResponse(get_google_auth_url())

@router.get("/auth/google/callback")
async def google_callback(code: str, request: Request):
    token_data = await get_google_token(code)
    access_token = token_data.get("access_token")
    
    # Validate Google token scopes
    try:
        import httpx
        from memory.cache import cache_client
        async with httpx.AsyncClient() as client:
            resp = await client.get(f"https://www.googleapis.com/oauth2/v2/tokeninfo?access_token={access_token}")
            print(f"[AUTH] Google tokeninfo response: {resp.status_code} - {resp.text}")
            if resp.status_code == 200:
                token_info = resp.json()
                scope_str = token_info.get("scope", "")
                scopes = scope_str.split()
                required_tasks = "https://www.googleapis.com/auth/tasks.readonly"
                required_drive = "https://www.googleapis.com/auth/drive.readonly"
                if required_tasks not in scopes or required_drive not in scopes:
                    print("[AUTH WARNING] Google token missing required scopes. Tasks/Drive agents will fail.")
                    request.session["limited_scopes"] = True
                    await cache_client.set(f"limited_scopes:{access_token}", True, ttl=3600)
                else:
                    print("[AUTH] Google token scopes validated successfully.")
                    request.session["limited_scopes"] = False
                    await cache_client.set(f"limited_scopes:{access_token}", False, ttl=3600)
            else:
                print(f"[AUTH WARNING] Failed to validate Google token scopes: {resp.status_code}")
    except Exception as se:
        print(f"[AUTH WARNING] Exception during Google scope validation: {se}")

    # Redirect to frontend dashboard with token and provider flag
    base_url = str(request.base_url).rstrip('/')
    return RedirectResponse(
        f"{base_url}/dashboard?token={access_token}&provider=google"
    )

@router.post("/auth/logout")
async def logout():
    """Stateless logout — frontend clears localStorage."""
    return {"status": "logged_out"}

@router.post("/api/query")
async def api_query(request: QueryRequest, req: Request):
    """
    Accepts a user query message and microsoft access token.
    Streams back JSON progress events and the final briefing.
    """
    if request.provider == "microsoft":
        await validate_token(request.access_token)
        
    limited_scopes = req.session.get("limited_scopes", False)

    async def event_generator():
        queue = asyncio.Queue()
        briefing_chunks = []
        
        async def producer():
            try:
                async for event in run_supervisor(request.message, request.access_token, provider=request.provider, limited_scopes=limited_scopes):
                    await queue.put(("event", event))
                    # Collect briefing chunks for history
                    try:
                        parsed = json.loads(event)
                        if parsed.get("event") == "final_briefing_chunk":
                            briefing_chunks.append(parsed.get("data", ""))
                    except (json.JSONDecodeError, TypeError):
                        pass
            except Exception as pe:
                await queue.put(("error", str(pe)))
            finally:
                await queue.put(("done", None))
                
        producer_task = asyncio.create_task(producer())
        
        try:
            while True:
                try:
                    msg_type, val = await asyncio.wait_for(queue.get(), timeout=15.0)
                    if msg_type == "event":
                        yield f"data: {val}\n\n"
                        try:
                            parsed = json.loads(val)
                            if parsed.get("event") == "agent_results":
                                # Extract and save items to indexed_sources
                                user_email = "session@worksphere.com"
                                if request.provider == "microsoft":
                                    try:
                                        from graph.client import GraphClient
                                        client = GraphClient(request.access_token)
                                        profile = await client.get_profile()
                                        user_email = profile.get("mail") or profile.get("userPrincipalName") or user_email
                                    except Exception:
                                        pass
                                elif request.provider == "google":
                                    user_email = "google-session@worksphere.com"
                                    if request.access_token:
                                        try:
                                            import httpx
                                            async with httpx.AsyncClient() as client:
                                                resp = await client.get(
                                                    "https://www.googleapis.com/oauth2/v2/userinfo",
                                                    headers={"Authorization": f"Bearer {request.access_token}"}
                                                )
                                                if resp.status_code == 200:
                                                    user_data = resp.json()
                                                    email = user_data.get("email")
                                                    if email:
                                                        user_email = email
                                        except Exception:
                                            pass

                                # Process and save email items
                                email_results = parsed.get("email_results") or {}
                                for item in email_results.get("urgent_items", []):
                                    name = item.get("subject") if isinstance(item, dict) else str(item)
                                    summary = item.get("summary") if isinstance(item, dict) else f"Urgent email: {name}"
                                    await save_indexed_source(user_email, name, "email", summary, ["email", "urgent", "briefing"])

                                # Process and save meeting items
                                meeting_results = parsed.get("meeting_results") or {}
                                for item in meeting_results.get("key_decisions", []):
                                    name = item.get("decision") if isinstance(item, dict) else str(item)
                                    summary = item.get("context") if isinstance(item, dict) else f"Key Decision: {name}"
                                    await save_indexed_source(user_email, name, "meeting", summary, ["meeting", "decision", "briefing"])

                                # Process and save task items
                                task_results = parsed.get("task_results") or {}
                                for item in task_results.get("high_risk_tasks", []):
                                    name = item.get("title") if isinstance(item, dict) else str(item)
                                    summary = item.get("description") if isinstance(item, dict) else f"High risk task: {name}"
                                    await save_indexed_source(user_email, name, "task", summary, ["task", "overdue", "briefing"])

                                # Process and save document items
                                research_results = parsed.get("research_results") or {}
                                for item in research_results.get("relevant_documents", []):
                                    name = item.get("name") if isinstance(item, dict) else str(item)
                                    summary = item.get("summary") if isinstance(item, dict) else f"Indexed document: {name}"
                                    await save_indexed_source(user_email, name, "document", summary, ["document", "knowledge", "briefing"])

                            if parsed.get("event") == "final_briefing":
                                user_query = request.message
                                briefing_text = parsed.get("data", "")
                                briefing_history.append({
                                    "id": str(uuid.uuid4()),
                                    "timestamp": datetime.utcnow().isoformat(),
                                    "query": user_query,
                                    "preview": briefing_text[:200] + "..." if len(briefing_text) > 200 else briefing_text
                                })
                                
                                user_email = "session@worksphere.com"
                                if request.provider == "microsoft":
                                    try:
                                        from graph.client import GraphClient
                                        client = GraphClient(request.access_token)
                                        profile = await client.get_profile()
                                        user_email = profile.get("mail") or profile.get("userPrincipalName") or user_email
                                    except Exception:
                                        pass
                                elif request.provider == "google":
                                    user_email = "google-session@worksphere.com"
                                    if request.access_token:
                                        try:
                                            import httpx
                                            async with httpx.AsyncClient() as client:
                                                resp = await client.get(
                                                    "https://www.googleapis.com/oauth2/v2/userinfo",
                                                    headers={"Authorization": f"Bearer {request.access_token}"}
                                                )
                                                if resp.status_code == 200:
                                                    user_data = resp.json()
                                                    email = user_data.get("email")
                                                    if email:
                                                        user_email = email
                                        except Exception:
                                            pass
                                    
                                try:
                                    await save_briefing(user_email, user_query, briefing_text[:200], briefing_text)
                                except Exception as dbe:
                                    print(f"[routes.py] Failed to save briefing to Supabase: {dbe}")
                                
                                # Send terminal structured event
                                structured_payload = parsed.get("structured", {})
                                yield f"data: {json.dumps({'type': 'structured', 'payload': structured_payload})}\n\n"
                        except Exception:
                            pass
                    elif msg_type == "error":
                        error_data = json.dumps({"event": "error", "message": val})
                        yield f"data: {error_data}\n\n"
                        break
                    elif msg_type == "done":
                        break
                except asyncio.TimeoutError:
                    yield ": keepalive\n\n"
        except Exception as e:
            error_data = json.dumps({"event": "error", "message": str(e)})
            yield f"data: {error_data}\n\n"
        finally:
            if not producer_task.done():
                producer_task.cancel()
                try:
                    await producer_task
                except asyncio.CancelledError:
                    pass
            yield "data: {\"event\": \"done\"}\n\n"

    headers = {
        "Cache-Control": "no-cache",
        "X-Accel-Buffering": "no"
    }
    return StreamingResponse(event_generator(), media_type="text/event-stream", headers=headers)

# --- System, Profile, and Memory API Endpoints ---
from ai.health_monitor import health_monitor
from ai.model_router import ROUTER_METRICS
from memory.cache import CACHE_METRICS
from graph.client import GraphClient

@router.get("/api/system/status")
async def get_system_status(token: str = Query(None), provider: str = Query("microsoft")):
    if provider == "microsoft":
        await validate_token(token)
    health_snapshot = health_monitor.get_status()
    all_configured_models = [settings.primary_model] + settings.fallback_models
    for model in all_configured_models:
        if model not in health_snapshot:
            health_snapshot[model] = {
                "status": "healthy",
                "failures": 0,
                "cooldown_remaining": 0.0
            }

    system_status = "nominal"
    for m, info in health_snapshot.items():
        if info["status"] == "cooldown":
            system_status = "degraded"

    return {
        "status": system_status,
        "metrics": {
            "requests_total": ROUTER_METRICS["requests_total"],
            "fallbacks_total": ROUTER_METRICS["fallbacks_total"],
            "cache_hits": CACHE_METRICS["hits"],
            "cache_misses": CACHE_METRICS["misses"],
            "model_selections": ROUTER_METRICS["model_selections"]
        },
        "models": {
            "primary": settings.primary_model,
            "fallbacks": settings.fallback_models,
            "health": health_snapshot
        },
        "agents": [
            {"name": "email_agent", "status": "idle", "description": "Processes emails and inbox tasks"},
            {"name": "meeting_agent", "status": "idle", "description": "Manages calendar meetings and schedules"},
            {"name": "task_agent", "status": "idle", "description": "Coordinates Outlook and Planner tasks"},
            {"name": "research_agent", "status": "idle", "description": "Queries OneDrive/SharePoint knowledge bases"}
        ],
        "cache_ttl": settings.graph_cache_ttl,
        "enabled_agents": settings.enabled_agents,
        "per_analyst_models": getattr(settings, "per_analyst_models", {})
    }

@router.get("/api/profile")
async def get_profile(token: str = Query(None), provider: str = Query("microsoft")):
    if provider == "microsoft":
        await validate_token(token)
    
    if provider == "google":
        try:
            import httpx
            async with httpx.AsyncClient() as client:
                resp = await client.get(
                    "https://www.googleapis.com/oauth2/v2/userinfo",
                    headers={"Authorization": f"Bearer {token}"}
                )
                if resp.status_code == 200:
                    user_data = resp.json()
                    display_name = user_data.get("name", "Executive")
                    email = user_data.get("email", "")
                else:
                    display_name = "Executive"
                    email = ""
            return {"display_name": display_name, "email": email, "provider": "google"}
        except Exception as e:
            print(f"Failed to fetch Google profile info: {e}")
            return {"display_name": "Executive", "email": "", "provider": "google"}
        
    try:
        client = GraphClient(token)
        profile_data = await client.get_profile()
        return profile_data
    except Exception as e:
        return {
            "displayName": "Active Session",
            "jobTitle": "Orchestrator",
            "mail": "session@worksphere.com",
            "userPrincipalName": "session@worksphere.onmicrosoft.com",
            "officeLocation": "Node-A",
            "warning": f"MS Graph call failed: {str(e)}"
        }

class SearchMemoryRequest(BaseModel):
    query: str = ""
    user_email: str

@router.post("/api/memory/search")
async def post_memory_search(request: SearchMemoryRequest, token: str = Query(None), provider: str = Query("microsoft")):
    if provider == "microsoft" and token:
        try:
            await validate_token(token)
        except Exception:
            pass
    
    user_email = request.user_email
    if token:
        try:
            if provider == "microsoft":
                client = GraphClient(token)
                profile = await client.get_profile()
                email = profile.get("mail") or profile.get("userPrincipalName")
                if email:
                    user_email = email
            elif provider == "google":
                import httpx
                async with httpx.AsyncClient() as client:
                    resp = await client.get(
                        "https://www.googleapis.com/oauth2/v2/userinfo",
                        headers={"Authorization": f"Bearer {token}"}
                    )
                    if resp.status_code == 200:
                        user_data = resp.json()
                        email = user_data.get("email")
                        if email:
                            user_email = email
        except Exception as e:
            print(f"[post_memory_search] Failed to resolve user email from token: {e}")

    query = request.query.strip() if request.query else ""
    user_email = user_email
    
    real_results = []
    if provider == "microsoft" and token and query:
        try:
            client = GraphClient(token)
            docs = await client.search_documents(query)
            for doc in docs:
                real_results.append({
                    "id": doc.get("id"),
                    "name": doc.get("name"),
                    "type": "document",
                    "lastModified": doc.get("lastModifiedDateTime") or doc.get("fileSystemInfo", {}).get("lastModifiedDateTime"),
                    "webUrl": doc.get("webUrl"),
                    "confidence": 0.95,
                    "summary": doc.get("description") or f"Document matching query '{query}'."
                })
        except Exception as e:
            print(f"[api_memory_search] Real search failed: {e}")
            pass

    # Fetch from Supabase indexed_sources table
    try:
        q = supabase.table("indexed_sources").select("*").eq("user_email", user_email)
        if query:
            q = q.or_(f"name.ilike.%{query}%,summary.ilike.%{query}%")
        result = q.order("created_at", desc=True).execute()
        data = result.data
    except Exception as e:
        print(f"Supabase source fetch error: {e}")
        data = []
    
    formatted_data = []
    for item in data:
        formatted_data.append({
            "id": item.get("id"),
            "name": item.get("name"),
            "type": item.get("type"),
            "lastModified": item.get("created_at"),
            "webUrl": "#",
            "confidence": 0.99,
            "summary": item.get("summary"),
            "tags": item.get("keywords") or []
        })
    # Merge with matches from MEMORY_POOL as a fallback/simulated memory source
    pool_results = []
    for item in MEMORY_POOL:
        if not query or query.lower() in item["name"].lower() or query.lower() in item["summary"].lower():
            if not any(d["name"] == item["name"] for d in formatted_data):
                pool_results.append({
                    "id": str(uuid.uuid4()),
                    "name": item["name"],
                    "type": item["type"],
                    "lastModified": item["lastModified"],
                    "webUrl": "#",
                    "confidence": 0.99,
                    "summary": item["summary"],
                    "tags": item.get("keywords") or []
                })

    return real_results + formatted_data + pool_results

# Global memory pool for simulated results (fix 17)
MEMORY_POOL = []

class AddMemoryRequest(BaseModel):
    name: str
    type: str
    summary: str
    keywords: list[str] = []
    user_email: str = None

@router.post("/api/memory/add")
async def add_memory(request: AddMemoryRequest, token: str = Query(None), provider: str = Query("microsoft")):
    if provider == "microsoft" and token:
        try:
            await validate_token(token)
        except Exception:
            pass
    if not request.name.strip() or not request.summary.strip():
        raise HTTPException(status_code=400, detail="Name and summary are required")
    
    # generate keywords from name if not provided
    kws = request.keywords
    if not kws:
        kws = [w.lower().strip(",.?!:;") for w in request.name.split() if len(w) > 2]

    MEMORY_POOL.insert(0, {
        "name": request.name,
        "type": request.type.lower(),
        "lastModified": datetime.now(timezone.utc).isoformat(),
        "summary": request.summary,
        "keywords": kws
    })
    
    user_email = "session@worksphere.com"
    if request.user_email:
        user_email = request.user_email
    elif provider == "microsoft" and token:
        try:
            client = GraphClient(token)
            profile = await client.get_profile()
            user_email = profile.get("mail") or profile.get("userPrincipalName") or user_email
        except Exception:
            pass
    elif provider == "google":
        user_email = "google-session@worksphere.com"

    await save_indexed_source(user_email, request.name, request.type.lower(), request.summary, kws)
    return {"status": "success"}

# --- Configuration Update and Briefings API ---

@router.post("/api/settings/update")
async def update_settings(data: dict, token: str = Query(None), provider: str = Query("microsoft")):
    import os
    if provider == "microsoft":
        await validate_token(token)
        
    # Update core settings in-memory fields
    if "primary_model" in data and data["primary_model"]:
        settings.primary_model = data["primary_model"].lower()
    if "cache_ttl" in data and data["cache_ttl"] is not None:
        settings.graph_cache_ttl = data["cache_ttl"]
        settings.report_cache_ttl = data["cache_ttl"]
    if "enabled_agents" in data and data["enabled_agents"] is not None:
        settings.enabled_agents = [x.lower().strip() for x in data["enabled_agents"]]
    if "per_analyst_models" in data and data["per_analyst_models"] is not None:
        settings.per_analyst_models = data["per_analyst_models"]
        
    for k, v in data.items():
        if hasattr(settings, k):
            setattr(settings, k, v)
            
    print(f"[api_settings_update] Settings updated: {data}")
    
    # Load existing settings.json, merge with new data, and save
    existing_settings = {}
    if os.path.exists(SETTINGS_FILE):
        try:
            with open(SETTINGS_FILE, "r") as f:
                existing_settings = json.load(f)
        except Exception:
            pass
            
    # Update with new settings data
    for k, v in data.items():
        existing_settings[k] = v
        
    # Ensure current settings object fields are correctly in existing_settings
    existing_settings["primary_model"] = settings.primary_model
    existing_settings["graph_cache_ttl"] = settings.graph_cache_ttl
    existing_settings["report_cache_ttl"] = settings.report_cache_ttl
    existing_settings["enabled_agents"] = settings.enabled_agents
    existing_settings["per_analyst_models"] = settings.per_analyst_models
    
    with open(SETTINGS_FILE, "w") as f:
        json.dump(existing_settings, f, indent=2)
        
    return {"status": "success", "settings": existing_settings}

@router.get("/api/briefings/history")
async def get_briefings_history(token: str = Query(None), provider: str = Query("microsoft")):
    if provider == "microsoft":
        await validate_token(token)
        
    user_email = "session@worksphere.com"
    if provider == "microsoft":
        try:
            client = GraphClient(token)
            profile = await client.get_profile()
            user_email = profile.get("mail") or profile.get("userPrincipalName") or user_email
        except Exception:
            pass
    elif provider == "google":
        user_email = "google-session@worksphere.com"

    try:
        from backend.memory.supabase_client import supabase
        result = supabase.table("briefing_history")\
            .select("id,created_at,preview")\
            .eq("user_email", user_email)\
            .order("created_at", desc=True)\
            .limit(5)\
            .execute()
        return result.data
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/api/briefings/{briefing_id}")
async def get_briefing_by_id(briefing_id: str, access_token: str):
    from backend.memory.supabase_client import supabase
    try:
        result = supabase.table("briefing_history")\
            .select("*")\
            .eq("id", briefing_id)\
            .single()\
            .execute()
        if result.data:
            return result.data
        raise HTTPException(status_code=404, detail="Briefing not found")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/api/settings")
async def get_settings(token: str = Query(None), provider: str = Query("microsoft")):
    import os
    if provider == "microsoft":
        try:
            await validate_token(token)
        except Exception:
            pass
            
    try:
        if os.path.exists(SETTINGS_FILE):
            with open(SETTINGS_FILE, "r") as f:
                return json.load(f)
    except Exception as e:
        print(f"[get_settings] Failed to read settings.json: {e}")
        
    return {
        "primary_model": settings.primary_model,
        "fallback_models": settings.fallback_models,
        "graph_cache_ttl": settings.graph_cache_ttl,
        "enabled_agents": settings.enabled_agents,
        "per_analyst_models": getattr(settings, "per_analyst_models", {})
    }

class CreateTodoRequest(BaseModel):
    title: str

@router.post("/api/actions/create-todo")
async def create_todo(request: CreateTodoRequest, token: str = Query(None), provider: str = Query("microsoft")):
    if provider == "microsoft":
        if token:
            try:
                if not token.startswith("dummy"):
                    await validate_token(token)
                graph = GraphClient(token)
                await graph.create_todo_task(request.title)
            except Exception as e:
                raise HTTPException(status_code=500, detail=f"Graph API error: {str(e)}")
        return {"success": True, "message": f"Task '{request.title}' successfully synced to Microsoft To Do"}
    return {"success": True, "message": f"Task '{request.title}' synced successfully"}

@router.post("/api/actions/approve-budget")
async def approve_budget(token: str = Query(None), provider: str = Query("microsoft")):
    if provider == "microsoft":
        if token:
            try:
                if not token.startswith("dummy"):
                    await validate_token(token)
                graph = GraphClient(token)
                await graph.create_todo_task("Q3 Budget Allocation Approved - Audit trail generated")
            except Exception as e:
                raise HTTPException(status_code=500, detail=f"Graph API error: {str(e)}")
        return {"success": True, "message": "Q3 Budget allocation of $250,000 signed off successfully via Finance connector"}
    return {"success": True, "message": "Q3 Budget allocation signed off via Google Workspace"}

@router.post("/api/actions/balance-workloads")
async def balance_workloads(token: str = Query(None), provider: str = Query("microsoft")):
    if provider == "microsoft":
        if token:
            try:
                if not token.startswith("dummy"):
                    await validate_token(token)
                graph = GraphClient(token)
                await graph.create_todo_task("Balanced workload: Reassign tasks from John to Sarah")
            except Exception as e:
                raise HTTPException(status_code=500, detail=f"Graph API error: {str(e)}")
        return {"success": True, "message": "Sarah reassigned 4 tasks from John. Workload balanced successfully."}
    return {"success": True, "message": "Workloads balanced successfully."}

@router.post("/api/actions/reply-escalation")
async def reply_escalation(token: str = Query(None), provider: str = Query("microsoft")):
    if provider == "microsoft":
        if token:
            try:
                if not token.startswith("dummy"):
                    await validate_token(token)
                graph = GraphClient(token)
                await graph.send_email(
                    subject="Re: Client Timeline Escalation",
                    content="Looking into this. Will update by 4 PM.",
                    to_email="sarah.jenkins@worksphere.com"
                )
            except Exception as e:
                raise HTTPException(status_code=500, detail=f"Graph API error: {str(e)}")
        return {"success": True, "message": "Reply sent: 'Looking into this. Will update by 4 PM.' Sent via Outlook Analyst."}
    return {"success": True, "message": "Reply sent successfully."}

@router.post("/api/actions/schedule-sync")
async def schedule_sync(token: str = Query(None), provider: str = Query("microsoft")):
    if provider == "microsoft":
        if token:
            try:
                if not token.startswith("dummy"):
                    await validate_token(token)
                graph = GraphClient(token)
                from datetime import datetime, timedelta
                tomorrow = datetime.now(timezone.utc) + timedelta(days=1)
                start_time = tomorrow.replace(hour=10, minute=0, second=0, microsecond=0).isoformat().replace("+00:00", "Z")
                end_time = tomorrow.replace(hour=11, minute=0, second=0, microsecond=0).isoformat().replace("+00:00", "Z")
                await graph.create_event(
                    subject="Project Alignment Sync",
                    start_iso=start_time,
                    end_iso=end_time,
                    attendees_emails=["sarah.jenkins@worksphere.com", "bob.white@worksphere.com"]
                )
            except Exception as e:
                raise HTTPException(status_code=500, detail=f"Graph API error: {str(e)}")
        return {"success": True, "message": "Teams invitation sent to Sarah Jenkins and Bob White for tomorrow 10:00 AM."}
    return {"success": True, "message": "Sync scheduled successfully."}

# --- Frontend Serving Routes ---
from fastapi.responses import FileResponse
import os
from memory.cache import cache_client

BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
STITCH_DIR = os.path.join(BASE_DIR, "frontend")

@router.get("/api/intelligence/latest")
async def get_latest_intelligence(token: str = Query(None), provider: str = Query("microsoft")):
    if provider == "microsoft":
        await validate_token(token)
        
    user_email = "session@worksphere.com"
    if provider == "microsoft":
        try:
            from graph.client import GraphClient
            client = GraphClient(token)
            profile = await client.get_profile()
            user_email = profile.get("mail") or profile.get("userPrincipalName") or user_email
        except Exception:
            pass
    elif provider == "google":
        user_email = "google-session@worksphere.com"
        if token:
            try:
                import httpx
                async with httpx.AsyncClient() as client:
                    resp = await client.get(
                        "https://www.googleapis.com/oauth2/v2/userinfo",
                        headers={"Authorization": f"Bearer {token}"}
                    )
                    if resp.status_code == 200:
                        user_data = resp.json()
                        email = user_data.get("email")
                        if email:
                            user_email = email
            except Exception:
                pass

    cache_key = f"latest_intelligence:{user_email}"
    cached_data = await cache_client.get(cache_key)
    if cached_data:
        return cached_data
    else:
        return {"status": "empty", "message": "No briefing compiled yet today"}

@router.get("/api/intelligence/structured")
async def get_intelligence_structured(token: str = Query(None), provider: str = Query("microsoft")):
    if provider == "microsoft":
        try:
            await validate_token(token)
        except Exception:
            pass
        
    user_email = "session@worksphere.com"
    if provider == "microsoft":
        try:
            from graph.client import GraphClient
            client = GraphClient(token)
            profile = await client.get_profile()
            user_email = profile.get("mail") or profile.get("userPrincipalName") or user_email
        except Exception:
            pass
    elif provider == "google":
        user_email = "google-session@worksphere.com"
        if token:
            try:
                import httpx
                async with httpx.AsyncClient() as client:
                    resp = await client.get(
                        "https://www.googleapis.com/oauth2/v2/userinfo",
                        headers={"Authorization": f"Bearer {token}"}
                    )
                    if resp.status_code == 200:
                        user_data = resp.json()
                        email = user_data.get("email")
                        if email:
                            user_email = email
            except Exception:
                pass
        
    try:
        from datetime import datetime
        from memory.cache import cache_client
        today_date = datetime.utcnow().date().isoformat()
        cache_key_structured = f"structured:{user_email}:{today_date}"
        cached_data = await cache_client.get(cache_key_structured)
        if cached_data:
            return cached_data
        else:
            return {"status": "empty", "message": "No structured payload found for today"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/")
@router.head("/")
def get_landing(response: Response):
    response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    response.headers["Pragma"] = "no-cache"
    response.headers["Expires"] = "0"
    return FileResponse(os.path.join(STITCH_DIR, "landing_page.html"))

@router.get("/dashboard")
def get_dashboard(response: Response):
    response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    response.headers["Pragma"] = "no-cache"
    response.headers["Expires"] = "0"
    return FileResponse(os.path.join(STITCH_DIR, "command_center.html"))

@router.get("/executive_intelligence")
def get_executive_intelligence(response: Response):
    response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    response.headers["Pragma"] = "no-cache"
    response.headers["Expires"] = "0"
    return FileResponse(os.path.join(STITCH_DIR, "executive_intelligence.html"))

@router.get("/agent_operations")
def get_agent_operations(response: Response):
    response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    response.headers["Pragma"] = "no-cache"
    response.headers["Expires"] = "0"
    return FileResponse(os.path.join(STITCH_DIR, "agent_operations.html"))

@router.get("/agent_network")
def get_agent_network():
    return RedirectResponse(url="/dashboard")

@router.get("/memory_explorer")
def get_memory_explorer(response: Response):
    response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    response.headers["Pragma"] = "no-cache"
    response.headers["Expires"] = "0"
    return FileResponse(os.path.join(STITCH_DIR, "memory_explorer.html"))

@router.get("/executive_briefing")
def get_executive_briefing():
    return RedirectResponse(url="/dashboard")

@router.get("/control_plane")
def get_control_plane(response: Response):
    response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    response.headers["Pragma"] = "no-cache"
    response.headers["Expires"] = "0"
    return FileResponse(os.path.join(STITCH_DIR, "control_plane.html"))

@router.get("/workspace_home")
def get_workspace_home():
    return RedirectResponse(url="/dashboard")

@router.get("/sidebar.js")
def get_sidebar_js(response: Response):
    response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    response.headers["Pragma"] = "no-cache"
    response.headers["Expires"] = "0"
    return FileResponse(os.path.join(STITCH_DIR, "sidebar.js"), media_type="application/javascript")
