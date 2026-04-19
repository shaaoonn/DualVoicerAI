# ai_engine/openrouter.py
"""OpenRouter API client - text + vision (multimodal) support."""
import aiohttp, asyncio, os
from config import (OPENROUTER_API_KEY, OPENROUTER_BASE_URL,
                    AI_MODELS, AI_TIMEOUT, AI_MAX_TOKENS, APP_NAME)

HEADERS = {
    "Authorization": f"Bearer {OPENROUTER_API_KEY}",
    "Content-Type": "application/json",
    "HTTP-Referer": "https://ejobsit.com",
    "X-Title": APP_NAME,
}

async def complete(messages: list, model_key: str = "primary") -> str:
    """Call OpenRouter API. Falls back to 'fallback' model on rate limit/timeout."""
    model   = AI_MODELS[model_key]
    payload = {"model": model, "messages": messages, "max_tokens": AI_MAX_TOKENS}
    try:
        async with aiohttp.ClientSession() as s:
            async with s.post(OPENROUTER_BASE_URL, headers=HEADERS, json=payload,
                              timeout=aiohttp.ClientTimeout(total=AI_TIMEOUT)) as resp:
                if resp.status == 429:
                    if model_key == "primary":
                        return await complete(messages, "fallback")
                    raise RuntimeError("RATE_LIMIT")
                if resp.status == 401:
                    raise RuntimeError("INVALID_API_KEY")
                data = await resp.json()
                choices = data.get("choices")
                if not choices or not choices[0].get("message"):
                    err = data.get("error", {}).get("message", "Unknown API error")
                    raise RuntimeError(f"API_ERROR: {err}")
                return choices[0]["message"]["content"]
    except asyncio.TimeoutError:
        if model_key == "primary":
            return await complete(messages, "fallback")
        raise RuntimeError("TIMEOUT")


async def complete_vision(messages: list, model_key: str = "primary") -> str:
    """Call OpenRouter with vision/multimodal messages.
    Messages can contain image_url content blocks:
    [{"role":"user","content":[
        {"type":"text","text":"..."},
        {"type":"image_url","image_url":{"url":"data:image/png;base64,..."}}
    ]}]
    """
    # Use vision-capable model (prefer primary, all configured models support vision)
    model = AI_MODELS[model_key]
    payload = {"model": model, "messages": messages, "max_tokens": AI_MAX_TOKENS}
    try:
        async with aiohttp.ClientSession() as s:
            async with s.post(OPENROUTER_BASE_URL, headers=HEADERS, json=payload,
                              timeout=aiohttp.ClientTimeout(total=30)) as resp:
                if resp.status == 429:
                    if model_key == "primary":
                        return await complete_vision(messages, "fallback")
                    raise RuntimeError("RATE_LIMIT")
                if resp.status == 401:
                    raise RuntimeError("INVALID_API_KEY")
                data = await resp.json()
                choices = data.get("choices")
                if not choices or not choices[0].get("message"):
                    err = data.get("error", {}).get("message", "Unknown API error")
                    raise RuntimeError(f"API_ERROR: {err}")
                return choices[0]["message"]["content"]
    except asyncio.TimeoutError:
        if model_key == "primary":
            return await complete_vision(messages, "fallback")
        raise RuntimeError("TIMEOUT")
