import httpx

class GmailClient:
    def __init__(self, access_token: str):
        self.token = access_token
        self.base = "https://gmail.googleapis.com/gmail/v1/users/me"
        self.headers = {"Authorization": f"Bearer {access_token}"}

    async def get_messages(self, max_results: int = 20) -> list:
        async with httpx.AsyncClient() as client:
            try:
                # Get message IDs
                resp = await client.get(
                    f"{self.base}/messages",
                    params={"maxResults": max_results, "labelIds": "INBOX", "q": "is:unread"},
                    headers=self.headers
                )
                resp.raise_for_status()
                msg_ids = [m["id"] for m in resp.json().get("messages", [])]
                # Get each message detail
                messages = []
                for mid in msg_ids[:10]:
                    detail = await client.get(
                        f"{self.base}/messages/{mid}",
                        params={"format": "metadata", "metadataHeaders": ["Subject", "From", "Date"]},
                        headers=self.headers
                    )
                    if detail.status_code == 200:
                        payload = detail.json()
                        headers_list = payload.get("payload", {}).get("headers", [])
                        header_map = {h["name"]: h["value"] for h in headers_list}
                        messages.append({
                            "subject": header_map.get("Subject", "No subject"),
                            "from": header_map.get("From", "Unknown"),
                            "date": header_map.get("Date", ""),
                            "snippet": payload.get("snippet", "")
                        })
                return messages
            except Exception as e:
                print(f"Gmail fetch error: {e}")
                return []
