from .base import TranslatorClient
from .poe_client import PoeClient
from .gemini_client import GeminiClient

PROVIDERS = ("poe", "gemini")  # D8's Custom option is deferred, not in v1.0


def get_client(provider: str, config) -> TranslatorClient:
    """config is Flask's dict-style app.config (or any dict-like
    object) with the keys defined in config.py."""
    if provider == "poe":
        return PoeClient(
            api_key=config["POE_API_KEY"],
            base_url=config["POE_BASE_URL"],
            model=config["POE_MODEL"],
        )
    if provider == "gemini":
        return GeminiClient(
            api_key=config["GEMINI_API_KEY"],
            base_url=config["GEMINI_BASE_URL"],
            model=config["GEMINI_MODEL"],
        )
    raise ValueError(f"Unknown provider '{provider}'. Expected one of {PROVIDERS}.")
