import httpx

class BatchGraphExecutor:
    def __init__(self, access_token: str):
        self.access_token = access_token
        self.headers = {
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json"
        }
        self.base_url = "https://graph.microsoft.com/v1.0"

    async def execute_batch(self, requests: list) -> dict:
        """
        Executes a batch request against Microsoft Graph API.
        Takes a list of request dictionaries:
        [
            {"id": "1", "method": "GET", "url": "/me/messages?$top=20"},
            {"id": "2", "method": "GET", "url": "/me/events"}
        ]
        Returns a dictionary mapping request ID to response:
        {
            "1": {"status": 200, "body": {...}},
            "2": {"status": 200, "body": {...}}
        }
        """
        if not requests:
            return {}

        async with httpx.AsyncClient() as client:
            batch_url = f"{self.base_url}/$batch"
            payload = {"requests": requests}
            
            response = await client.post(batch_url, headers=self.headers, json=payload)
            response.raise_for_status()
            
            responses_list = response.json().get("responses", [])
            
            # Map the response list by ID for easy consumption
            mapped_responses = {}
            for resp in responses_list:
                mapped_responses[str(resp.get("id"))] = {
                    "status": resp.get("status"),
                    "body": resp.get("body", {})
                }
                
            return mapped_responses
