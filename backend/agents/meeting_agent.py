import os
import json
import hashlib
from graph.client import GraphClient
from ai.model_router import model_router
from memory.cache import cache_client
from ai.runtime_settings import settings

class MeetingAgent:
    async def run(self, access_token: str, user_query: str, provider: str = "microsoft") -> dict:
        """
        Fetches calendar events (Outlook or Google Calendar) and active chats (Teams), pre-truncates metadata,
        hashes the combined input for MD5 caching, and extracts meeting summaries, key decisions,
        and follow-up actions via the Model Router.
        """
        try:
            # 1. Fetch raw events and map them
            processed_meetings = []
            processed_chats = []
            
            if provider == "google":
                # Google Calendar API
                import httpx
                from datetime import datetime
                async with httpx.AsyncClient() as client:
                    resp = await client.get(
                        "https://www.googleapis.com/calendar/v3/calendars/primary/events",
                        params={
                            "maxResults": 10,
                            "orderBy": "startTime",
                            "singleEvents": True,
                            "timeMin": datetime.utcnow().isoformat() + "Z"
                        },
                        headers={"Authorization": f"Bearer {access_token}"}
                    )
                    events = resp.json().get("items", []) if resp.status_code == 200 else []
                    # Format events to match Microsoft structure
                    meetings_data = [
                        {"subject": e.get("summary", "No title"),
                         "start": e.get("start", {}).get("dateTime", ""),
                         "attendees": [a.get("email") for a in e.get("attendees", [])]}
                        for e in events
                    ]
            else:
                # Existing Microsoft GraphClient call — keep as is
                graph = GraphClient(access_token)
                meetings_data = await graph.get_calendar_events()

            # Format/map meetings_data to match existing structure
            for meeting in meetings_data:
                processed_meetings.append({
                    "subject": meeting.get("subject", "No title")[:100],
                    "start": meeting.get("start", {}).get("dateTime", meeting.get("start", "")) if isinstance(meeting.get("start"), dict) else meeting.get("start", ""),
                    "end": meeting.get("end", {}).get("dateTime", "") if isinstance(meeting.get("end"), dict) else "",
                    "attendees": [
                        (att.get("emailAddress", {}).get("name", "") if isinstance(att, dict) else str(att))[:50]
                        for att in meeting.get("attendees", [])
                    ][:10],
                    "source": "Google Calendar" if provider == "google" else "Outlook Calendar"
                })

            # Attempt to fetch Teams chats (may fail for personal accounts without Teams license)
            if provider != "google":
                try:
                    teams_chats = await graph.get_teams_chats()
                    for chat in teams_chats:
                        chat_msgs = []
                        for msg in chat.get("messages", [])[:5]:
                            body_content = msg.get("body", {}).get("content", "")
                            sender = msg.get("from", {}).get("user", {}).get("displayName", "System")
                            chat_msgs.append({
                                "sender": sender,
                                "content": body_content[:200],
                                "created": msg.get("createdDateTime", "")
                            })
                        processed_chats.append({
                            "topic": chat.get("topic")[:100] if chat.get("topic") else "Direct Chat",
                            "chat_type": chat.get("chatType", ""),
                            "web_url": chat.get("webUrl", ""),
                            "id": chat.get("id", ""),
                            "messages": chat_msgs,
                            "source": "Microsoft Teams"
                        })
                except Exception as e:
                    print(f"Teams data unavailable (expected on personal accounts): {e}")

            # 2. Caching layer optimization
            combined_payload = {
                "meetings": processed_meetings,
                "chats": processed_chats
            }
            raw_json = json.dumps(combined_payload, sort_keys=True)
            data_hash = hashlib.md5(raw_json.encode('utf-8')).hexdigest()
            cache_key = f"meeting_agent:{data_hash}:{hashlib.md5(user_query.encode('utf-8')).hexdigest()}"
            
            cached_result = await cache_client.get(cache_key)
            if cached_result:
                return cached_result

            # 3. Prompt definition
            prompt = f"""
You are a Meeting Intelligence Analyst reviewing the user's meeting calendar and chat syncs.
Analyze these calendar meetings:
{json.dumps(processed_meetings, indent=1)}

Analyze these active Teams chats:
{json.dumps(processed_chats, indent=1)}

Extract the following business intelligence details:
1) Decisions: Agreed plans, finalized dates, design choices, or scope updates.
2) Risks: Blocker topics, unresolved technical dependencies, scheduling challenges, or stakeholder disagreements.

Context (what the user is asking about): {user_query}
"""
            schema = {
                "decisions": [{"decision": "decision text", "source": "meeting/chat topic name", "date": "date/time of decision"}],
                "risks": [{"risk": "risk description", "severity": "MEDIUM/HIGH/CRITICAL"}]
            }
            
            # Execute through router
            preferred_model = getattr(settings, "per_analyst_models", {}).get("meeting")
            result = await model_router.structured_extract(
                content=prompt,
                schema=schema,
                preferred_model=preferred_model
            )
            
            upcoming_meetings = []
            for m in processed_meetings:
                upcoming_meetings.append({
                    "title": m["subject"],
                    "time": m["start"],
                    "attendees": m["attendees"]
                })

            structured_res = {
                "upcoming_meetings": upcoming_meetings,
                "decisions": result.get("decisions", []),
                "risks": result.get("risks", [])
            }
            
            # Cache the result
            await cache_client.set(cache_key, structured_res, ttl=settings.graph_cache_ttl)
            return structured_res

        except Exception as e:
            return {
                "upcoming_meetings": [],
                "decisions": [],
                "risks": [],
                "error": str(e)
            }
