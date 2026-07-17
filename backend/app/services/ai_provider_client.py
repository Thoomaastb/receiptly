import json
import logging
import re
from typing import NamedTuple

import httpx

from app.models.ai_settings import AIProviderType

logger = logging.getLogger(__name__)

# Hardcoded-Defaults, falls kein model_name konfiguriert ist. Gemini-Modellnamen ändern
# sich vergleichsweise häufig — beim nächsten Provider-Review gegen die aktuelle Doku
# verifizieren, "flash" ist hier bewusst die schnelle/günstige Linie, nicht das teuerste Modell.
_DEFAULT_MODELS: dict[AIProviderType, str] = {
    AIProviderType.OLLAMA: "llama3.1",
    AIProviderType.OPENAI: "gpt-4o-mini",
    AIProviderType.ANTHROPIC: "claude-3-5-haiku-20241022",
    AIProviderType.GOOGLE: "gemini-2.5-flash",
}

_TOOL_NAME = "extract_receipt_data"

# Obergrenze für KI-Provider-Antworten — ein fehlkonfigurierter/kompromittierter Endpoint
# könnte sonst eine beliebig große Response schicken, die komplett per resp.json() in den
# Speicher geladen wird. 1 MB ist für die hier erwarteten JSON-/Tool-Use-Antworten großzügig.
_MAX_RESPONSE_BYTES = 1024 * 1024


class AIProviderError(Exception):
    """Normalisierter Fehler für jeden Provider-Call — nie eine rohe httpx-Exception durchreichen."""


class StructuredCallResult(NamedTuple):
    """Rückgabe von call_structured(): das extrahierte JSON plus Token-Verbrauch (für
    ai_usage_events, siehe ai_extraction.py). Bei einem Retry (Schema-Fallback) sind beide
    Zähler bereits über beide HTTP-Calls summiert — beide haben real Tokens verbraucht."""

    content: dict
    prompt_tokens: int
    completion_tokens: int


def _safe_json(resp: httpx.Response) -> dict:
    """
    Zentrale Stelle für alle Provider-Branches: prüft Content-Length (falls vorhanden)
    UND die tatsächliche Byte-Länge des empfangenen Bodies (Header kann fehlen oder nicht
    zur Realität passen), bevor geparst wird.
    """
    content_length = resp.headers.get("content-length")
    if content_length is not None and int(content_length) > _MAX_RESPONSE_BYTES:
        raise AIProviderError(
            f"Antwort vom KI-Provider überschreitet das Größenlimit ({_MAX_RESPONSE_BYTES} Bytes)"
        )
    if len(resp.content) > _MAX_RESPONSE_BYTES:
        raise AIProviderError(
            f"Antwort vom KI-Provider überschreitet das Größenlimit ({_MAX_RESPONSE_BYTES} Bytes)"
        )
    return resp.json()


def _strip_code_fence(text: str) -> str:
    """Manche Modelle antworten trotz JSON-Anforderung mit ```json ... ``` — Fence entfernen vor json.loads."""
    stripped = text.strip()
    if stripped.startswith("```"):
        stripped = re.sub(r"^```[a-zA-Z]*\s*", "", stripped)
        stripped = re.sub(r"\s*```$", "", stripped)
    return stripped.strip()


def _try_parse(text: str) -> dict | None:
    try:
        return json.loads(_strip_code_fence(text))
    except (json.JSONDecodeError, TypeError):
        return None


def _fallback_instruction(json_schema: dict) -> str:
    return (
        "Antworte AUSSCHLIESSLICH mit einem einzigen validen JSON-Objekt (keine Erklärung, "
        "kein Markdown-Codeblock), das exakt diesem JSON-Schema entspricht:\n"
        f"{json.dumps(json_schema)}"
    )


def resolve_model_name(provider: AIProviderType, model_name: str | None) -> str:
    """Modellname, der für einen Call tatsächlich verwendet wird (expliziter Override oder
    Hardcoded-Default) — auch außerhalb dieses Moduls relevant (ai_usage_events-Logging in
    ai_extraction.py), daher public statt in call_structured() versteckt."""
    return model_name or _DEFAULT_MODELS[provider]


