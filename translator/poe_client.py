import requests

from .base import TranslatorClient, TranslatorError


class PoeClient(TranslatorClient):
    """D1 locked default: Poe's OpenAI-compatible API, billed against
    the user's existing Poe subscription points."""

    name = "poe"

    def __init__(self, api_key: str, base_url: str, model: str, timeout: int = 60):
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.timeout = timeout

    def complete(self, prompt: str) -> str:
        if not self.api_key:
            raise TranslatorError("POE_API_KEY is not configured.")

        url = f"{self.base_url}/chat/completions"
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        payload = {
            "model": self.model,
            "messages": [{"role": "user", "content": prompt}],
        }

        response = requests.post(url, headers=headers, json=payload, timeout=self.timeout)
        if response.status_code != 200:
            raise TranslatorError(
                f"Poe API returned HTTP {response.status_code}: {response.text[:300]}"
            )

        data = response.json()
        try:
            return data["choices"][0]["message"]["content"]
        except (KeyError, IndexError, TypeError) as exc:
            raise TranslatorError(f"Unexpected Poe API response shape: {data}") from exc
