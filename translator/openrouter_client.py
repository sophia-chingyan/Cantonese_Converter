import requests

from .base import TranslatorClient, TranslatorError

OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"


class OpenRouterClient(TranslatorClient):
    """OpenRouter chat completions; shared retry policy lives in base.py."""

    name = "openrouter"

    # Some OpenRouter models (especially reasoning ones) take well over a
    # minute on a 1,500-character chunk, so allow more than Poe/Gemini.
    def __init__(self, api_key: str, model: str, timeout: int = 120):
        self.api_key = (api_key or "").strip()
        self.model = (model or "").strip()
        self.timeout = timeout

    def complete(self, prompt: str) -> str:
        for name, value in (("OPENROUTER_API_KEY", self.api_key),
                            ("OPENROUTER_MODEL", self.model)):
            if not value:
                raise TranslatorError(f"{name} is not configured.")
        try:
            response = requests.post(
                OPENROUTER_URL,
                headers={"Authorization": f"Bearer {self.api_key}",
                         "Content-Type": "application/json",
                         # Optional attribution headers OpenRouter shows
                         # in its dashboard; harmless if unused.
                         "X-Title": "Cantonese Converter"},
                json={"model": self.model,
                      "messages": [{"role": "user", "content": prompt}]},
                timeout=self.timeout,
            )
        except requests.RequestException as exc:
            raise TranslatorError("OpenRouter request failed or timed out.") from exc

        if response.status_code != 200:
            # Only OpenRouter's own short error message is surfaced (e.g.
            # "not a valid model ID") - never the key or the source text.
            raise TranslatorError(
                f"OpenRouter API returned HTTP {response.status_code}"
                f"{_error_detail(response)}."
            )
        try:
            data = response.json()
            if data.get("error"):
                raise TranslatorError(f"OpenRouter returned an API error{_error_detail(response)}.")
            choice = data["choices"][0]
            if choice.get("finish_reason") in ("length", "content_filter", "error"):
                raise TranslatorError(
                    "OpenRouter returned an incomplete or blocked translation "
                    f"(finish_reason={choice.get('finish_reason')})."
                )
            content = choice["message"]["content"]
            if not isinstance(content, str) or not content.strip():
                raise TranslatorError("OpenRouter returned no translation text.")
            return content
        except (ValueError, KeyError, IndexError, TypeError, AttributeError) as exc:
            raise TranslatorError("Unexpected OpenRouter API response format.") from exc


def _error_detail(response) -> str:
    """': <message>' from an OpenRouter error body, or '' if there isn't one."""
    try:
        message = response.json()["error"]["message"]
    except (ValueError, KeyError, TypeError):
        return ""
    if not isinstance(message, str) or not message.strip():
        return ""
    return ": " + message.strip()[:200]
