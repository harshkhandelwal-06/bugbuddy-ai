"""Provider-agnostic LLM adapter (Gemini, Anthropic, or any OpenAI-compatible API).

Configuration is read from environment variables (or Streamlit secrets, copied
into the environment by app.py). No key is ever stored in the repository.

  LLM_PROVIDER   gemini | anthropic | openai        (default: gemini)
  LLM_MODEL      model name, e.g. the name shown in Google AI Studio
  LLM_API_KEY    API key (or GEMINI_API_KEY / ANTHROPIC_API_KEY / OPENAI_API_KEY)
  LLM_BASE_URL   optional; use for OpenAI-compatible services such as Groq/OpenRouter
"""
from __future__ import annotations

import os
import re
import time
from dataclasses import dataclass

import requests

DEFAULT_BASE = {
    "gemini": "https://generativelanguage.googleapis.com/v1beta",
    "anthropic": "https://api.anthropic.com",
    "openai": "https://api.openai.com/v1",
}
KEY_ENV = {
    "gemini": ["LLM_API_KEY", "GEMINI_API_KEY", "GOOGLE_API_KEY"],
    "anthropic": ["LLM_API_KEY", "ANTHROPIC_API_KEY"],
    "openai": ["LLM_API_KEY", "OPENAI_API_KEY"],
}


class LLMError(RuntimeError):
    pass


@dataclass
class LLMResponse:
    text: str
    latency_s: float
    provider: str
    model: str


def config() -> dict:
    provider = os.environ.get("LLM_PROVIDER", "gemini").strip().lower()
    if provider not in DEFAULT_BASE:
        raise LLMError(f"Unknown LLM_PROVIDER '{provider}'. Use gemini, anthropic or openai.")
    key = next((os.environ[k] for k in KEY_ENV[provider] if os.environ.get(k)), "")
    model = os.environ.get("LLM_MODEL", "").strip()
    base = os.environ.get("LLM_BASE_URL", "").strip().rstrip("/") or DEFAULT_BASE[provider]
    return {"provider": provider, "model": model, "key": key, "base": base}


def describe() -> str:
    c = config()
    return f"{c['provider']} / {c['model'] or '(model not set)'}"


def _retry_delay(resp: requests.Response, attempt: int) -> float:
    m = re.search(r'"retryDelay"\s*:\s*"(\d+(?:\.\d+)?)s"', resp.text)
    if m:
        return min(float(m.group(1)) + 1, 70)
    ra = resp.headers.get("retry-after")
    if ra and ra.replace(".", "", 1).isdigit():
        return min(float(ra) + 1, 70)
    return min(5 * 2 ** attempt, 60)


def _post(url: str, headers: dict, body: dict, max_tries: int = 6) -> dict:
    last = ""
    for attempt in range(max_tries):
        try:
            resp = requests.post(url, headers=headers, json=body, timeout=120)
        except requests.RequestException as exc:  # network problem
            last = str(exc)
            time.sleep(min(5 * 2 ** attempt, 40))
            continue
        if resp.status_code == 200:
            return resp.json()
        last = f"HTTP {resp.status_code}: {resp.text[:300]}"
        if resp.status_code in (429, 500, 502, 503, 504):
            time.sleep(_retry_delay(resp, attempt))
            continue
        break
    raise LLMError(last)


def call_llm(system: str, user: str, temperature: float | None = None,
             max_tokens: int = 4096) -> LLMResponse:
    c = config()
    if not c["key"]:
        raise LLMError("No API key found. Set LLM_API_KEY (see README.md).")
    if not c["model"]:
        raise LLMError("LLM_MODEL is not set. Run: python code/check_setup.py")
    if os.environ.get("LLM_IGNORE_TEMPERATURE") == "1":
        temperature = None

    t0 = time.time()
    p, model = c["provider"], c["model"]

    if p == "gemini":
        gen = {"maxOutputTokens": max(max_tokens, 8192)}
        if temperature is not None:
            gen["temperature"] = temperature
        body = {"contents": [{"role": "user", "parts": [{"text": user}]}],
                "generationConfig": gen}
        if model.lower().startswith("gemma"):  # Gemma models take no system instruction
            body["contents"][0]["parts"][0]["text"] = system + "\n\n" + user
        else:
            body["systemInstruction"] = {"parts": [{"text": system}]}
        data = _post(f"{c['base']}/models/{model}:generateContent",
                     {"x-goog-api-key": c["key"], "content-type": "application/json"}, body)
        cands = data.get("candidates") or []
        parts = (cands[0].get("content", {}).get("parts", []) if cands else [])
        text = "".join(x.get("text", "") for x in parts if not x.get("thought"))
        if not text.strip():
            reason = cands[0].get("finishReason") if cands else data.get("promptFeedback")
            raise LLMError(f"Empty response from Gemini (reason: {reason})")

    elif p == "anthropic":
        body = {"model": model, "max_tokens": max_tokens, "system": system,
                "messages": [{"role": "user", "content": user}]}
        if temperature is not None:
            body["temperature"] = temperature
        data = _post(f"{c['base']}/v1/messages",
                     {"x-api-key": c["key"], "anthropic-version": "2023-06-01",
                      "content-type": "application/json"}, body)
        text = "".join(b.get("text", "") for b in data.get("content", []) if b.get("type") == "text")
        if not text.strip():
            raise LLMError("Empty response from Anthropic API")

    else:  # openai-compatible
        body = {"model": model, "messages": [{"role": "system", "content": system},
                                             {"role": "user", "content": user}]}
        if temperature is not None:
            body["temperature"] = temperature
        data = _post(f"{c['base']}/chat/completions",
                     {"authorization": f"Bearer {c['key']}", "content-type": "application/json"}, body)
        text = (data.get("choices") or [{}])[0].get("message", {}).get("content") or ""
        if not text.strip():
            raise LLMError("Empty response from the chat-completions API")

    return LLMResponse(text=text, latency_s=round(time.time() - t0, 2), provider=p, model=model)


def list_gemini_models() -> list[str]:
    c = config()
    resp = requests.get(f"{DEFAULT_BASE['gemini']}/models?pageSize=200",
                        headers={"x-goog-api-key": c["key"]}, timeout=30)
    if resp.status_code != 200:
        raise LLMError(f"HTTP {resp.status_code}: {resp.text[:300]}")
    return [m["name"].split("/", 1)[1] for m in resp.json().get("models", [])
            if "generateContent" in m.get("supportedGenerationMethods", [])]
