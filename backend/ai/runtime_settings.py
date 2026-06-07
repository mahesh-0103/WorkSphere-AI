import json, os
SETTINGS_FILE = "settings.json"
from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field

class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore"
    )

    client_id: str = Field(..., validation_alias="CLIENT_ID")
    tenant_id: str = Field(..., validation_alias="TENANT_ID")
    client_secret: str = Field(..., validation_alias="CLIENT_SECRET")

    # WorkSphere AI Configuration
    ai_provider: str = Field("groq", validation_alias="WORKSPHERE_AI_PROVIDER")
    groq_secret: str = Field(..., validation_alias="WORKSPHERE_GROQ_SECRET")

    primary_model: str = Field("openai/gpt-oss-120b", validation_alias="WORKSPHERE_PRIMARY_MODEL")
    fallback_model_1: str = Field("qwen/qwen3-32b", validation_alias="WORKSPHERE_FALLBACK_MODEL_1")
    fallback_model_2: str = Field("llama-3.3-70b-versatile", validation_alias="WORKSPHERE_FALLBACK_MODEL_2")
    fallback_model_3: str = Field("meta-llama/llama-4-scout-17b-16e-instruct", validation_alias="WORKSPHERE_FALLBACK_MODEL_3")
    fallback_model_4: str = Field("llama-3.1-8b-instant", validation_alias="WORKSPHERE_FALLBACK_MODEL_4")
    fallback_model_5: str = Field("qwen/qwen3-14b", validation_alias="WORKSPHERE_FALLBACK_MODEL_5")
    
    enabled_agents: list = Field(["email_agent", "meeting_agent", "task_agent", "research_agent"], validation_alias="WORKSPHERE_ENABLED_AGENTS")
    per_analyst_models: dict = Field(default_factory=dict, validation_alias="WORKSPHERE_PER_ANALYST_MODELS")

    max_output_tokens: int = Field(1200, validation_alias="WORKSPHERE_MAX_OUTPUT_TOKENS")
    request_timeout_seconds: int = Field(20, validation_alias="WORKSPHERE_REQUEST_TIMEOUT_SECONDS")
    agent_parallelism: int = Field(4, validation_alias="WORKSPHERE_AGENT_PARALLELISM")
    graph_cache_ttl: int = Field(300, validation_alias="WORKSPHERE_GRAPH_CACHE_TTL")
    report_cache_ttl: int = Field(180, validation_alias="WORKSPHERE_REPORT_CACHE_TTL")

    redis_url: str = Field("redis://localhost:6379/0", validation_alias="REDIS_URL")
    frontend_url: str = Field("http://localhost:3000", validation_alias="WORKSPHERE_FRONTEND_URL")
    onedrive_root: str = Field("/Documents", validation_alias="WORKSPHERE_ONEDRIVE_ROOT")

    perm_inbox: bool = True
    perm_calendar: bool = True
    perm_files: bool = True
    perm_tasks: bool = True
    file_types: list = ["pdf", "docx", "xlsx", "txt"]
    max_docs: int = 50
    include_attachments: bool = True
    include_sharepoint: bool = True
    urgency_keywords: str = "urgent\nasap\nescalation\ncritical\nboard review\ndeadline today"
    risk_sensitivity: int = 3
    flag_overdue: bool = True
    detect_sentiment: bool = True
    detect_approvals: bool = True
    notify_morning: bool = True
    notify_urgent: bool = True
    notify_approval: bool = True
    notify_eod: bool = True
    notify_channel: str = "teams"
    enable_fallback: bool = True
    enable_logging: bool = True

    @property
    def fallback_models(self) -> list:
        return [
            self.fallback_model_1,
            self.fallback_model_2,
            self.fallback_model_3,
            self.fallback_model_4,
            self.fallback_model_5,
        ]

    def load_from_file(self):
        """Load persisted settings from settings.json if it exists."""
        if os.path.exists(SETTINGS_FILE):
            try:
                with open(SETTINGS_FILE, "r") as f:
                    data = json.load(f)
                for k, v in data.items():
                    if hasattr(self, k):
                        setattr(self, k, v)
                print(f"[runtime_settings] Loaded persisted settings from {SETTINGS_FILE}")
            except Exception as e:
                print(f"[runtime_settings] Failed to load settings.json: {e}")

    def save_to_file(self):
        """Persist current mutable settings to settings.json."""
        data = {
            "primary_model": self.primary_model,
            "graph_cache_ttl": self.graph_cache_ttl,
            "report_cache_ttl": self.report_cache_ttl,
            "enabled_agents": self.enabled_agents,
            "per_analyst_models": self.per_analyst_models,
            "onedrive_root": self.onedrive_root,
            "perm_inbox": self.perm_inbox,
            "perm_calendar": self.perm_calendar,
            "perm_files": self.perm_files,
            "perm_tasks": self.perm_tasks,
            "file_types": self.file_types,
            "max_docs": self.max_docs,
            "include_attachments": self.include_attachments,
            "include_sharepoint": self.include_sharepoint,
            "urgency_keywords": self.urgency_keywords,
            "risk_sensitivity": self.risk_sensitivity,
            "flag_overdue": self.flag_overdue,
            "detect_sentiment": self.detect_sentiment,
            "detect_approvals": self.detect_approvals,
            "notify_morning": self.notify_morning,
            "notify_urgent": self.notify_urgent,
            "notify_approval": self.notify_approval,
            "notify_eod": self.notify_eod,
            "notify_channel": self.notify_channel,
            "enable_fallback": self.enable_fallback,
            "enable_logging": self.enable_logging
        }
        try:
            with open(SETTINGS_FILE, "w") as f:
                json.dump(data, f, indent=2)
            print(f"[runtime_settings] Settings persisted to {SETTINGS_FILE}")
        except Exception as e:
            print(f"[runtime_settings] Failed to save settings.json: {e}")

settings = Settings()
if os.path.exists(SETTINGS_FILE):
    with open(SETTINGS_FILE, "r") as f:
        saved = json.load(f)
        for k, v in saved.items():
            if hasattr(settings, k):
                setattr(settings, k, v)
