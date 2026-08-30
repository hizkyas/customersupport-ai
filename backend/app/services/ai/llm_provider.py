from typing import Protocol, List, Dict, Any

class LLMProvider(Protocol):
    """Abstract interface for LLM providers — decoupled from any specific SDK."""
    async def generate(
        self,
        system_prompt: str,
        messages: List[Dict[str, str]],
        temperature: float = 0.2
    ) -> str:
        ...

class OpenAILLMProvider:
    """OpenAI implementation of LLMProvider with mock support."""

    def __init__(self, api_key: str, model: str):
        self.api_key = api_key
        self.model = model

    async def generate(
        self,
        system_prompt: str,
        messages: List[Dict[str, str]],
        temperature: float = 0.2
    ) -> str:
        import httpx
        
        if self.api_key == "mock-key":
            # Deterministic mock response for testing offline
            last_msg = messages[-1]["content"] if messages else ""
            if "human" in last_msg.lower() or "agent" in last_msg.lower():
                return "I am connecting you with a human support agent now. Please hold on."
            return f"Based on the provided organization knowledge, here is the information: '{last_msg}'."

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        
        full_messages = [{"role": "system", "content": system_prompt}] + messages
        payload = {
            "model": self.model,
            "messages": full_messages,
            "temperature": temperature,
        }

        async with httpx.AsyncClient(timeout=60) as client:
            resp = await client.post(
                "https://api.openai.com/v1/chat/completions",
                json=payload,
                headers=headers,
            )
            resp.raise_for_status()
            data = resp.json()

        return data["choices"][0]["message"]["content"]

def get_llm_provider() -> LLMProvider:
    """Factory to return configured LLM provider."""
    from app.core.config import settings
    if settings.LLM_PROVIDER == "openai":
        return OpenAILLMProvider(
            api_key=settings.LLM_API_KEY,
            model=settings.LLM_MODEL,
        )
    raise ValueError(f"Unknown LLM provider: {settings.LLM_PROVIDER}")
