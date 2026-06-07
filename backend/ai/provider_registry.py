from ai.groq_provider import GroqProvider
from ai.runtime_settings import settings

_registry = {}

def get_provider(provider_name: str = None):
    """
    Returns the resolved inference provider instance (defaults to setting configuration).
    """
    name = provider_name or settings.ai_provider
    
    if name not in _registry:
        if name == "groq":
            _registry[name] = GroqProvider()
        else:
            raise ValueError(f"Unsupported WorkSphere AI inference provider: {name}")
            
    return _registry[name]
