"""
AI Content Generator — generates LinkedIn posts, outreach emails, and replies
using the configured AI model (OpenAI, Claude, local LLM, etc.)
"""

import json
import logging
import os
from typing import Optional, Dict, Any, List

import httpx

from backend.database import get_db_ctx

logger = logging.getLogger(__name__)


def get_active_ai_config() -> Dict[str, Any]:
    """Get the active AI model configuration from database."""
    with get_db_ctx() as conn:
        row = conn.execute(
            "SELECT * FROM ai_model_configs WHERE is_active = 1 ORDER BY id DESC LIMIT 1"
        ).fetchone()
    
    if row:
        return dict(row)
    
    # Fallback to settings table
    with get_db_ctx() as conn:
        provider = conn.execute("SELECT value FROM settings WHERE key = 'ai_provider'").fetchone()
        api_key = conn.execute("SELECT value FROM settings WHERE key = 'ai_api_key'").fetchone()
        model = conn.execute("SELECT value FROM settings WHERE key = 'ai_model'").fetchone()
        base_url = conn.execute("SELECT value FROM settings WHERE key = 'ai_base_url'").fetchone()
    
    return {
        "provider": provider[0] if provider else "openai",
        "api_key": api_key[0] if api_key else "",
        "model_name": model[0] if model else "gpt-4o",
        "base_url": base_url[0] if base_url else "",
    }


def get_base_url(config: Dict[str, Any]) -> str:
    """Get the API base URL for the configured provider."""
    if config.get("base_url"):
        return config["base_url"].rstrip("/")
    
    provider = config.get("provider", "openai").lower()
    urls = {
        "openai": "https://api.openai.com/v1",
        "anthropic": "https://api.anthropic.com/v1",
        "claude": "https://api.anthropic.com/v1",
        "deepseek": "https://api.deepseek.com/v1",
        "moonshot": "https://api.moonshot.cn/v1",
        "zhipu": "https://open.bigmodel.cn/api/paas/v4",
        "qwen": "https://dashscope.aliyuncs.com/compatible-mode/v1",
        "baidu": "https://aip.baidubce.com/rpc/2.0/ai_custom/v1",
        "minimax": "https://api.minimax.chat/v1",
        "spark": "https://spark-api-open.xf-yun.com/v1",
        "ollama": "http://localhost:11434/v1",
    }
    return urls.get(provider, "https://api.openai.com/v1")


async def generate_content(prompt: str, max_tokens: int = 1000) -> str:
    """
    Generate content using the configured AI model.
    Supports OpenAI-compatible APIs (most providers).
    """
    config = get_active_ai_config()
    
    if not config.get("api_key"):
        raise ValueError("No AI API key configured. Please configure AI model in Settings.")
    
    base_url = get_base_url(config)
    model = config.get("model_name", "gpt-4o")
    api_key = config["api_key"]
    
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    
    # Anthropic uses different format
    provider = config.get("provider", "").lower()
    if provider in ("anthropic", "claude"):
        headers = {
            "x-api-key": api_key,
            "anthropic-version": "2023-06-01",
            "Content-Type": "application/json",
        }
        payload = {
            "model": model,
            "max_tokens": max_tokens,
            "messages": [{"role": "user", "content": prompt}],
        }
        url = f"{base_url}/messages"
    else:
        # OpenAI-compatible format
        payload = {
            "model": model,
            "max_tokens": max_tokens,
            "messages": [
                {"role": "system", "content": "You are a professional B2B content writer specializing in logistics and supply chain industry. Write in English for international audiences (US, EU, Middle East)."},
                {"role": "user", "content": prompt},
            ],
            "temperature": 0.8,
        }
        url = f"{base_url}/chat/completions"
    
    async with httpx.AsyncClient(timeout=60) as client:
        response = await client.post(url, headers=headers, json=payload)
        
        if response.status_code != 200:
            error_text = response.text[:500]
            raise Exception(f"AI API error {response.status_code}: {error_text}")
        
        data = response.json()
        
        # Anthropic response format
        if provider in ("anthropic", "claude"):
            return data["content"][0]["text"]
        
        # OpenAI-compatible format
        return data["choices"][0]["message"]["content"]


