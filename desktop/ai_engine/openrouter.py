# ai_engine/openrouter.py
"""OpenRouter API client - text + vision (multimodal) support."""
import aiohttp, asyncio, json, os
from config import (OPENROUTER_API_KEY, OPENROUTER_BASE_URL,
                    AI_MODELS, AI_TIMEOUT, AI_MAX_TOKENS, APP_NAME)

HEADERS = {
    "Authorization": f"Bearer {OPENROUTER_API_KEY}",
    "Content-Type": "application/json",
    "HTTP-Referer": "https://ejobsit.com",
    "X-Title": APP_NAME,
}

# ── Persistent executor + session ────────────────────────────────────
# Each `translate_sync()` call used to spin up a fresh event loop +
# aiohttp session — meaning a full TLS handshake per request
# (~200-400ms wasted). We instead keep ONE background thread with one
# event loop and one shared session, and dispatch every coroutine to
# it via run_coroutine_threadsafe(). Subsequent requests reuse the
# same TCP/TLS connection (HTTP keep-alive).
import threading

_EXEC_LOOP = None
_EXEC_THREAD = None
_EXEC_READY = threading.Event()
_SESSION = None

def _exec_thread_main():
    """Background thread running a permanent asyncio event loop."""
    global _EXEC_LOOP
    _EXEC_LOOP = asyncio.new_event_loop()
    asyncio.set_event_loop(_EXEC_LOOP)
    _EXEC_READY.set()
    try:
        _EXEC_LOOP.run_forever()
    finally:
        try:
            _EXEC_LOOP.close()
        except Exception:
            pass

def _ensure_executor():
    global _EXEC_THREAD
    if _EXEC_THREAD is None or not _EXEC_THREAD.is_alive():
        _EXEC_THREAD = threading.Thread(
            target=_exec_thread_main, daemon=True, name="openrouter-exec")
        _EXEC_THREAD.start()
        _EXEC_READY.wait(timeout=5)

def run_on_executor(coro, timeout=AI_TIMEOUT + 5):
    """Dispatch `coro` onto the persistent executor loop and block until
    it completes. Returns the coroutine's result, or raises."""
    _ensure_executor()
    fut = asyncio.run_coroutine_threadsafe(coro, _EXEC_LOOP)
    return fut.result(timeout=timeout)

async def _get_session() -> aiohttp.ClientSession:
    """Return the singleton aiohttp session bound to the executor loop."""
    global _SESSION
    if _SESSION is None or _SESSION.closed:
        connector = aiohttp.TCPConnector(
            limit=4, ttl_dns_cache=300, keepalive_timeout=60,
            force_close=False)
        _SESSION = aiohttp.ClientSession(connector=connector)
    return _SESSION


async def complete_stream(messages: list, on_chunk, model_key: str = "primary") -> str:
    """Streaming variant of complete().

    Calls `on_chunk(delta_text)` for every incremental piece of generated
    text — the user can start typing immediately instead of waiting for
    the full response. Returns the full assembled text at the end.

    `on_chunk` is invoked from this coroutine's event-loop thread; the
    callback should be cheap / non-blocking (e.g. queue work for the Tk
    main thread, don't do I/O directly).
    """
    model = AI_MODELS[model_key]
    payload = {
        "model": model,
        "messages": messages,
        "max_tokens": AI_MAX_TOKENS,
        "stream": True,
    }
    full_text = []
    try:
        s = await _get_session()
        async with s.post(OPENROUTER_BASE_URL, headers=HEADERS, json=payload,
                          timeout=aiohttp.ClientTimeout(total=AI_TIMEOUT)) as resp:
            if resp.status == 429:
                if model_key == "primary":
                    return await complete_stream(messages, on_chunk, "fallback")
                raise RuntimeError("RATE_LIMIT")
            if resp.status == 401:
                raise RuntimeError("INVALID_API_KEY")
            # OpenRouter streams Server-Sent Events: lines like
            # "data: {json}\n\n" and a final "data: [DONE]\n\n".
            async for raw in resp.content:
                if not raw:
                    continue
                line = raw.decode("utf-8", errors="ignore").strip()
                if not line.startswith("data:"):
                    continue
                body = line[5:].strip()
                if body == "[DONE]":
                    break
                try:
                    obj = json.loads(body)
                except json.JSONDecodeError:
                    continue
                choices = obj.get("choices") or []
                if not choices:
                    continue
                delta = choices[0].get("delta") or {}
                piece = delta.get("content") or ""
                if piece:
                    full_text.append(piece)
                    try:
                        on_chunk(piece)
                    except Exception:
                        pass
        return "".join(full_text)
    except asyncio.TimeoutError:
        if model_key == "primary":
            return await complete_stream(messages, on_chunk, "fallback")
        raise RuntimeError("TIMEOUT")

async def complete(messages: list, model_key: str = "primary") -> str:
    """Call OpenRouter API. Falls back to 'fallback' model on rate limit/timeout."""
    model   = AI_MODELS[model_key]
    payload = {"model": model, "messages": messages, "max_tokens": AI_MAX_TOKENS}
    try:
        s = await _get_session()
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
