"""
Common interface every translation provider implements.

Per spec 5.2, each provider (Poe, Gemini, and eventually the deferred
Custom option from D8) is one small client behind this same shape.
Nothing outside translator/ needs to know which provider is active.
"""
from __future__ import annotations

import time
from typing import Callable, TypeVar

T = TypeVar("T")


class TranslatorError(Exception):
    """Raised when a provider call fails after retries, or returns
    something unusable (empty response, malformed shape)."""


class TranslatorClient:
    #: short identifier, e.g. "poe" or "gemini" - used in error messages
    #: and to tag failed chunks in the output.
    name = "base"

    def complete(self, prompt: str) -> str:
        """Send a single fully-composed prompt, return the raw text
        response. Subclasses implement this; retry logic wraps it in
        translate_with_retries() below, not here."""
        raise NotImplementedError


def translate_with_retries(
    client: TranslatorClient,
    prompt: str,
    attempts: int = 3,
    base_delay_seconds: float = 1.5,
) -> str:
    """Spec section 7: a failed call is retried up to 3 times with
    backoff. Raises TranslatorError if every attempt fails."""
    last_error: Exception | None = None
    for attempt in range(1, attempts + 1):
        try:
            result = client.complete(prompt)
            if not result or not result.strip():
                raise TranslatorError(f"{client.name} returned an empty response")
            return result.strip()
        except Exception as exc:  # noqa: BLE001 - deliberately broad, we retry any failure
            last_error = exc
            if attempt < attempts:
                time.sleep(base_delay_seconds * attempt)
    raise TranslatorError(
        f"{client.name} failed after {attempts} attempts: {last_error}"
    ) from last_error
