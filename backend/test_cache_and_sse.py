import asyncio
import json
import httpx
from datetime import datetime

async def test_all():
    print("Testing SSE stream and caching...")
    
    # 1. Trigger the SSE stream using httpx POST /api/query
    # We'll use Microsoft provider and dummy token to get mock results
    payload = {
        "message": "Verify dashboard features",
        "access_token": "dummy_token",
        "provider": "microsoft"
    }
    
    found_structured_event = False
    structured_payload = None
    
    # Clear old cache by running a query which automatically updates it
    async with httpx.AsyncClient() as client:
        # We stream the response
        async with client.stream("POST", "http://localhost:8000/api/query", json=payload, timeout=60.0) as response:
            assert response.status_code == 200, f"Expected 200, got {response.status_code}"
            
            async for line in response.aiter_lines():
                if line.startswith("data: "):
                    data_str = line[len("data: "):].strip()
                    try:
                        data_json = json.loads(data_str)
                        if isinstance(data_json, dict) and data_json.get("type") == "structured":
                            found_structured_event = True
                            structured_payload = data_json.get("payload")
                            print("\n[SUCCESS] Found terminal SSE structured event:")
                            print(json.dumps(data_json, indent=2))
                    except Exception as e:
                        pass
                        
    assert found_structured_event, "Terminal SSE structured event was not received"
    assert structured_payload is not None, "Structured payload is empty"
    
    # 2. Test the new GET /api/intelligence/structured endpoint
    print("\nTesting GET /api/intelligence/structured endpoint...")
    async with httpx.AsyncClient() as client:
        resp = await client.get("http://localhost:8000/api/intelligence/structured?token=dummy_token&provider=microsoft")
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}"
        
        result_json = resp.json()
        print("[SUCCESS] GET /api/intelligence/structured returned successfully:")
        print(json.dumps(result_json, indent=2))
        
        assert "urgent_emails" in result_json
        assert "upcoming_meetings" in result_json
        assert "overdue_tasks" in result_json
        assert "telemetry" in result_json

    print("\nAll integration checks passed successfully!")

if __name__ == "__main__":
    asyncio.run(test_all())
