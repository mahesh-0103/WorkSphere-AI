import json
import asyncio
from abc import ABC, abstractmethod
from typing import AsyncGenerator, Optional
from groq import AsyncGroq
from ai.runtime_settings import settings

class WorkSphereInferenceProvider(ABC):
    @abstractmethod
    async def generate_response(
        self,
        model_name: str,
        prompt: str,
        system_prompt: Optional[str] = None,
        response_format: Optional[str] = None,
        timeout: Optional[float] = None,
        max_tokens: Optional[int] = None
    ) -> str:
        pass

    @abstractmethod
    async def generate_stream(
        self,
        model_name: str,
        prompt: str,
        system_prompt: Optional[str] = None,
        timeout: Optional[float] = None
    ) -> AsyncGenerator[str, None]:
        pass

    @abstractmethod
    async def summarize_content(
        self,
        model_name: str,
        content: str,
        user_query: Optional[str] = None,
        timeout: Optional[float] = None
    ) -> str:
        pass

    @abstractmethod
    async def structured_extract(
        self,
        model_name: str,
        content: str,
        schema: Optional[dict] = None,
        timeout: Optional[float] = None
    ) -> dict:
        pass

    @abstractmethod
    async def health_check(self, model_name: str) -> bool:
        pass


class GroqProvider(WorkSphereInferenceProvider):
    def __init__(self):
        # Configure Groq async client using namespace secret
        self.client = AsyncGroq(api_key=settings.groq_secret)

    async def generate_response(
        self,
        model_name: str,
        prompt: str,
        system_prompt: Optional[str] = None,
        response_format: Optional[str] = None,
        timeout: Optional[float] = None,
        max_tokens: Optional[int] = None
    ) -> str:
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})

        # Set JSON format parameter
        kwargs = {}
        if response_format == "json":
            kwargs["response_format"] = {"type": "json_object"}

        timeout_val = timeout if timeout is not None else settings.request_timeout_seconds
        max_tok = max_tokens if max_tokens is not None else settings.max_output_tokens

        response = await asyncio.wait_for(
            self.client.chat.completions.create(
                model=model_name,
                messages=messages,
                max_tokens=max_tok,
                **kwargs
            ),
            timeout=float(timeout_val)
        )
        return response.choices[0].message.content

    async def generate_stream(
        self,
        model_name: str,
        prompt: str,
        system_prompt: Optional[str] = None,
        timeout: Optional[float] = None
    ) -> AsyncGenerator[str, None]:
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})

        timeout_val = timeout if timeout is not None else settings.request_timeout_seconds

        stream = await asyncio.wait_for(
            self.client.chat.completions.create(
                model=model_name,
                messages=messages,
                max_tokens=settings.max_output_tokens,
                stream=True
            ),
            timeout=float(timeout_val)
        )

        async for chunk in stream:
            content = chunk.choices[0].delta.content
            if content:
                yield content

    async def summarize_content(
        self,
        model_name: str,
        content: str,
        user_query: Optional[str] = None,
        timeout: Optional[float] = None
    ) -> str:
        prompt = f"Summarize this content:\n{content}"
        if user_query:
            prompt += f"\nContext: User query is: '{user_query}'."
        
        return await self.generate_response(model_name, prompt, timeout=timeout)

    async def structured_extract(
        self,
        model_name: str,
        content: str,
        schema: Optional[dict] = None,
        timeout: Optional[float] = None
    ) -> dict:
        prompt = f"""
Analyze the following content and extract structured data:
---
{content}
---
Respond ONLY with a JSON object. Ensure it aligns with this key structure:
{json.dumps(schema) if schema else 'object'}

Do not include any other explanations, comments, or wrapping (like ```json). Respond with raw JSON only.
"""
        raw = await self.generate_response(
            model_name=model_name,
            prompt=prompt,
            response_format="json",
            timeout=timeout
        )
        
        cleaned = raw.strip()
        if cleaned.startswith("```"):
            lines = cleaned.splitlines()
            if lines[0].startswith("```"):
                lines = lines[1:]
            if lines[-1].strip() == "```":
                lines = lines[:-1]
            cleaned = "\n".join(lines).strip()
        return json.loads(cleaned)

    async def health_check(self, model_name: str) -> bool:
        try:
            await asyncio.wait_for(
                self.client.chat.completions.create(
                    model=model_name,
                    messages=[{"role": "user", "content": "ping"}],
                    max_tokens=1
                ),
                timeout=5.0
            )
            return True
        except Exception:
            return False
