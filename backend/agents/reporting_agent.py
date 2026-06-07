import os
import json
import hashlib
from typing import AsyncGenerator
from ai.model_router import model_router
from memory.cache import cache_client
from ai.runtime_settings import settings

class ReportingAgent:
    def _get_prompt(self, context: dict) -> str:
        return f"""
You are a Chief of Staff synthesizing business intelligence for an executive. Based on this workspace data:
{json.dumps(context, indent=1)}

Write a professional Executive Briefing with exactly these 10 sections:
1. Executive Summary
2. Urgent Issues
3. Upcoming Meetings
4. High Priority Tasks
5. Stakeholder Risks
6. Pending Approvals
7. Key Decisions
8. Recommended Actions
9. Deadlines This Week
10. Suggested Agenda For Next Meeting

CRITICAL WRITING RULES:
- STRICTLY avoid all technical jargon and developer terminology. Never refer to "database keys", "API calls", "JSON schemas", "LLMs", "tokens", "caches", "Redis", "Supabase", or "RAG systems". Use clean, executive-ready business language.
- Under "Executive Summary", write a brief, high-level summary of the overall business situation.
- Under "Urgent Issues", identify critical problems requiring response within 24 hours.
- Under "Upcoming Meetings", outline the key calendar appointments and discussions.
- Under "High Priority Tasks", list important deliverables.
- Under "Stakeholder Risks", highlight stakeholder concerns and delivery blockers.
- Under "Pending Approvals", list sign-offs, budgets, or contracts awaiting review.
- Under "Key Decisions", detail agreements reached.
- Under "Recommended Actions", outline suggested next steps.
- Under "Deadlines This Week", compile upcoming milestone dates.
- Under "Suggested Agenda For Next Meeting", recommend topics for alignment syncs.
- For lists or status tracking, format items in clear tables or bullet points to ensure the document is highly scannable.
- If no information is found for a section, write: "No active items identified."
- Keep your writing professional, concise, and actionable.
"""

    async def run(self, access_token: str, user_query: str, context: dict = None) -> dict:
        """
        Synthesizes agent outputs into a unified text briefing. Supports caching.
        """
        try:
            if context is None:
                context = {}

            email_results = context.get("email_results")
            meeting_results = context.get("meeting_results")
            task_results = context.get("task_results")
            research_results = context.get("research_results")

            all_empty = all(
                not v or (isinstance(v, dict) and all(
                    not val for val in v.values()
                ))
                for v in [email_results, meeting_results, task_results, research_results]
            )

            fallback_structured = {
                "urgent_emails": [],
                "upcoming_meetings": [],
                "overdue_tasks": [],
                "pending_approvals": [],
                "decisions": [],
                "risks": [],
                "stakeholder_sentiment": [],
                "telemetry": {
                    "time_saved_minutes": 0,
                    "emails_reviewed": 0,
                    "meetings_analysed": 0,
                    "tasks_reviewed": 0,
                    "docs_indexed": 0
                }
            }

            if all_empty:
                return {
                    "report": "# No data available\n\nNo emails, meetings, tasks, or documents were found in your connected accounts. Please ensure your Microsoft 365 account has data and try again.",
                    "structured": fallback_structured
                }

            # Caching check
            raw_json = json.dumps(context, sort_keys=True)
            data_hash = hashlib.md5(raw_json.encode('utf-8')).hexdigest()
            cache_key = f"reporting_agent:{data_hash}"
            
            cached = await cache_client.get(cache_key)
            if cached and "briefing" in cached:
                return {
                    "briefing": cached["briefing"],
                    "structured": cached.get("structured", fallback_structured)
                }

            prompt = self._get_prompt(context)
            report = await model_router.generate_response(prompt)

            # Make the second separate LLM call for structured JSON extraction
            context_str = json.dumps(context, indent=1)
            sys_prompt = 'Return ONLY valid JSON. No markdown fences. No explanation. Extract from the agent data and return this schema: {"urgent_emails":[],"upcoming_meetings":[],"overdue_tasks":[],"pending_approvals":[],"decisions":[],"risks":[],"stakeholder_sentiment":[],"telemetry":{"time_saved_minutes":0,"emails_reviewed":0,"meetings_analysed":0,"tasks_reviewed":0,"docs_indexed":0}}. Never invent placeholder names or example data. If a list has no real items, return an empty array.'
            
            structured_raw = await model_router.generate_response(
                prompt=context_str,
                system_prompt=sys_prompt,
                response_format="json",
                max_tokens=2000
            )

            try:
                cleaned = structured_raw.strip()
                if cleaned.startswith("```"):
                    lines = cleaned.splitlines()
                    if lines[0].startswith("```"):
                        lines = lines[1:]
                    if lines[-1].strip() == "```":
                        lines = lines[:-1]
                    cleaned = "\n".join(lines).strip()
                structured_data = json.loads(cleaned)
            except Exception as ex:
                print(f"[ReportingAgent] Error parsing structured JSON: {ex}")
                structured_data = fallback_structured
            
            # Cache the report and structured data
            await cache_client.set(cache_key, {"briefing": report, "structured": structured_data}, ttl=settings.report_cache_ttl)
            return {
                "briefing": report,
                "structured": structured_data
            }
            
        except Exception as e:
            return {
                "briefing": f"Error generating briefing: {str(e)}",
                "structured": {
                    "urgent_emails": [],
                    "upcoming_meetings": [],
                    "overdue_tasks": [],
                    "pending_approvals": [],
                    "decisions": [],
                    "risks": [],
                    "stakeholder_sentiment": [],
                    "telemetry": {
                        "time_saved_minutes": 0,
                        "emails_reviewed": 0,
                        "meetings_analysed": 0,
                        "tasks_reviewed": 0,
                        "docs_indexed": 0
                    }
                }
            }

    async def run_stream(self, access_token: str, user_query: str, context: dict = None) -> AsyncGenerator[str, None]:
        """
        Asynchronously streams the briefing tokens while saving the compiled report to the cache.
        """
        if context is None:
            context = {}

        email_results = context.get("email_results")
        meeting_results = context.get("meeting_results")
        task_results = context.get("task_results")
        research_results = context.get("research_results")

        all_empty = all(
            not v or (isinstance(v, dict) and all(
                not val for val in v.values()
            ))
            for v in [email_results, meeting_results, task_results, research_results]
        )

        fallback_structured = {
            "urgent_emails": [],
            "upcoming_meetings": [],
            "overdue_tasks": [],
            "pending_approvals": [],
            "decisions": [],
            "risks": [],
            "stakeholder_sentiment": [],
            "telemetry": {
                "time_saved_minutes": 0,
                "emails_reviewed": 0,
                "meetings_analysed": 0,
                "tasks_reviewed": 0,
                "docs_indexed": 0
            }
        }

        if all_empty:
            yield json.dumps({
                "event": "final_briefing",
                "briefing": "# No data available\n\nNo emails, meetings, tasks, or documents were found in your connected accounts. Please ensure your Microsoft 365 account has data and try again.",
                "structured": fallback_structured
            })
            return

        # Caching check
        raw_json = json.dumps(context, sort_keys=True)
        data_hash = hashlib.md5(raw_json.encode('utf-8')).hexdigest()
        cache_key = f"reporting_agent:{data_hash}"
        
        cached = await cache_client.get(cache_key)
        if cached and "briefing" in cached:
            # Yield full report if cache hits
            yield json.dumps({
                "event": "final_briefing",
                "briefing": cached["briefing"],
                "structured": cached.get("structured", fallback_structured)
            })
            return

        prompt = self._get_prompt(context)
        
        full_report_chunks = []
        try:
            async for chunk in model_router.generate_stream(prompt):
                full_report_chunks.append(chunk)
                yield chunk
            
            full_report = "".join(full_report_chunks)

            # Make the second separate LLM call for structured JSON extraction
            context_str = json.dumps(context, indent=1)
            sys_prompt = 'Return ONLY valid JSON. No markdown fences. No explanation. Extract from the agent data and return this schema: {"urgent_emails":[],"upcoming_meetings":[],"overdue_tasks":[],"pending_approvals":[],"decisions":[],"risks":[],"stakeholder_sentiment":[],"telemetry":{"time_saved_minutes":0,"emails_reviewed":0,"meetings_analysed":0,"tasks_reviewed":0,"docs_indexed":0}}. Never invent placeholder names or example data. If a list has no real items, return an empty array.'
            
            structured_raw = await model_router.generate_response(
                prompt=context_str,
                system_prompt=sys_prompt,
                response_format="json",
                max_tokens=2000
            )

            try:
                cleaned = structured_raw.strip()
                if cleaned.startswith("```"):
                    lines = cleaned.splitlines()
                    if lines[0].startswith("```"):
                        lines = lines[1:]
                    if lines[-1].strip() == "```":
                        lines = lines[:-1]
                    cleaned = "\n".join(lines).strip()
                structured_data = json.loads(cleaned)
            except Exception as ex:
                print(f"[ReportingAgent] Error parsing structured JSON: {ex}")
                structured_data = fallback_structured

            # Store assembled report in cache
            await cache_client.set(cache_key, {"briefing": full_report, "structured": structured_data}, ttl=settings.report_cache_ttl)
            
            yield json.dumps({
                "event": "final_briefing",
                "briefing": full_report,
                "structured": structured_data
            })
            
        except Exception as e:
            yield f"\n[Error streaming briefing: {str(e)}]"
