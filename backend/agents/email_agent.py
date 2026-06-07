import os
import json
import hashlib
from graph.client import GraphClient
from graph.gmail_client import GmailClient
from ai.model_router import model_router
from memory.cache import cache_client
from ai.runtime_settings import settings

EXCLUDE_PATTERNS = [
    'noreply', 'no-reply', 'donotreply', 'do-not-reply',
    'notification', 'newsletter', 'unsubscribe', 'marketing',
    'assessment', 'extension update', 'chrome extension',
    'update for', 'days assessment', 'automated', 'auto-generated',
    'mailer-daemon', 'postmaster', 'bounce',
    'security alert from google',  # Keep this ONLY if sender is noreply@google.com
]

def is_relevant_email(email: dict) -> bool:
    subject = email.get('subject', '').lower()
    sender = email.get('from', '').lower()
    # Exclude automated senders
    if any(pattern in sender for pattern in ['noreply', 'no-reply', 'donotreply', 'notifications@', 'alerts@']):
        return False
    # Exclude promotional subjects
    exclude_subjects = ['extension update', 'days assessment', 'newsletter', 'unsubscribe', 'marketing', 'promotional']
    if any(pattern in subject for pattern in exclude_subjects):
        return False
    # Keep security alerts ONLY if they are from a trusted sender (not google noreply)
    if 'security alert' in subject and 'noreply' in sender:
        return False
    return True

class EmailAgent:
    async def run(self, access_token: str, user_query: str, provider: str = "microsoft") -> dict:
        """
        Fetches emails, performs optimization/truncation, hashes the data for caching, 
        and extracts urgent emails, action items, and summaries via the Model Router.
        """
        try:
            # 1. Fetch raw emails
            if provider == "google":
                gmail_client = GmailClient(access_token)
                raw_emails = await gmail_client.get_messages(20)
                emails = []
                for email in raw_emails:
                    emails.append({
                        "subject": email.get("subject", ""),
                        "bodyPreview": email.get("snippet", ""),
                        "from": {"emailAddress": {"name": email.get("from", "")}},
                        "receivedDateTime": email.get("date", "")
                    })
            else:
                client = GraphClient(access_token)
                emails = await client.get_messages(20)
            
            # Preprocess and truncate inputs to save tokens
            raw_processed = []
            for email in emails:
                raw_processed.append({
                    "subject": email.get("subject", "")[:100],
                    "snippet": email.get("bodyPreview", "")[:200],
                    "from": email.get("from", {}).get("emailAddress", {}).get("name", "")[:50] if isinstance(email.get("from"), dict) else email.get("from", "")[:50],
                    "date": email.get("receivedDateTime", "")
                })

            processed_emails = [e for e in raw_processed if is_relevant_email(e)]

            # 2. Caching layer optimization
            raw_json = json.dumps(processed_emails, sort_keys=True)
            data_hash = hashlib.md5(raw_json.encode('utf-8')).hexdigest()
            cache_key = f"email_agent:{data_hash}:{hashlib.md5(user_query.encode('utf-8')).hexdigest()}"
            
            cached_result = await cache_client.get(cache_key)
            if cached_result:
                return cached_result

            # 3. Urgency and Approval Detection (Python-based substring matching)
            keywords_str = getattr(settings, "urgency_keywords", "")
            if not keywords_str:
                keywords_str = "urgent\nasap\nescalation\ncritical\nboard review\ndeadline today"
            
            urgency_keywords = [
                kw.strip().lower() 
                for kw in keywords_str.split("\n") 
                if kw.strip()
            ]

            approval_phrases = [
                "please approve",
                "awaiting sign-off",
                "needs your review",
                "action required",
                "pending your decision",
                "approval",
                "approve",
                "sign-off"
            ]

            python_urgent = []
            python_approvals = []

            for email in processed_emails:
                subj = email.get("subject", "")
                snip = email.get("snippet", "")
                sender = email.get("from", "")
                text_to_check = f"{subj} {snip}".lower()

                # Case-insensitive substring search for urgency keywords
                is_urgent = False
                for kw in urgency_keywords:
                    if kw in text_to_check:
                        is_urgent = True
                        break
                if is_urgent:
                    python_urgent.append({
                        "subject": subj,
                        "sender": sender,
                        "reason": "Flagged by urgency keywords"
                    })

                # Case-insensitive substring search for approval phrases
                is_approval = False
                for phrase in approval_phrases:
                    if phrase in text_to_check:
                        is_approval = True
                        break
                if is_approval:
                    python_approvals.append({
                        "item": subj,
                        "requested_by": sender,
                        "idle_hours": 24
                    })

            # 4. Prompt definition
            prompt = f"""
You are an Executive Communications Analyst reviewing the user's inbox.
Analyze these emails:
{json.dumps(processed_emails, indent=1)}

Identify and extract the following business insights based on the emails and the user's query:
1) Urgent Emails: Emails needing attention within 24 hours. Exclude automated notifications.
2) Pending Approvals: Invoices, budgets, sign-offs, or decisions awaiting approval.
3) Stakeholder Sentiment: Critical concerns, timeline questions, anxieties, or sentiment shifts raised by stakeholders.

Context (what the user is asking about): {user_query}
"""
            # Structured extraction schema
            schema = {
                "urgent_emails": [{"subject": "email subject", "sender": "sender name/email", "reason": "reason why it is urgent"}],
                "pending_approvals": [{"item": "approval item details", "requested_by": "sender/requester name", "idle_hours": 24}],
                "stakeholder_sentiment": [{"name": "stakeholder name", "sentiment": "POSITIVE/CONCERNED/NEGATIVE", "signal": "description of concern or signal"}]
            }
            
            # Execute through router
            preferred_model = getattr(settings, "per_analyst_models", {}).get("email")
            result = await model_router.structured_extract(
                content=prompt,
                schema=schema,
                preferred_model=preferred_model
            )
            
            # Merge Python-detected items and LLM-extracted items
            urgent_emails = result.get("urgent_emails", [])
            for item in python_urgent:
                item_subject = item["subject"].lower()
                if not any(item_subject in existing.get("subject", "").lower() for existing in urgent_emails):
                    urgent_emails.append(item)

            pending_approvals = result.get("pending_approvals", [])
            for item in python_approvals:
                item_subject = item["item"].lower()
                if not any(item_subject in existing.get("item", "").lower() for existing in pending_approvals):
                    pending_approvals.append(item)

            stakeholder_sentiment = result.get("stakeholder_sentiment", [])

            structured_res = {
                "urgent_emails": urgent_emails,
                "pending_approvals": pending_approvals,
                "stakeholder_sentiment": stakeholder_sentiment
            }
            
            # Cache the result
            await cache_client.set(cache_key, structured_res, ttl=settings.graph_cache_ttl)
            return structured_res

        except Exception as e:
            return {
                "urgent_emails": [],
                "pending_approvals": [],
                "stakeholder_sentiment": [],
                "error": str(e)
            }