async def call_structured(
    provider: AIProviderType,
    api_key: str | None,
    endpoint: str | None,
    model_name: str | None,
    system_prompt: str,
    user_prompt: str,
    json_schema: dict,
    timeout: float,
) -> StructuredCallResult:
    """
    Ruft den gegebenen KI-Provider mit provider-nativem Structured-Output auf. Liefert bei
    nicht-schema-validem JSON einen Retry über einen Prompt-JSON-Fallback (Schema als
    Textinstruktion). Alle HTTP-/Timeout-/Parse-Fehler werden zu AIProviderError normalisiert
    — niemals eine rohe httpx-Exception nach außen durchreichen.
    """
    model = resolve_model_name(provider, model_name)
    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            if provider == AIProviderType.OLLAMA:
                if not endpoint:
                    raise AIProviderError("Ollama-Aufruf ohne endpoint")
                return await _call_ollama(client, endpoint, model, system_prompt, user_prompt, json_schema)
            if provider == AIProviderType.OPENAI:
                return await _call_openai(client, api_key, model, system_prompt, user_prompt, json_schema)
            if provider == AIProviderType.ANTHROPIC:
                return await _call_anthropic(client, api_key, model, system_prompt, user_prompt, json_schema)
            if provider == AIProviderType.GOOGLE:
                return await _call_google(client, api_key, model, system_prompt, user_prompt, json_schema)
            raise AIProviderError(f"Unbekannter Provider: {provider}")
    except AIProviderError:
        raise
    except httpx.HTTPError as exc:
        raise AIProviderError(f"HTTP-/Timeout-Fehler beim KI-Provider-Call ({exc.__class__.__name__})") from exc
    except (KeyError, IndexError, TypeError) as exc:
        raise AIProviderError(
            f"Unerwartetes Antwortformat vom KI-Provider ({exc.__class__.__name__})"
        ) from exc


def _ollama_token_counts(data: dict) -> tuple[int, int]:
    """Ollama liefert prompt_eval_count/eval_count nicht in jeder Antwort (z.B. bei
    Streaming-Edgefällen) — fehlende Felder best-effort als 0 behandeln statt zu crashen."""
    return data.get("prompt_eval_count") or 0, data.get("eval_count") or 0


async def _call_ollama(
    client: httpx.AsyncClient,
    endpoint: str,
    model: str,
    system_prompt: str,
    user_prompt: str,
    json_schema: dict,
) -> StructuredCallResult:
    url = f"{endpoint.rstrip('/')}/api/chat"
    base_messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt},
    ]

    resp = await client.post(
        url,
        json={"model": model, "messages": base_messages, "format": json_schema, "stream": False},
    )
    resp.raise_for_status()
    data = _safe_json(resp)
    prompt_tokens, completion_tokens = _ollama_token_counts(data)
    parsed = _try_parse(data["message"]["content"])
    if parsed is not None:
        return StructuredCallResult(parsed, prompt_tokens, completion_tokens)

    logger.warning("Ollama-Antwort nicht schema-valide, Prompt-JSON-Fallback wird versucht")
    fallback_messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": f"{user_prompt}\n\n{_fallback_instruction(json_schema)}"},
    ]
    resp = await client.post(url, json={"model": model, "messages": fallback_messages, "stream": False})
    resp.raise_for_status()
    data = _safe_json(resp)
    fallback_prompt_tokens, fallback_completion_tokens = _ollama_token_counts(data)
    prompt_tokens += fallback_prompt_tokens
    completion_tokens += fallback_completion_tokens
    parsed = _try_parse(data["message"]["content"])
    if parsed is not None:
        return StructuredCallResult(parsed, prompt_tokens, completion_tokens)
    raise AIProviderError("Ollama-Antwort auch im Prompt-Fallback nicht als JSON parsebar")


def _openai_token_counts(data: dict) -> tuple[int, int]:
    usage = data.get("usage") or {}
    return usage.get("prompt_tokens") or 0, usage.get("completion_tokens") or 0


async def _call_openai(
    client: httpx.AsyncClient,
    api_key: str | None,
    model: str,
    system_prompt: str,
    user_prompt: str,
    json_schema: dict,
) -> StructuredCallResult:
    if not api_key:
        raise AIProviderError("OpenAI-Aufruf ohne api_key")
    url = "https://api.openai.com/v1/chat/completions"
    headers = {"Authorization": f"Bearer {api_key}"}
    base_messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt},
    ]

    resp = await client.post(
        url,
        headers=headers,
        json={
            "model": model,
            "messages": base_messages,
            "response_format": {
                "type": "json_schema",
                "json_schema": {"name": "receipt_extraction", "schema": json_schema, "strict": True},
            },
        },
    )
    resp.raise_for_status()
    data = _safe_json(resp)
    prompt_tokens, completion_tokens = _openai_token_counts(data)
    parsed = _try_parse(data["choices"][0]["message"]["content"])
    if parsed is not None:
        return StructuredCallResult(parsed, prompt_tokens, completion_tokens)

    logger.warning("OpenAI-Antwort nicht schema-valide, Prompt-JSON-Fallback wird versucht")
    fallback_messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": f"{user_prompt}\n\n{_fallback_instruction(json_schema)}"},
    ]
    resp = await client.post(
        url, headers=headers, json={"model": model, "messages": fallback_messages}
    )
    resp.raise_for_status()
    data = _safe_json(resp)
    fallback_prompt_tokens, fallback_completion_tokens = _openai_token_counts(data)
    prompt_tokens += fallback_prompt_tokens
    completion_tokens += fallback_completion_tokens
    parsed = _try_parse(data["choices"][0]["message"]["content"])
    if parsed is not None:
        return StructuredCallResult(parsed, prompt_tokens, completion_tokens)
    raise AIProviderError("OpenAI-Antwort auch im Prompt-Fallback nicht als JSON parsebar")


