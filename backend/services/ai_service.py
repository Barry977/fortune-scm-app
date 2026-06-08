import logging
import httpx

logger = logging.getLogger(__name__)


async def generate_content(prompt: str, provider: str = "openai", api_key: str = "",
                           model: str = "gpt-4o", base_url: str = "") -> str:
    if provider == "openai":
        return await _call_openai(prompt, api_key, model, base_url or "https://api.openai.com/v1")
    elif provider == "anthropic":
        return await _call_anthropic(prompt, api_key, model)
    elif provider == "custom":
        return await _call_custom(prompt, api_key, model, base_url)
    else:
        raise ValueError(f"Unknown provider: {provider}")


async def _call_openai(prompt: str, api_key: str, model: str, base_url: str) -> str:
    url = f"{base_url.rstrip('/')}/chat/completions"
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": "You are a professional LinkedIn content writer for logistics/supply chain industry. Write engaging, insightful posts."},
            {"role": "user", "content": prompt},
        ],
        "max_tokens": 1000,
    }
    async with httpx.AsyncClient(timeout=60) as client:
        resp = await client.post(url, json=payload, headers=headers)
        resp.raise_for_status()
        data = resp.json()
        return data["choices"][0]["message"]["content"]


async def _call_anthropic(prompt: str, api_key: str, model: str) -> str:
    url = "https://api.anthropic.com/v1/messages"
    headers = {
        "x-api-key": api_key,
        "anthropic-version": "2023-06-01",
        "Content-Type": "application/json",
    }
    payload = {
        "model": model or "claude-sonnet-4-20250514",
        "max_tokens": 1000,
        "system": "You are a professional LinkedIn content writer for logistics/supply chain industry.",
        "messages": [{"role": "user", "content": prompt}],
    }
    async with httpx.AsyncClient(timeout=60) as client:
        resp = await client.post(url, json=payload, headers=headers)
        resp.raise_for_status()
        data = resp.json()
        return data["content"][0]["text"]


async def _call_custom(prompt: str, api_key: str, model: str, base_url: str) -> str:
    if not base_url:
        raise ValueError("Custom provider requires base_url")
    return await _call_openai(prompt, api_key, model, base_url)
