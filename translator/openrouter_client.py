import requests

from .base import TranslatorClient, TranslatorError


class OpenRouterClient(TranslatorClient):
    """OpenRouter chat completions; shared retry policy lives in base.py."""

    name = "openrouter"

    def __init__(self, api_key: str, model: str, timeout: int = 60):
        self.api_key = api_key.strip()
        self.model = model.strip()
        self.timeout = timeout

    def complete(self, prompt: str) -> str:
        for name, value in (("OPENROUTER_API_KEY", self.api_key),
                            ("OPENROUTER_MODEL", self.model)):
            if not value:
                raise TranslatorError(f"{name} is not configured.")
        try:
            response = requests.post(
                "https://openrouter.ai/api/v1/chat/completions",
                headers={"Authorization": f"Bearer {self.api_key}",
                         "Content-Type": "application/json"},
                json={"model": self.model,
                      "messages": [{"role": "user", "content": prompt}]},
                timeout=self.timeout,
            )
        except requests.RequestException as exc:
            raise TranslatorError("OpenRouter request failed or timed out.") from exc
        if response.status_code != 200:
            # Don't expose provider response bodies, keys, or source text.
            raise TranslatorError(f"OpenRouter API returned HTTP {response.status_code}.")
        try:
            data = response.json()
            if data.get("error"):
                raise TranslatorError("OpenRouter returned an API error.")
            choice = data["choices"][0]
            if choice.get("finish_reason") in ("length", "content_filter", "error"):
                raise TranslatorError("OpenRouter returned an incomplete or blocked translation.")
            content = choice["message"]["content"]
            if not isinstance(content, str) or not content.strip():
                raise TranslatorError("OpenRouter returned no translation text.")
            return content
        except (ValueError, KeyError, IndexError, TypeError, AttributeError) as exc:
            raise TranslatorError("Unexpected OpenRouter API response format.") from exc
