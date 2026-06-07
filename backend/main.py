import os
import sys
# Add current directory to path to ensure local packages (api, ai, memory, etc.) are always importable
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from starlette.middleware.sessions import SessionMiddleware
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Import the router from api/routes.py
from api.routes import router as api_router

app = FastAPI(title="WorkSphere AI Backend")

# Enable session middleware
app.add_middleware(
    SessionMiddleware,
    secret_key=os.getenv("SESSION_SECRET_KEY", "worksphere_default_secret_key_1234567890"),
    session_cookie="worksphere_session"
)

@app.on_event("startup")
async def validate_groq_key():
    import httpx
    groq_key = os.getenv("GROQ_API_KEY", "")
    if not groq_key:
        print("[STARTUP WARNING] GROQ_API_KEY is not set. Briefings will fail.")
        return
    async with httpx.AsyncClient() as client:
        try:
            resp = await client.get(
                "https://api.groq.com/openai/v1/models",
                headers={"Authorization": f"Bearer {groq_key}"}
            )
            if resp.status_code == 200:
                print("[STARTUP] Groq API key validated successfully.")
            elif resp.status_code == 401:
                print("[STARTUP ERROR] Groq API key is invalid or expired. Update GROQ_API_KEY in .env")
            elif resp.status_code == 429:
                print("[STARTUP WARNING] Groq API key is rate-limited. Briefings may fail.")
            else:
                print(f"[STARTUP] Groq API responded with {resp.status_code}")
        except Exception as e:
            print(f"[STARTUP WARNING] Groq API validation request failed: {e}")

# CORS — restrict to known origins
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:8000", "http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Global exception handler
from fastapi.responses import JSONResponse
@app.exception_handler(Exception)
async def global_exception_handler(request, exc):
    return JSONResponse(
        status_code=500,
        content={"error": "An internal error occurred", "detail": str(exc)}
    )

# Include the router
app.include_router(api_router)

@app.get("/health")
@app.head("/health")
def health_check():
    return {"status": "ok"}
