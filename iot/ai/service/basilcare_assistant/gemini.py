"""Explicit external Gemini provider. No tools, redirects, retries or secret logging."""
import json
import os
from pathlib import Path
import re
from urllib.error import HTTPError, URLError
from urllib.request import Request, build_opener, ProxyHandler

from .selectors import ModelUnavailable, ModelOutputError, NoRedirect, SYSTEM_PROMPT

DEFAULT_MODEL = "gemini-3.1-flash-lite"
API_ROOT = "https://generativelanguage.googleapis.com/v1beta/models/"
OPTIONS = {"temperature": 0, "maxOutputTokens": 256}


def load_api_key(env_file=None):
    """Read only this literal key. Never source shell code or expand other .env values."""
    key = os.environ.get("GEMINI_API_KEY", "").strip()
    if not key and env_file:
        for line in Path(env_file).read_text(encoding="utf-8").splitlines():
            name, separator, value = line.partition("=")
            if separator and name.strip() == "GEMINI_API_KEY":
                key = value.strip()
                if len(key) >= 2 and key[0] == key[-1] and key[0] in "\"'":
                    key = key[1:-1]
    if not key or len(key) > 512 or any(c.isspace() or ord(c) < 32 for c in key):
        raise ValueError("set GEMINI_API_KEY or pass --env-file with a nonempty literal GEMINI_API_KEY")
    return key


def request_gemini(model, body, api_key, timeout):
    # Fixed HTTPS destination; key is a header, never a URL/query parameter.
    request = Request(API_ROOT + model + ":generateContent", data=json.dumps(body).encode(),
                      headers={"Content-Type": "application/json", "x-goog-api-key": api_key})
    try:
        with build_opener(ProxyHandler({}), NoRedirect()).open(request, timeout=timeout) as response:
            raw = response.read(262145)
            if len(raw) > 262144:
                raise ModelOutputError("Gemini response exceeds the size limit")
            try:
                return json.loads(raw)
            except ValueError:
                raise ModelOutputError("Gemini returned invalid JSON") from None
    except HTTPError as error:
        # Do not read/print error bodies, which can echo user input or credentials.
        code = {400: "invalid_request", 401: "invalid_key", 403: "access_denied",
                402: "quota_exhausted", 404: "model_not_found", 429: "quota_exhausted",
                500: "provider_unavailable", 502: "provider_unavailable",
                503: "provider_unavailable", 504: "provider_unavailable"}.get(error.code, "unavailable")
        error.close()
        raise ModelUnavailable("Gemini request failed", code=code) from None
    except (URLError, TimeoutError, OSError):
        raise ModelUnavailable("Gemini connection failed", code="connection_failed") from None


class GeminiSelector:
    mode = "gemini"

    def __init__(self, api_key, model=DEFAULT_MODEL, timeout=60, transport=request_gemini):
        if not isinstance(model, str) or not re.fullmatch(r"gemini-[a-z0-9][a-z0-9.-]{0,99}", model):
            raise ValueError("choose a Gemini model ID without URL, slash or credentials")
        if not isinstance(api_key, str) or not api_key or len(api_key) > 512 or any(c.isspace() or ord(c) < 32 for c in api_key):
            raise ValueError("GEMINI_API_KEY must be a nonempty literal without whitespace")
        if not 1 <= timeout <= 120:
            raise ValueError("timeout must be between 1 and 120 seconds")
        self.model, self.timeout = model, timeout
        self._api_key, self.transport = api_key, transport
        self.last_metadata = {}

    def select(self, question, passages):
        if not passages or any(p.get("scope") != "garden" for p in passages):
            raise ValueError("Gemini accepts public garden passages only")
        self.last_metadata = {"generation_requested": True, "options": OPTIONS.copy()}
        schema = {"type": "object", "properties": {"passage_ids": {
            "type": "array", "items": {"type": "string", "enum": [p["id"] for p in passages]},
            "maxItems": 2}}, "required": ["passage_ids"]}
        body = {"systemInstruction": {"parts": [{"text": SYSTEM_PROMPT}]},
                "contents": [{"role": "user", "parts": [{"text": json.dumps({
                    "question": question, "passages": [
                        {k: p[k] for k in ("id", "title", "scope", "text")} for p in passages]})}]}],
                "generationConfig": {**OPTIONS, "responseMimeType": "application/json", "responseSchema": schema}}
        response = self.transport(self.model, body, self._api_key, self.timeout)
        if not isinstance(response, dict):
            raise ModelOutputError("invalid Gemini response")
        version = response.get("modelVersion")
        if not isinstance(version, str) or not re.fullmatch(r"[A-Za-z0-9._-]{1,150}", version):
            raise ModelOutputError("Gemini response needs an identifiable model version")
        self.last_metadata["resolved_model"] = version
        usage = response.get("usageMetadata", {})
        if isinstance(usage, dict):
            for field in ("promptTokenCount", "candidatesTokenCount", "totalTokenCount", "thoughtsTokenCount"):
                if type(usage.get(field)) is int and usage[field] >= 0:
                    self.last_metadata[field] = usage[field]
        candidates = response.get("candidates")
        if (not isinstance(candidates, list) or len(candidates) != 1
                or not isinstance(candidates[0], dict) or candidates[0].get("finishReason") != "STOP"):
            raise ModelOutputError("blocked or incomplete Gemini response")
        content = candidates[0].get("content")
        parts = content.get("parts") if isinstance(content, dict) else None
        # Text parts may carry an opaque signature. Single-turn selection discards it;
        # it is never interpreted, replayed or stored in metadata/traces.
        if (not isinstance(parts, list) or not parts or any(
                not isinstance(p, dict) or p.get("thought") or not {"text"} <= set(p) <= {"text", "thoughtSignature"}
                or not isinstance(p["text"], str)
                or ("thoughtSignature" in p and not isinstance(p["thoughtSignature"], str)) for p in parts)):
            raise ModelOutputError("Gemini must return selection text, not tools or other parts")
        try:
            return json.loads("".join(p["text"] for p in parts))
        except ValueError:
            raise ModelOutputError("Gemini did not return selection JSON") from None
