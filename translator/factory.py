from .base import TranslatorClient
from .poe_client import PoeClient
from .gemini_client import GeminiClient
from .openrouter_client import OpenRouterClient

PROVIDERS = ("poe", "gemini", "openrouter")  # D8's Custom option is deferred, not in v1.0

PROVIDER_LABELS = {"poe": "Poe", "gemini": "Gemini", "openrouter": "OpenRouter"}

# Settings each provider can't run without. Checked before a job starts
# so a missing Railway variable is reported up front, not as every
# chunk failing in the background.
REQUIRED_SETTINGS = {
    "poe": ("POE_API_KEY", "POE_MODEL"),
    "gemini": ("GEMINI_API_KEY", "GEMINI_MODEL"),
    "openrouter": ("OPENROUTER_API_KEY", "OPENROUTER_MODEL"),
}


def missing_settings(provider: str, config) -> list:
    """Names of required settings that are empty for this provider."""
    return [
        name for name in REQUIRED_SETTINGS.get(provider, ())
        if not str(config.get(name) or "").strip()
    ]


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
    if provider == "openrouter":
        return OpenRouterClient(
            api_key=config["OPENROUTER_API_KEY"],
            model=config["OPENROUTER_MODEL"],
        )
    raise ValueError(f"Unknown provider '{provider}'. Expected one of {PROVIDERS}.")
