import requests

from .base import TranslatorClient, TranslatorError


class GeminiClient(TranslatorClient):
    """Direct Gemini API, selectable per session alongside Poe (R10)."""

    name = "gemini"

    def __init__(self, api_key: str, base_url: str, model: str, timeout: int = 60):
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.timeout = timeout

    def complete(self, prompt: str) -> str:
        if not self.api_key:
            raise TranslatorError("GEMINI_API_KEY is not configured.")

        url = f"{self.base_url}/models/{self.model}:generateContent"
        params = {"key": self.api_key}
        payload = {
            "contents": [{"role": "user", "parts": [{"text": prompt}]}],
        }

        response = requests.post(url, params=params, json=payload, timeout=self.timeout)
        if response.status_code != 200:
            raise TranslatorError(
                f"Gemini API returned HTTP {response.status_code}: {response.text[:300]}"
            )

        data = response.json()
        try:
            candidate = data["candidates"][0]
            parts = candidate["content"]["parts"]
            return "".join(p.get("text", "") for p in parts)
        except (KeyError, IndexError, TypeError) as exc:
            # A candidate can also be blocked by safety filters, in which
            # case "content" is absent entirely - surface that clearly.
            finish_reason = None
            try:
                finish_reason = data["candidates"][0].get("finishReason")
            except Exception:  # noqa: BLE001
                pass
            raise TranslatorError(
                f"Unexpected Gemini API response shape (finishReason={finish_reason}): {data}"
            ) from exc