def _anthropic_token_counts(data: dict) -> tuple[int, int]:
    """Anthropic liefert kein total_tokens-Feld — input_tokens/output_tokens sind hier
    bereits das, was call_structured() als prompt_tokens/completion_tokens durchreicht."""
    usage = data.get("usage") or {}
    return usage.get("input_tokens") or 0, usage.get("output_tokens") or 0


async def _call_anthropic(
    client: httpx.AsyncClient,
    api_key: str | None,
    model: str,
    system_prompt: str,
    user_prompt: str,
    json_schema: dict,
) -> StructuredCallResult:
    if not api_key:
        raise AIProviderError("Anthropic-Aufruf ohne api_key")
    url = "https://api.anthropic.com/v1/messages"
    headers = {
        "x-api-key": api_key,
        "anthropic-version": "2023-06-01",
        "content-type": "application/json",
    }
    tool = {
        "name": _TOOL_NAME,
        "description": "Gibt die strukturiert extrahierten Belegdaten zurück.",
        "input_schema": json_schema,
    }

    resp = await client.post(
        url,
        headers=headers,
        json={
            "model": model,
            "max_tokens": 1024,
            "system": system_prompt,
            "messages": [{"role": "user", "content": user_prompt}],
            "tools": [tool],
            "tool_choice": {"type": "tool", "name": _TOOL_NAME},
        },
    )
    resp.raise_for_status()
    data = _safe_json(resp)
    prompt_tokens, completion_tokens = _anthropic_token_counts(data)
    for block in data.get("content", []):
        if block.get("type") == "tool_use":
            return StructuredCallResult(block["input"], prompt_tokens, completion_tokens)

    logger.warning("Anthropic-Antwort ohne tool_use-Block, Prompt-JSON-Fallback wird versucht")
    resp = await client.post(
        url,
        headers=headers,
        json={
            "model": model,
            "max_tokens": 1024,
            "system": system_prompt,
            "messages": [
                {"role": "user", "content": f"{user_prompt}\n\n{_fallback_instruction(json_schema)}"}
            ],
        },
    )
    resp.raise_for_status()
    data = _safe_json(resp)
    fallback_prompt_tokens, fallback_completion_tokens = _anthropic_token_counts(data)
    prompt_tokens += fallback_prompt_tokens
    completion_tokens += fallback_completion_tokens
    text_blocks = [b["text"] for b in data.get("content", []) if b.get("type") == "text"]
    parsed = _try_parse("".join(text_blocks)) if text_blocks else None
    if parsed is not None:
        return StructuredCallResult(parsed, prompt_tokens, completion_tokens)
    raise AIProviderError("Anthropic-Antwort auch im Prompt-Fallback nicht als JSON parsebar")


def _google_token_counts(data: dict) -> tuple[int, int]:
    usage = data.get("usageMetadata") or {}
    return usage.get("promptTokenCount") or 0, usage.get("candidatesTokenCount") or 0


async def _call_google(
    client: httpx.AsyncClient,
    api_key: str | None,
    model: str,
    system_prompt: str,
    user_prompt: str,
    json_schema: dict,
) -> StructuredCallResult:
    if not api_key:
        raise AIProviderError("Google-Aufruf ohne api_key")
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={api_key}"

    resp = await client.post(
        url,
        json={
            "systemInstruction": {"parts": [{"text": system_prompt}]},
            "contents": [{"role": "user", "parts": [{"text": user_prompt}]}],
            "generationConfig": {
                "responseMimeType": "application/json",
                "responseSchema": json_schema,
            },
        },
    )
    resp.raise_for_status()
    data = _safe_json(resp)
    prompt_tokens, completion_tokens = _google_token_counts(data)
    parsed = _try_parse(data["candidates"][0]["content"]["parts"][0]["text"])
    if parsed is not None:
        return StructuredCallResult(parsed, prompt_tokens, completion_tokens)

    logger.warning("Gemini-Antwort nicht schema-valide, Prompt-JSON-Fallback wird versucht")
    resp = await client.post(
        url,
        json={
            "systemInstruction": {"parts": [{"text": system_prompt}]},
            "contents": [
                {
                    "role": "user",
                    "parts": [{"text": f"{user_prompt}\n\n{_fallback_instruction(json_schema)}"}],
                }
            ],
        },
    )
    resp.raise_for_status()
    data = _safe_json(resp)
    fallback_prompt_tokens, fallback_completion_tokens = _google_token_counts(data)
    prompt_tokens += fallback_prompt_tokens
    completion_tokens += fallback_completion_tokens
    parsed = _try_parse(data["candidates"][0]["content"]["parts"][0]["text"])
    if parsed is not None:
        return StructuredCallResult(parsed, prompt_tokens, completion_tokens)
    raise AIProviderError("Gemini-Antwort auch im Prompt-Fallback nicht als JSON parsebar")
