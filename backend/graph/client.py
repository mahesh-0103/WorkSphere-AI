import httpx
import hashlib
import json
from typing import Optional
from memory.cache import cache_client
from ai.runtime_settings import settings
from graph.batch_executor import BatchGraphExecutor

class GraphClient:
    def __init__(self, access_token: str):
        self.access_token = access_token
        self.headers = {
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json"
        }
        self.base_url = "https://graph.microsoft.com/v1.0"
        # Unique safe hash for token cache namespaces
        self.token_hash = hashlib.md5(access_token.encode('utf-8')).hexdigest()

    def _get_mock_data(self) -> dict:
        """
        Generates comprehensive mock Microsoft Graph data for dry-runs and demo sessions.
        """
        return {
            "profile": {
                "displayName": "Active Session",
                "jobTitle": "Orchestrator",
                "mail": "session@worksphere.com",
                "userPrincipalName": "session@worksphere.onmicrosoft.com",
                "officeLocation": "Node-A"
            },
            "emails": [
                {
                    "subject": "Urgent: Update client credentials on Planner integration",
                    "bodyPreview": "Hey Marcus, Sarah here. We are completely blocked on synchronizing the Q4 Roadmap with the Teams scheduler. The client secret needs to be regenerated in the Azure portal and updated in settings. Let's fix this during standup.",
                    "from": {
                        "emailAddress": {
                            "name": "Sarah Jenkins",
                            "address": "sarah.jenkins@worksphere.com"
                        }
                    },
                    "receivedDateTime": "2026-06-05T08:22:00Z"
                },
                {
                    "subject": "Alert: Node-04 degradation timeline",
                    "bodyPreview": "This is an automated alert from System Sentinel. Node-04 is showing signs of memory exhaustion. Redis cache hits have dropped by 18%. SRE is initiating hot failover to backup cluster Node-05.",
                    "from": {
                        "emailAddress": {
                            "name": "System Sentinel",
                            "address": "sentinel@worksphere.com"
                        }
                    },
                    "receivedDateTime": "2026-06-05T07:45:00Z"
                },
                {
                    "subject": "Q3 Budget & Token Spending Forecasts",
                    "bodyPreview": "Hi Marcus, I reviewed the token usage metrics for the Fallback Model Router. Under heavy failover load, costs on Llama 3.3 and Qwen models have ticked up slightly, but caching rules successfully saved 35% of token expenses.",
                    "from": {
                        "emailAddress": {
                            "name": "Emily Vance",
                            "address": "emily.vance@worksphere.com"
                        }
                    },
                    "receivedDateTime": "2026-06-04T16:15:00Z"
                },
                {
                    "subject": "Security audit checklist for compliance",
                    "bodyPreview": "Dear WorkSphere team, the external ingress penetration testing is scheduled for tomorrow. Please ensure all inactive system components and old debug routes are disabled. Check our design checklist document.",
                    "from": {
                        "emailAddress": {
                            "name": "Compliance Core",
                            "address": "compliance@worksphere.com"
                        }
                    },
                    "receivedDateTime": "2026-06-04T12:00:00Z"
                },
                {
                    "subject": "Re: Design System Glassmorphism guidelines",
                    "bodyPreview": "The sidebar glassmorphism assets and active badge overlays are merged. They look premium! Ensure that they dynamically render session states from token caches rather than static templates.",
                    "from": {
                        "emailAddress": {
                            "name": "Bob White",
                            "address": "bob.white@worksphere.com"
                        }
                    },
                    "receivedDateTime": "2026-06-03T15:30:00Z"
                }
            ],
            "meetings": [
                {
                    "subject": "Project Phoenix Scope Alignment",
                    "start": {
                        "dateTime": "2026-06-05T10:00:00Z",
                        "timeZone": "UTC"
                    },
                    "end": {
                        "dateTime": "2026-06-05T11:00:00Z",
                        "timeZone": "UTC"
                    },
                    "attendees": [
                        {"emailAddress": {"name": "Sarah Jenkins"}},
                        {"emailAddress": {"name": "Bob White"}},
                        {"emailAddress": {"name": "Marcus Vance"}}
                    ]
                },
                {
                    "subject": "Node-04 Outage Retrospective",
                    "start": {
                        "dateTime": "2026-06-05T14:00:00Z",
                        "timeZone": "UTC"
                    },
                    "end": {
                        "dateTime": "2026-06-05T15:00:00Z",
                        "timeZone": "UTC"
                    },
                    "attendees": [
                        {"emailAddress": {"name": "System Sentinel"}},
                        {"emailAddress": {"name": "Sarah Jenkins"}},
                        {"emailAddress": {"name": "Marcus Vance"}}
                    ]
                },
                {
                    "subject": "Q4 Strategic Roadmap & Timeline Review",
                    "start": {
                        "dateTime": "2026-06-06T09:00:00Z",
                        "timeZone": "UTC"
                    },
                    "end": {
                        "dateTime": "2026-06-06T10:30:00Z",
                        "timeZone": "UTC"
                    },
                    "attendees": [
                        {"emailAddress": {"name": "Emily Vance"}},
                        {"emailAddress": {"name": "Sarah Jenkins"}},
                        {"emailAddress": {"name": "Marcus Vance"}}
                    ]
                }
            ],
            "todo_tasks": [
                {
                    "title": "Fix Planner sync credentials",
                    "status": "notStarted",
                    "importance": "high",
                    "dueDateTime": {
                        "dateTime": "2026-06-06T12:00:00Z",
                        "timeZone": "UTC"
                    }
                },
                {
                    "title": "Verify tenant ID permissions for Planner APIs",
                    "status": "inProgress",
                    "importance": "high",
                    "dueDateTime": {
                        "dateTime": "2026-06-05T18:00:00Z",
                        "timeZone": "UTC"
                    }
                },
                {
                    "title": "Audit external ingress points",
                    "status": "completed",
                    "importance": "normal",
                    "dueDateTime": {
                        "dateTime": "2026-06-04T12:00:00Z",
                        "timeZone": "UTC"
                    }
                },
                {
                    "title": "Optimize Groq fallback context limits",
                    "status": "notStarted",
                    "importance": "normal",
                    "dueDateTime": {
                        "dateTime": "2026-06-07T12:00:00Z",
                        "timeZone": "UTC"
                    }
                }
            ],
            "planner_tasks": [
                {
                    "title": "Update client secrets in Azure portal",
                    "percentComplete": 0,
                    "priority": 1,
                    "dueDateTime": "2026-06-06T17:00:00Z"
                },
                {
                    "title": "Failover test Node-04",
                    "percentComplete": 50,
                    "priority": 3,
                    "dueDateTime": "2026-06-05T20:00:00Z"
                },
                {
                    "title": "Update context truncation rules",
                    "percentComplete": 100,
                    "priority": 9,
                    "dueDateTime": "2026-06-04T12:00:00Z"
                },
                {
                    "title": "Deploy secondary token cache nodes",
                    "percentComplete": 0,
                    "priority": 5,
                    "dueDateTime": "2026-06-08T12:00:00Z"
                }
            ],
            "teams_chats": [
                {
                    "topic": "Phoenix Integration Blocker",
                    "chatType": "group",
                    "webUrl": "#",
                    "id": "chat-phoenix",
                    "messages": [
                        {
                            "from": {"user": {"displayName": "Sarah Jenkins"}},
                            "body": {"content": "We need the credentials updated on the tenant portal immediately. Sarah's local build is breaking."},
                            "createdDateTime": "2026-06-05T08:10:00Z"
                        },
                        {
                            "from": {"user": {"displayName": "Bob White"}},
                            "body": {"content": "I uploaded the design files, but we can't test page binding without the token cache layer active."},
                            "createdDateTime": "2026-06-05T08:12:00Z"
                        },
                        {
                            "from": {"user": {"displayName": "Marcus Vance"}},
                            "body": {"content": "Understood. I will retrieve the client secret and update it in Azure before standup."},
                            "createdDateTime": "2026-06-05T08:15:00Z"
                        }
                    ]
                },
                {
                    "topic": "Node-04 Health Check",
                    "chatType": "group",
                    "webUrl": "#",
                    "id": "chat-node04",
                    "messages": [
                        {
                            "from": {"user": {"displayName": "System Sentinel"}},
                            "body": {"content": "Node-04 memory saturation warning resolved. Failover successful."},
                            "createdDateTime": "2026-06-05T07:46:00Z"
                        },
                        {
                            "from": {"user": {"displayName": "Sarah Jenkins"}},
                            "body": {"content": "Excellent work. Latency is back down to 14ms nominal values."},
                            "createdDateTime": "2026-06-05T07:50:00Z"
                        }
                    ]
                }
            ],
            "documents": [
                {
                    "id": "doc-roadmap",
                    "name": "Q4 Strategic Roadmap & Timeline.pdf",
                    "description": "Full roadmap of deliverables, agent dependencies, and timeline milestones for next quarter's integrations.",
                    "webUrl": "#",
                    "fileSystemInfo": {"lastModifiedDateTime": "2026-06-04T10:14:00Z"}
                },
                {
                    "id": "doc-budget",
                    "name": "Budget Projections Q3_Final.xlsx",
                    "description": "Excel workbook tracking cost metrics, Groq model token utilization spends, and operational yields.",
                    "webUrl": "#",
                    "fileSystemInfo": {"lastModifiedDateTime": "2026-06-03T16:50:00Z"}
                },
                {
                    "id": "doc-design",
                    "name": "WorkSphere UI Design Guidelines.docx",
                    "description": "Unified glassmorphism and connection badge design requirements for front-end fidelity.",
                    "webUrl": "#",
                    "fileSystemInfo": {"lastModifiedDateTime": "2026-06-04T15:30:00Z"}
                },
                {
                    "id": "doc-azure",
                    "name": "Azure Active Directory Integration Guide.docx",
                    "description": "App registrations, client credentials, and Planner API permission scopes setup instructions.",
                    "webUrl": "#",
                    "fileSystemInfo": {"lastModifiedDateTime": "2026-06-01T09:00:00Z"}
                }
            ]
        }

    async def get_profile(self) -> dict:
        """
        Fetches the user's Microsoft Graph profile details. Supports caching.
        """
        if self.access_token.startswith("dummy"):
            return self._get_mock_data()["profile"]

        cache_key = f"graph_response:profile:{self.token_hash}"
        cached = await cache_client.get(cache_key)
        if cached is not None and "data" in cached:
            return cached["data"]

        try:
            async with httpx.AsyncClient() as client:
                url = f"{self.base_url}/me"
                response = await client.get(url, headers=self.headers)
                response.raise_for_status()
                data = response.json()
                await cache_client.set(cache_key, {"data": data}, ttl=settings.graph_cache_ttl)
                return data
        except Exception as e:
            print(f"[GraphClient] Error fetching profile: {e}")
            raise e

    async def get_messages(self, top: int = 20) -> list:
        """
        Fetches the last N messages from the user's Outlook inbox. Supports caching.
        """
        if self.access_token.startswith("dummy"):
            return self._get_mock_data()["emails"][:top]

        cache_key = f"graph_response:messages:{self.token_hash}:{top}"
        cached = await cache_client.get(cache_key)
        if cached is not None and "data" in cached:
            return cached["data"]

        try:
            async with httpx.AsyncClient() as client:
                url = f"{self.base_url}/me/messages?$top={top}&$select=subject,bodyPreview,from,receivedDateTime"
                response = await client.get(url, headers=self.headers)
                response.raise_for_status()
                data = response.json().get("value", [])
                await cache_client.set(cache_key, {"data": data}, ttl=settings.graph_cache_ttl)
                return data
        except Exception as e:
            print(f"[GraphClient] Error fetching messages: {e}")
            raise e

    async def get_calendar_events(self) -> list:
        """
        Fetches the user's Outlook Calendar events. Supports caching.
        """
        if self.access_token.startswith("dummy"):
            return self._get_mock_data()["meetings"]

        cache_key = f"graph_response:events:{self.token_hash}"
        cached = await cache_client.get(cache_key)
        if cached is not None and "data" in cached:
            return cached["data"]

        try:
            async with httpx.AsyncClient() as client:
                url = f"{self.base_url}/me/events?$select=subject,start,end,attendees"
                response = await client.get(url, headers=self.headers)
                response.raise_for_status()
                data = response.json().get("value", [])
                await cache_client.set(cache_key, {"data": data}, ttl=settings.graph_cache_ttl)
                return data
        except Exception as e:
            print(f"[GraphClient] Error fetching calendar events: {e}")
            raise e

    async def get_tasks(self) -> list:
        """
        Fetches tasks from Outlook/Microsoft To-Do default list. Supports caching.
        """
        if self.access_token.startswith("dummy"):
            return self._get_mock_data()["todo_tasks"]

        cache_key = f"graph_response:todo_tasks:{self.token_hash}"
        cached = await cache_client.get(cache_key)
        if cached is not None and "data" in cached:
            return cached["data"]

        try:
            async with httpx.AsyncClient() as client:
                # 1. Fetch todo lists to find default
                lists_url = f"{self.base_url}/me/todo/lists"
                lists_response = await client.get(lists_url, headers=self.headers)
                lists_response.raise_for_status()
                lists = lists_response.json().get("value", [])
                
                default_list_id = None
                for lst in lists:
                    if lst.get("wellKnownListName") == "defaultList":
                        default_list_id = lst.get("id")
                        break
                
                if not default_list_id and lists:
                    default_list_id = lists[0].get("id")
                    
                if not default_list_id:
                    return []
                    
                # 2. Get tasks from default list
                tasks_url = f"{self.base_url}/me/todo/lists/{default_list_id}/tasks"
                tasks_response = await client.get(tasks_url, headers=self.headers)
                tasks_response.raise_for_status()
                data = tasks_response.json().get("value", [])
                await cache_client.set(cache_key, {"data": data}, ttl=settings.graph_cache_ttl)
                return data
        except Exception as e:
            print(f"[GraphClient] Error fetching To-Do tasks: {e}")
            raise e

    async def get_planner_tasks(self) -> list:
        """
        Fetches the Microsoft Planner tasks assigned to the user. Supports caching.
        """
        if self.access_token.startswith("dummy"):
            return self._get_mock_data()["planner_tasks"]

        cache_key = f"graph_response:planner_tasks:{self.token_hash}"
        cached = await cache_client.get(cache_key)
        if cached is not None and "data" in cached:
            return cached["data"]

        try:
            async with httpx.AsyncClient() as client:
                url = f"{self.base_url}/me/planner/tasks"
                response = await client.get(url, headers=self.headers)
                response.raise_for_status()
                data = response.json().get("value", [])
                await cache_client.set(cache_key, {"data": data}, ttl=settings.graph_cache_ttl)
                return data
        except Exception as e:
            print(f"[GraphClient] Error fetching Planner tasks: {e}")
            raise e

    async def get_teams_chats(self) -> list:
        """
        Fetches active Microsoft Teams chats for the user. Supports caching.
        """
        if self.access_token.startswith("dummy"):
            return self._get_mock_data()["teams_chats"]

        cache_key = f"graph_response:teams_chats:{self.token_hash}"
        cached = await cache_client.get(cache_key)
        if cached is not None and "data" in cached:
            return cached["data"]

        try:
            async with httpx.AsyncClient() as client:
                url = f"{self.base_url}/me/chats?$top=10&$expand=messages"
                response = await client.get(url, headers=self.headers)
                response.raise_for_status()
                data = response.json().get("value", [])
                await cache_client.set(cache_key, {"data": data}, ttl=settings.graph_cache_ttl)
                return data
        except Exception as e:
            print(f"[GraphClient] Error fetching Teams chats: {e}")
            raise e

    async def search_documents(self, query: str) -> list:
        """
        Searches user files in OneDrive. Supports caching.
        """
        if self.access_token.startswith("dummy"):
            q_lower = query.lower()
            mock_docs = self._get_mock_data()["documents"]
            matched_docs = []
            
            for doc in mock_docs:
                # Simple keyword matching
                if (any(word in q_lower for word in ["roadmap", "timeline", "q4"]) and "roadmap" in doc["name"].lower()) or \
                   (any(word in q_lower for word in ["budget", "projections", "q3", "cost"]) and "budget" in doc["name"].lower()) or \
                   (any(word in q_lower for word in ["design", "guidelines", "glassmorphism"]) and "design" in doc["name"].lower()) or \
                   (any(word in q_lower for word in ["azure", "aad", "credentials", "secrets", "planner"]) and "azure" in doc["name"].lower()):
                    matched_docs.append(doc)
            
            # Fallback if no matching document, return all mock documents so the LLM has context to process
            return matched_docs if matched_docs else mock_docs

        query_hash = hashlib.md5(query.encode('utf-8')).hexdigest()
        cache_key = f"graph_response:doc_search:{self.token_hash}:{query_hash}"
        cached = await cache_client.get(cache_key)
        if cached is not None and "data" in cached:
            return cached["data"]

        try:
            async with httpx.AsyncClient() as client:
                url = f"{self.base_url}/me/drive/root/search(q='{query}')"
                response = await client.get(url, headers=self.headers)
                response.raise_for_status()
                data = response.json().get("value", [])
                await cache_client.set(cache_key, {"data": data}, ttl=settings.graph_cache_ttl)
                return data
        except Exception as e:
            print(f"[GraphClient] Error searching OneDrive: {e}")
            raise e

    async def get_batched_dashboard_data(self) -> dict:
        """
        Executes a Microsoft Graph JSON batch request to fetch emails, calendar events, 
        planner tasks, and teams chats in a single HTTP network call.
        """
        if self.access_token.startswith("dummy"):
            mock_data = self._get_mock_data()
            structured_data = {
                "emails": mock_data["emails"],
                "meetings": mock_data["meetings"],
                "planner_tasks": mock_data["planner_tasks"],
                "teams_chats": mock_data["teams_chats"]
            }
            # Cache individual items to guarantee cache hits
            await cache_client.set(f"graph_response:messages:{self.token_hash}:20", {"data": structured_data["emails"]}, ttl=settings.graph_cache_ttl)
            await cache_client.set(f"graph_response:events:{self.token_hash}", {"data": structured_data["meetings"]}, ttl=settings.graph_cache_ttl)
            await cache_client.set(f"graph_response:planner_tasks:{self.token_hash}", {"data": structured_data["planner_tasks"]}, ttl=settings.graph_cache_ttl)
            await cache_client.set(f"graph_response:teams_chats:{self.token_hash}", {"data": structured_data["teams_chats"]}, ttl=settings.graph_cache_ttl)
            
            await cache_client.set(f"graph_response:batched_dashboard:{self.token_hash}", structured_data, ttl=settings.graph_cache_ttl)
            return structured_data

        cache_key = f"graph_response:batched_dashboard:{self.token_hash}"
        cached = await cache_client.get(cache_key)
        if cached is not None:
            return cached

        try:
            executor = BatchGraphExecutor(self.access_token)
            requests = [
                {
                    "id": "emails",
                    "method": "GET",
                    "url": "/me/messages?$top=20&$select=subject,bodyPreview,from,receivedDateTime"
                },
                {
                    "id": "meetings",
                    "method": "GET",
                    "url": "/me/events?$select=subject,start,end,attendees"
                },
                {
                    "id": "planner_tasks",
                    "method": "GET",
                    "url": "/me/planner/tasks"
                },
                {
                    "id": "teams_chats",
                    "method": "GET",
                    "url": "/me/chats?$top=10&$expand=messages"
                }
            ]
            
            batch_res = await executor.execute_batch(requests)
            
            structured_data = {
                "emails": batch_res.get("emails", {}).get("body", {}).get("value", []),
                "meetings": batch_res.get("meetings", {}).get("body", {}).get("value", []),
                "planner_tasks": batch_res.get("planner_tasks", {}).get("body", {}).get("value", []),
                "teams_chats": batch_res.get("teams_chats", {}).get("body", {}).get("value", [])
            }
            
            # Cache the individual items to guarantee cache hits for individual agent queries
            await cache_client.set(f"graph_response:messages:{self.token_hash}:20", {"data": structured_data["emails"]}, ttl=settings.graph_cache_ttl)
            await cache_client.set(f"graph_response:events:{self.token_hash}", {"data": structured_data["meetings"]}, ttl=settings.graph_cache_ttl)
            await cache_client.set(f"graph_response:planner_tasks:{self.token_hash}", {"data": structured_data["planner_tasks"]}, ttl=settings.graph_cache_ttl)
            await cache_client.set(f"graph_response:teams_chats:{self.token_hash}", {"data": structured_data["teams_chats"]}, ttl=settings.graph_cache_ttl)
            
            await cache_client.set(cache_key, structured_data, ttl=settings.graph_cache_ttl)
            return structured_data
        except Exception as e:
            print(f"[GraphClient] Error fetching batch data: {e}")
            raise e

    async def create_todo_task(self, title: str) -> dict:
        if self.access_token.startswith("dummy"):
            return {"id": "dummy-task-id", "title": title}
            
        try:
            async with httpx.AsyncClient() as client:
                # 1. Fetch todo lists
                lists_url = f"{self.base_url}/me/todo/lists"
                lists_response = await client.get(lists_url, headers=self.headers)
                lists_response.raise_for_status()
                lists = lists_response.json().get("value", [])
                
                default_list_id = None
                for lst in lists:
                    if lst.get("wellKnownListName") == "defaultList":
                        default_list_id = lst.get("id")
                        break
                
                if not default_list_id and lists:
                    default_list_id = lists[0].get("id")
                    
                if not default_list_id:
                    raise Exception("Could not find default To-Do list")
                    
                # 2. Create task
                url = f"{self.base_url}/me/todo/lists/{default_list_id}/tasks"
                payload = {"title": title}
                resp = await client.post(url, headers=self.headers, json=payload)
                resp.raise_for_status()
                return resp.json()
        except Exception as e:
            print(f"[GraphClient] Error creating To-Do task: {e}")
            raise e

    async def send_email(self, subject: str, content: str, to_email: str) -> dict:
        if self.access_token.startswith("dummy"):
            return {"status": "sent"}
            
        try:
            async with httpx.AsyncClient() as client:
                url = f"{self.base_url}/me/sendMail"
                payload = {
                    "message": {
                        "subject": subject,
                        "body": {
                            "contentType": "Text",
                            "content": content
                        },
                        "toRecipients": [
                            {
                                "emailAddress": {
                                    "address": to_email
                                }
                            }
                        ]
                    }
                }
                resp = await client.post(url, headers=self.headers, json=payload)
                resp.raise_for_status()
                return {"status": "sent"}
        except Exception as e:
            print(f"[GraphClient] Error sending email: {e}")
            raise e

    async def create_event(self, subject: str, start_iso: str, end_iso: str, attendees_emails: list) -> dict:
        if self.access_token.startswith("dummy"):
            return {"id": "dummy-event-id", "subject": subject}
            
        try:
            async with httpx.AsyncClient() as client:
                url = f"{self.base_url}/me/events"
                payload = {
                    "subject": subject,
                    "start": {
                        "dateTime": start_iso,
                        "timeZone": "UTC"
                    },
                    "end": {
                        "dateTime": end_iso,
                        "timeZone": "UTC"
                    },
                    "attendees": [
                        {
                            "emailAddress": {
                                "address": email
                            },
                            "type": "required"
                        }
                        for email in attendees_emails
                    ]
                }
                resp = await client.post(url, headers=self.headers, json=payload)
                resp.raise_for_status()
                return resp.json()
        except Exception as e:
            print(f"[GraphClient] Error creating calendar event: {e}")
            raise e

