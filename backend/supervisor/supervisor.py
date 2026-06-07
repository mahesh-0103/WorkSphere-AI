import json
import asyncio
import time
from memory.context import SharedContext
from agents.email_agent import EmailAgent
from agents.meeting_agent import MeetingAgent
from agents.task_agent import TaskAgent
from agents.research_agent import ResearchAgent
from agents.reporting_agent import ReportingAgent
from ai.model_router import model_router, ROUTER_METRICS
from memory.cache import CACHE_METRICS, cache_client
from ai.runtime_settings import settings

async def run_supervisor(user_query: str, access_token: str, provider: str = "microsoft", limited_scopes: bool = False):
    """
    Executes WorkSphere's agent planning, triggers concurrent agent execution, 
    streams progress & reporting tokens, and gathers telemetry/observability metrics.
    """
    start_total_time = time.time()
    context = SharedContext(user_query=user_query)

    ALL_AGENTS = {
        "email_agent": EmailAgent,
        "meeting_agent": MeetingAgent,
        "task_agent": TaskAgent,
        "research_agent": ResearchAgent
    }
    
    # Filter based on settings.enabled_agents
    active_agents = {k: v for k, v in ALL_AGENTS.items() if k in settings.enabled_agents}
    if not active_agents:
        active_agents = ALL_AGENTS

    # Default fallback: select all agents if planning fails
    selected_agents = list(active_agents.keys())

    # Google limited scopes check
    is_limited = limited_scopes
    if provider == "google":
        try:
            cache_limited = await cache_client.get(f"limited_scopes:{access_token}")
            if cache_limited:
                is_limited = True
        except Exception as se:
            print(f"[SUPERVISOR WARNING] Error checking limited_scopes cache: {se}")

    if provider == "google" and is_limited:
        print("[SUPERVISOR] Limited scopes active. Skipping task_agent and research_agent.")
        active_agents = {k: v for k, v in active_agents.items() if k not in ["task_agent", "research_agent"]}
        selected_agents = [a for a in selected_agents if a not in ["task_agent", "research_agent"]]

    # Step 1: Intent Classification & Planning
    yield json.dumps({"event": "planning", "status": "running"})
    start_planning = time.time()
    
    prompt = f"""
You are the planner for a WorkSphere AI workplace assistant.
Analyze the user's query: "{user_query}"
Decide which of the following agents are required to fulfill the request:

Available Agents:
- "email_agent": Required if asking about emails, inbox, messages, or mail.
- "meeting_agent": Required if asking about meetings, calendars, syncs, or appointments.
- "task_agent": Required if asking about tasks, To-Do items, Planner, or checklists.
- "research_agent": Required if asking about documents, files, OneDrive, or SharePoint.

Respond ONLY with a JSON object containing keys:
- "agents": (list of strings chosen from ["email_agent", "meeting_agent", "task_agent", "research_agent"])
"""
    try:
        plan_res = await model_router.structured_extract(
            content=prompt,
            schema={"agents": ["list of agent names"]}
        )
        valid_agents = [a for a in plan_res.get("agents", []) if a in active_agents]
        if valid_agents:
            selected_agents = valid_agents
    except Exception as e:
        # Silently fall back to all agents on planning failure
        pass
        
    planning_duration_ms = int((time.time() - start_planning) * 1000)
    yield json.dumps({"event": "execution_plan", "agents": selected_agents, "duration_ms": planning_duration_ms})

    # Step 2: Parallel Agent Collection
    email_agent = EmailAgent()
    meeting_agent = MeetingAgent()
    task_agent = TaskAgent()
    research_agent = ResearchAgent()

    # Pre-fetch batched data if any dashboard agents are running to cut network roundtrips to 1
    dashboard_agents = {"email_agent", "meeting_agent", "task_agent"}
    if any(agent in dashboard_agents for agent in selected_agents) and provider == "microsoft":
        try:
            from graph.client import GraphClient
            client = GraphClient(access_token)
            await client.get_batched_dashboard_data()
        except Exception:
            pass

    start_parallel = time.time()

    # Determine which agents are skipped/disabled
    skipped_agents = []
    for k in ALL_AGENTS.keys():
        if k not in selected_agents:
            skipped_agents.append(k)

    # Yield running events for the UI
    for k in ALL_AGENTS.keys():
        if k not in skipped_agents:
            yield json.dumps({"agent": k, "status": "running"})

    # Setup execution tasks
    email_run = email_agent.run(access_token, user_query, provider)
    meeting_run = meeting_agent.run(access_token, user_query, provider)
    
    if "task_agent" in skipped_agents:
        async def dummy_task_run():
            return {}
        task_run = dummy_task_run()
    else:
        task_run = task_agent.run(access_token, user_query, provider)
        
    if "research_agent" in skipped_agents:
        async def dummy_research_run():
            return {}
        research_run = dummy_research_run()
    else:
        research_run = research_agent.run(access_token, user_query, provider)

    try:
        results = await asyncio.gather(
            email_run,
            meeting_run,
            task_run,
            research_run,
            return_exceptions=True
        )
    except Exception as e:
        import traceback
        print(f"[SUPERVISOR CRITICAL ERROR] {e}")
        print(traceback.format_exc())
        yield json.dumps({"event": "error", "message": str(e)})
        return

    # Check for exceptions
    for i, result in enumerate(results):
        if isinstance(result, Exception):
            agent_names = ["email", "meeting", "task", "research"]
            print(f"[AGENT FAILED] {agent_names[i]}: {result}")
            # Do NOT fail the whole briefing — continue with empty result for this agent
            results[i] = {}

    email_results, meeting_results, task_results, research_results = results
    
    # Yield done/error events for the UI
    agent_names_full = ["email_agent", "meeting_agent", "task_agent", "research_agent"]
    agents_parallel_duration_ms = int((time.time() - start_parallel) * 1000)
    for i, result in enumerate(results):
        k = agent_names_full[i]
        if k not in skipped_agents:
            yield json.dumps({"agent": k, "status": "done", "duration_ms": agents_parallel_duration_ms})

    # Store in context layer
    context.email_results = email_results
    context.meeting_results = meeting_results
    context.task_results = task_results
    context.research_results = research_results

    # Step 3: Reporting Agent (Streaming Token Outputs)
    yield json.dumps({"agent": "reporting_agent", "status": "running"})
    start_reporting = time.time()
    
    reporting_agent = ReportingAgent()
    report_chunks = []
    
    try:
        async for chunk in reporting_agent.run_stream(access_token, user_query, context.to_dict()):
            try:
                parsed_chunk = json.loads(chunk)
                if isinstance(parsed_chunk, dict) and parsed_chunk.get("event") == "final_briefing":
                    briefing_val = parsed_chunk.get("briefing", "")
                    yield json.dumps({"event": "final_briefing_chunk", "data": briefing_val})
                    context.report = briefing_val
                    context.structured = parsed_chunk.get("structured", {})
                    continue
            except Exception:
                pass
            
            report_chunks.append(chunk)
            yield json.dumps({"event": "final_briefing_chunk", "data": chunk})
            
        reporting_duration_ms = int((time.time() - start_reporting) * 1000)
        yield json.dumps({"agent": "reporting_agent", "status": "done", "duration_ms": reporting_duration_ms})
        if not context.report:
            context.report = "".join(report_chunks)
        
    except Exception as e:
        yield json.dumps({"agent": "reporting_agent", "status": "error", "error": str(e)})
        context.report = f"Error generating briefing: {e}"
        reporting_duration_ms = int((time.time() - start_reporting) * 1000)

    # Step 4: Observability metrics & final report payload
    total_duration_ms = int((time.time() - start_total_time) * 1000)
    
    metrics = {
        "planning_duration_ms": planning_duration_ms,
        "agents_parallel_duration_ms": agents_parallel_duration_ms,
        "reporting_duration_ms": reporting_duration_ms,
        "total_duration_ms": total_duration_ms,
        "cache_hits": CACHE_METRICS["hits"],
        "cache_misses": CACHE_METRICS["misses"],
        "router_calls": ROUTER_METRICS["requests_total"],
        "router_fallbacks": ROUTER_METRICS["fallbacks_total"],
        "model_selections": ROUTER_METRICS["model_selections"]
    }
    
    # Retrieve user email for caching
    user_email = "session@worksphere.com"
    if provider == "microsoft":
        try:
            from graph.client import GraphClient
            client = GraphClient(access_token)
            profile = await client.get_profile()
            user_email = profile.get("mail") or profile.get("userPrincipalName") or user_email
        except Exception:
            pass
    elif provider == "google":
        user_email = "google-session@worksphere.com"

    # Cache latest payload
    latest_payload = {
        "timestamp": time.time(),
        "report": context.report,
        "structured": context.structured,
        "email_results": context.email_results,
        "meeting_results": context.meeting_results,
        "task_results": context.task_results,
        "research_results": context.research_results,
        "metrics": metrics
    }
    cache_key = f"latest_intelligence:{user_email}"
    await cache_client.set(cache_key, latest_payload, ttl=86400)

    # Cache structured payload separately
    try:
        from datetime import datetime
        today_date = datetime.utcnow().date().isoformat()
        cache_key_structured = f"structured:{user_email}:{today_date}"
        await cache_client.set(cache_key_structured, context.structured, ttl=86400)
    except Exception as ce:
        print(f"[SUPERVISOR] Failed to cache structured payload separately: {ce}")

    yield json.dumps({
        "event": "agent_results",
        "email_results": context.email_results,
        "meeting_results": context.meeting_results,
        "task_results": context.task_results,
        "research_results": context.research_results
    })
    yield json.dumps({"event": "observability_metrics", "metrics": metrics})
    yield json.dumps({"event": "final_briefing", "data": context.report, "structured": context.structured})
    yield json.dumps({"type": "structured", "payload": context.structured})
