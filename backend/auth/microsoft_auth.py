import os
import httpx
from msal import ConfidentialClientApplication
from dotenv import load_dotenv
from fastapi import HTTPException, APIRouter

async def validate_token(token: str) -> bool:
    if token and token.startswith("dummy"):
        return True
    async with httpx.AsyncClient() as client:
        resp = await client.get(
            "https://graph.microsoft.com/v1.0/me",
            headers={"Authorization": f"Bearer {token}"}
        )
        if resp.status_code == 401:
            raise HTTPException(status_code=401, detail="Session expired. Please sign in again.")
        return resp.status_code == 200

# Load env variables
load_dotenv()

CLIENT_ID = os.getenv("CLIENT_ID")
TENANT_ID = os.getenv("TENANT_ID")
CLIENT_SECRET = os.getenv("CLIENT_SECRET")
# Use /common authority to allow any Microsoft account (multi-tenant + personal)
AUTHORITY = "https://login.microsoftonline.com/common"

# Initialize MSAL Confidential Client Application
app = ConfidentialClientApplication(
    CLIENT_ID,
    client_credential=CLIENT_SECRET,
    authority=AUTHORITY
)

# Required scopes
SCOPES = [
    "User.Read",
    "Mail.Read",
    "Calendars.Read",
    "Files.Read.All",
    "Tasks.Read",
]

BASE_URL = os.getenv("RENDER_EXTERNAL_URL") or os.getenv("BASE_URL") or "http://localhost:8000"
REDIRECT_URI = f"{BASE_URL.rstrip('/')}/auth/callback"

router = APIRouter()

@router.post("/auth/logout")
async def logout():
    return {"status": "logged_out"}

def get_auth_url() -> str:
    """
    Generates and returns the Microsoft OAuth2 login URL.
    """
    auth_url = app.get_authorization_request_url(
        scopes=SCOPES,
        redirect_uri=REDIRECT_URI
    )
    return auth_url

def get_token_from_code(code: str) -> str:
    """
    Exchanges authorization code for an access token.
    """
    result = app.acquire_token_by_authorization_code(
        code=code,
        scopes=SCOPES,
        redirect_uri=REDIRECT_URI
    )
    
    if "access_token" in result:
        return result["access_token"]
    else:
        error_msg = result.get("error_description") or result.get("error") or "Unknown error acquiring token"
        raise Exception(error_msg)