async def generate_linkedin_post(topic: str = "", style: str = "professional") -> str:
    """
    Generate a LinkedIn post for logistics/supply chain industry.
    
    Args:
        topic: Specific topic (e.g., "ocean freight rates", "supply chain resilience")
        style: Post style - "professional", "thought_leadership", "tips", "story"
    """
    style_prompts = {
        "professional": "Write a professional LinkedIn post (150-300 words) about {topic} in the logistics and supply chain industry. Include relevant hashtags. Make it engaging and informative.",
        "thought_leadership": "Write a thought-provoking LinkedIn post (200-400 words) sharing insights about {topic} in global logistics. Position the author as an industry expert. Include a question to encourage engagement.",
        "tips": "Write a practical tips post (150-250 words) sharing 3-5 actionable tips about {topic} for supply chain professionals. Use bullet points and emojis sparingly.",
        "story": "Write a storytelling LinkedIn post (200-350 words) about a logistics challenge or success related to {topic}. Make it relatable and end with a lesson learned.",
    }
    
    if not topic:
        topics = [
            "ocean freight rate trends and market outlook",
            "supply chain resilience in uncertain times",
            "cross-border e-commerce logistics",
            "sustainable shipping and green logistics",
            "Middle East trade corridor opportunities",
            "US-EU trade lane optimization",
            "warehouse automation and efficiency",
            "last-mile delivery innovations",
            "customs clearance best practices",
            "freight forwarding digital transformation",
        ]
        import random
        topic = random.choice(topics)
    
    prompt = style_prompts.get(style, style_prompts["professional"]).format(topic=topic)
    prompt += "\n\nTarget audience: Logistics professionals, supply chain managers, import/export businesses in US, Europe, and Middle East."
    
    return await generate_content(prompt, max_tokens=800)


async def generate_outreach_email(
    company_name: str = "",
    contact_title: str = "",
    context: str = "",
) -> str:
    """
    Generate a cold outreach email for potential logistics clients.
    """
    prompt = f"""Write a professional cold outreach email for a logistics company targeting potential clients.

Context:
- Target company: {company_name or 'a potential client'}
- Contact role: {contact_title or 'decision maker'}
- Additional context: {context or 'general logistics services'}

Requirements:
1. Subject line that gets opened
2. Personalized opening (reference their industry/role)
3. Brief value proposition (2-3 sentences)
4. Specific benefit for their business
5. Soft call-to-action
6. Professional signature block

Keep it under 200 words. Write in English. Tone: professional but warm, not pushy.
Focus on: international freight, supply chain optimization, cost savings, reliability."""

    return await generate_content(prompt, max_tokens=600)


async def generate_reply(
    original_message: str,
    context: str = "",
    tone: str = "professional",
) -> str:
    """
    Generate a reply to a client inquiry or message.
    """
    prompt = f"""Generate a professional reply to this message from a potential or existing client.

Original message:
---
{original_message}
---

Additional context: {context or 'Logistics and supply chain services'}

Requirements:
1. Address their specific points/questions
2. Be helpful and solution-oriented
3. Maintain {tone} tone
4. Include relevant details about our capabilities
5. Clear next steps or call-to-action
6. Write in English

Keep the reply concise (100-200 words) but thorough."""

    return await generate_content(prompt, max_tokens=500)


async def generate_linkedin_connection_note(
    person_name: str = "",
    person_title: str = "",
    person_company: str = "",
) -> str:
    """
    Generate a personalized LinkedIn connection request note (max 300 chars).
    """
    prompt = f"""Write a LinkedIn connection request note (MAX 300 characters, this is strict).

Target: {person_name or 'Professional'}, {person_title or 'Industry professional'} at {person_company or 'their company'}

Requirements:
1. Personalized reference to their role/company
2. Brief mention of mutual interest in logistics/supply chain
3. Professional and friendly tone
4. Under 300 characters total (LinkedIn limit)

Write in English. Do NOT be salesy."""

    result = await generate_content(prompt, max_tokens=200)
    # Ensure under 300 chars
    if len(result) > 300:
        result = result[:297] + "..."
    return result


async def generate_daily_content_plan() -> Dict[str, Any]:
    """
    Generate a full day's content plan:
    - 1 LinkedIn post
    - 3 connection notes
    - 2 outreach emails
    """
    post = await generate_linkedin_post()
    
    notes = []
    for _ in range(3):
        note = await generate_linkedin_connection_note()
        notes.append(note)
    
    emails = []
    for _ in range(2):
        email = await generate_outreach_email()
        emails.append(email)
    
    return {
        "linkedin_post": post,
        "connection_notes": notes,
        "outreach_emails": emails,
        "generated_at": __import__("datetime").datetime.now().isoformat(),
    }
