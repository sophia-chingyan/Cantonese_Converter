"""
Central configuration, loaded from environment variables.

Every setting the app needs lives here so nothing reaches os.environ
directly from elsewhere in the codebase. See the System Specification
Document section 8 for what each variable means and section 9 for the
locked defaults (D1-D8).
"""
import os


def _int_env(name: str, default: int) -> int:
    raw = os.environ.get(name)
    if raw is None or raw == "":
        return default
    try:
        return int(raw)
    except ValueError:
        return default


class Config:
    # --- Auth (Google OAuth, single allowed user) ---
    GOOGLE_CLIENT_ID = os.environ.get("GOOGLE_CLIENT_ID", "")
    GOOGLE_CLIENT_SECRET = os.environ.get("GOOGLE_CLIENT_SECRET", "")
    ALLOWED_EMAIL = os.environ.get("ALLOWED_EMAIL", "")

    # --- Flask ---
    FLASK_SECRET_KEY = os.environ.get("FLASK_SECRET_KEY", "")

    # --- Translation providers (R10 / D1) ---
    # Poe: OpenAI-compatible endpoint, billed against the user's Poe subscription.
    POE_API_KEY = os.environ.get("POE_API_KEY", "")
    POE_BASE_URL = os.environ.get("POE_BASE_URL", "https://api.poe.com/v1")
    POE_MODEL = os.environ.get("POE_MODEL", "GPT-5.6-Luna")

    # Gemini: direct Google AI Studio key.
    GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "")
    GEMINI_BASE_URL = os.environ.get(
        "GEMINI_BASE_URL", "https://generativelanguage.googleapis.com/v1beta"
    )
    GEMINI_MODEL = os.environ.get("GEMINI_MODEL", "gemini-3.1-flash-lite")

    # D1: default provider selected when a session has not chosen one yet.
    DEFAULT_PROVIDER = os.environ.get("DEFAULT_PROVIDER", "poe")

    # --- File handling ---
    OUTPUT_DIR = os.environ.get("OUTPUT_DIR", "storage/outputs")
    MAX_UPLOAD_MB = _int_env("MAX_UPLOAD_MB", 10)

    # D2: chunk target size in characters.
    CHUNK_SIZE_CHARS = _int_env("CHUNK_SIZE_CHARS", 1500)

    # D6: how many saved files to keep before pruning the oldest.
    FILE_RETENTION_COUNT = _int_env("FILE_RETENTION_COUNT", 50)

    # D3: how much of the previous chunk's translated output to carry
    # forward as a style anchor.
    CONTEXT_CARRYOVER_CHARS = _int_env("CONTEXT_CARRYOVER_CHARS", 200)

    # Networking
    PORT = _int_env("PORT", 8080)

    @classmethod
    def validate(cls):
        """Fail loudly and early on missing required config, rather than
        surfacing a confusing error mid-request later."""
        missing = []
        for name in ("GOOGLE_CLIENT_ID", "GOOGLE_CLIENT_SECRET", "ALLOWED_EMAIL", "FLASK_SECRET_KEY"):
            if not getattr(cls, name):
                missing.append(name)
        if missing:
            raise RuntimeError(
                "Missing required environment variables: " + ", ".join(missing)
            )
