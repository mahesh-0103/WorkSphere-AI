# WorkSphere AI

A multi-agent AI workplace assistant that connects to Microsoft 365 and Google Workspace to answer questions about your emails, meetings, tasks, and documents.

---

## 1. System Overview
*   **Orchestrated Agent Fleet**: Runs parallel Communications, Meeting, Workload, and Knowledge Analysts using `asyncio.gather`.
*   **Two-Call Synthesis Pipeline**: Computes a streaming markdown Chief of Staff briefing, followed by a non-streaming structured JSON data extraction.
*   **Token Caching & SSE**: Caches structured payload data and streams it down in real-time as a terminal Server-Sent Event (SSE).
*   **Persistent Control Plane**: Toggles, sliders, and dropdown selections are persisted on settings update and re-loaded dynamically.

---

## 2. Directory Structure

```
worksphere/
├── static/                  ← Renamed from stitch_assets/
│   ├── landing_page.html
│   ├── command_center.html
│   ├── executive_intelligence.html
│   ├── agent_operations.html
│   ├── memory_explorer.html
│   └── sidebar.js
├── backend/
│   ├── main.py
│   ├── settings.json
│   ├── api/routes.py
│   ├── supervisor/supervisor.py
│   ├── agents/
│   ├── ai/
│   ├── auth/
│   ├── graph/
│   └── memory/
├── requirements.txt
├── .gitignore
└── README.md
```

---

## 3. Environment Variables (.env)

Configure these in `backend/.env` (reference `backend/.env.example`):
*   `MICROSOFT_CLIENT_ID`: Azure Client Application ID.
*   `MICROSOFT_CLIENT_SECRET`: Azure Application Secret Value.
*   `MICROSOFT_TENANT_ID`: Set to `common` for multi-tenant and personal logins.
*   `GROQ_API_KEY`: Groq API Console key.
*   `GEMINI_API_KEY`: Google Gemini Developer key (fallback model router).
*   `SUPABASE_URL`: Supabase backend endpoint URL (optional, defaults to mock if unconfigured).
*   `SUPABASE_KEY`: Supabase service role key (optional).

---

## 4. Setup & Running Instructions

### 1. Install Dependencies
```bash
pip install -r requirements.txt
```

### 2. Configure Environment
Copy `backend/.env.example` to `backend/.env` and supply all active secrets.

### 3. Run the Backend Server
```bash
cd backend
python -m uvicorn main:app --host 127.0.0.1 --port 8000 --reload
```

### 4. Access the Application
Open [http://localhost:8000](http://localhost:8000) in your web browser.
*   `/` — Landing page with Microsoft and Google login triggers.
*   `/dashboard` — Command Center with live Briefing streaming and dynamic Quick Actions.
*   `/executive_intelligence` — Chief of Staff Decision Tracker, Approval Queue, Risk Radar, and Deadlines.
*   `/agent_operations` — Agent fleet workloads, execution metrics, and streaming Activity Feed.
*   `/memory_explorer` — SVG Knowledge Graph explorer with interactive filters and search query inputs.
*   `/control_plane` — Settings configuration and persistent analyst toggles.
