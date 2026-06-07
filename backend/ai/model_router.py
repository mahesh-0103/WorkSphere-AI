import asyncio
import time
from typing import AsyncGenerator, Optional
from ai.provider_registry import get_provider
from ai.health_monitor import health_monitor
from ai.runtime_settings import settings

# Observability counters
ROUTER_METRICS = {
    "requests_total": 0,
    "fallbacks_total": 0,
    "model_selections": {},  # model -> count
    "failures": {}           # model -> count
}

class ModelRouter:
    def __init__(self):
        # Default resolved inference provider (e.g. Groq)
        self.provider = get_provider()

    def _get_ordered_models(self, preferred_model: Optional[str] = None) -> list:
        # Construct priority sequence list
        all_models = []
        if preferred_model:
            all_models.append(preferred_model.lower())
        all_models.append(settings.primary_model.lower())
        for m in settings.fallback_models:
            all_models.append(m.lower())
        
        # Deduplicate while preserving order
        seen = set()
        ordered = []
        for m in all_models:
            if m not in seen:
                seen.add(m)
                ordered.append(m)
        return ordered

    async def generate_response(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        response_format: Optional[str] = None,
        timeout: Optional[float] = None,
        preferred_model: Optional[str] = None,
        max_tokens: Optional[int] = None
    ) -> str:
        models = self._get_ordered_models(preferred_model)
        ROUTER_METRICS["requests_total"] += 1
        
        fallback_occurred = False
        
        for idx, model in enumerate(models):
            if not health_monitor.is_healthy(model):
                continue
                
            if idx > 0:
                fallback_occurred = True

            max_retries = 2
            for attempt in range(max_retries):
                try:
                    res = await self.provider.generate_response(
                        model_name=model,
                        prompt=prompt,
                        system_prompt=system_prompt,
                        response_format=response_format,
                        timeout=timeout,
                        max_tokens=max_tokens
                    )
                    health_monitor.report_success(model)
                    
                    # Track metrics
                    ROUTER_METRICS["model_selections"][model] = ROUTER_METRICS["model_selections"].get(model, 0) + 1
                    if fallback_occurred:
                        ROUTER_METRICS["fallbacks_total"] += 1
                        
                    return res
                    
                except Exception as e:
                    ROUTER_METRICS["failures"][model] = ROUTER_METRICS["failures"].get(model, 0) + 1
                    # Exponential backoff (1s, 2s)
                    if attempt < max_retries - 1:
                        await asyncio.sleep(2 ** attempt)
                        
            # Mark model unhealthy if all retries fail, then fall back to the next model
            health_monitor.report_failure(model)

        raise Exception("All configured WorkSphere inference models failed to generate response.")

    async def generate_stream(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        timeout: Optional[float] = None,
        preferred_model: Optional[str] = None
    ) -> AsyncGenerator[str, None]:
        models = self._get_ordered_models(preferred_model)
        ROUTER_METRICS["requests_total"] += 1
        
        fallback_occurred = False
        
        for idx, model in enumerate(models):
            if not health_monitor.is_healthy(model):
                continue
                
            if idx > 0:
                fallback_occurred = True

            max_retries = 2
            for attempt in range(max_retries):
                try:
                    stream = self.provider.generate_stream(
                        model_name=model,
                        prompt=prompt,
                        system_prompt=system_prompt,
                        timeout=timeout
                    )
                    
                    # Wrapper to track status inside generator loop
                    async def stream_wrapper():
                        try:
                            async for chunk in stream:
                                yield chunk
                            health_monitor.report_success(model)
                        except Exception as e:
                            health_monitor.report_failure(model)
                            raise e

                    # Warm up: test read first chunk to ensure stream connection is successful
                    iterator = stream_wrapper().__aiter__()
                    first_chunk = await asyncio.wait_for(iterator.__anext__(), timeout=5.0)
                    
                    ROUTER_METRICS["model_selections"][model] = ROUTER_METRICS["model_selections"].get(model, 0) + 1
                    if fallback_occurred:
                        ROUTER_METRICS["fallbacks_total"] += 1
                        
                    yield first_chunk
                    try:
                        while True:
                            chunk = await iterator.__anext__()
                            yield chunk
                    except StopAsyncIteration:
                        pass
                    return
                    
                except Exception as e:
                    ROUTER_METRICS["failures"][model] = ROUTER_METRICS["failures"].get(model, 0) + 1
                    if attempt < max_retries - 1:
                        await asyncio.sleep(2 ** attempt)
                        
            health_monitor.report_failure(model)
            
        raise Exception("All configured WorkSphere inference models failed to start streaming.")

    async def summarize_content(
        self,
        content: str,
        user_query: Optional[str] = None,
        timeout: Optional[float] = None,
        preferred_model: Optional[str] = None
    ) -> str:
        models = self._get_ordered_models(preferred_model)
        ROUTER_METRICS["requests_total"] += 1
        
        fallback_occurred = False
        
        for idx, model in enumerate(models):
            if not health_monitor.is_healthy(model):
                continue
            if idx > 0:
                fallback_occurred = True

            max_retries = 2
            for attempt in range(max_retries):
                try:
                    res = await self.provider.summarize_content(
                        model_name=model,
                        content=content,
                        user_query=user_query,
                        timeout=timeout
                    )
                    health_monitor.report_success(model)
                    ROUTER_METRICS["model_selections"][model] = ROUTER_METRICS["model_selections"].get(model, 0) + 1
                    if fallback_occurred:
                        ROUTER_METRICS["fallbacks_total"] += 1
                    return res
                except Exception as e:
                    ROUTER_METRICS["failures"][model] = ROUTER_METRICS["failures"].get(model, 0) + 1
                    if attempt < max_retries - 1:
                        await asyncio.sleep(2 ** attempt)
            
            health_monitor.report_failure(model)
            
        raise Exception("All configured WorkSphere inference models failed to summarize content.")

    async def structured_extract(
        self,
        content: str,
        schema: Optional[dict] = None,
        timeout: Optional[float] = None,
        preferred_model: Optional[str] = None
    ) -> dict:
        models = self._get_ordered_models(preferred_model)
        ROUTER_METRICS["requests_total"] += 1
        
        fallback_occurred = False
        
        for idx, model in enumerate(models):
            if not health_monitor.is_healthy(model):
                continue
            if idx > 0:
                fallback_occurred = True

            max_retries = 2
            for attempt in range(max_retries):
                try:
                    res = await self.provider.structured_extract(
                        model_name=model,
                        content=content,
                        schema=schema,
                        timeout=timeout
                    )
                    health_monitor.report_success(model)
                    ROUTER_METRICS["model_selections"][model] = ROUTER_METRICS["model_selections"].get(model, 0) + 1
                    if fallback_occurred:
                        ROUTER_METRICS["fallbacks_total"] += 1
                    return res
                except Exception as e:
                    ROUTER_METRICS["failures"][model] = ROUTER_METRICS["failures"].get(model, 0) + 1
                    if attempt < max_retries - 1:
                        await asyncio.sleep(2 ** attempt)
            
            health_monitor.report_failure(model)
            
        raise Exception("All configured WorkSphere inference models failed to extract structured data.")

# Global Model Router Instance
model_router = ModelRouter()
