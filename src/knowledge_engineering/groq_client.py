from __future__ import annotations

import json
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


class GroqError(RuntimeError):
    pass


class GroqClient:
    """Small, dependency-free client for Groq's OpenAI-compatible chat endpoint."""

    def __init__(self, api_key: str, model: str, timeout_seconds: int = 60):
        if not api_key:
            raise GroqError("Configure KE_GROQ_API_KEY to generate knowledge packs.")
        self.api_key = api_key
        self.model = model
        self.timeout_seconds = timeout_seconds

    def complete_json(self, *, system: str, user: str) -> dict:
        payload = {
            "model": self.model,
            "temperature": 0,
            "response_format": {"type": "json_object"},
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
        }
        request = Request(
            "https://api.groq.com/openai/v1/chat/completions",
            data=json.dumps(payload).encode("utf-8"),
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            },
            method="POST",
        )
        try:
            with urlopen(request, timeout=self.timeout_seconds) as response:
                body = json.loads(response.read().decode("utf-8"))
        except HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")
            raise GroqError(f"Groq returned HTTP {exc.code}: {detail}") from exc
        except URLError as exc:
            raise GroqError(f"Could not reach Groq: {exc.reason}") from exc

        try:
            content = body["choices"][0]["message"]["content"]
            return json.loads(content)
        except (KeyError, IndexError, TypeError, json.JSONDecodeError) as exc:
            raise GroqError("Groq did not return a valid JSON object.") from exc
