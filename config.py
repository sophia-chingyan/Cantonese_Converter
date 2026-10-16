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


def _bool_env(name: str, default: bool) -> bool:
    raw = os.environ.get(name)
    if raw is None or raw == "":
        return default
    return raw.strip().lower() in ("1", "true", "yes", "on")


# Railway sets this on every deploy, so it's the cheapest way to tell
# "running on Railway" from "running on a laptop" without a flag of our own.
ON_RAILWAY = bool(os.environ.get("RAILWAY_ENVIRONMENT_NAME") or os.environ.get("RAILWAY_ENVIRONMENT"))


def _default_output_dir() -> str:
    """Where saved translations go when OUTPUT_DIR isn't set explicitly.

    Railway injects RAILWAY_VOLUME_MOUNT_PATH when a persistent volume is
    attached to the service. Defaulting into it means saved files survive
    redeploys as soon as a volume exists, with no extra variable to set.
    Without a volume this falls back to the container filesystem, where
    files are lost on redeploy (README: "What's deliberately not here").
    """
    volume = os.environ.get("RAILWAY_VOLUME_MOUNT_PATH", "").strip()
    if volume:
        return os.path.join(volume, "outputs")
    return "storage/outputs"


def _default_dictionary_path() -> str:
    """Same volume logic as _default_output_dir, but deliberately outside
    OUTPUT_DIR: the Files page lists everything there and D6 retention
    would eventually delete the dictionary along with old outputs."""
    volume = os.environ.get("RAILWAY_VOLUME_MOUNT_PATH", "").strip()
    if volume:
        return os.path.join(volume, "dictionary.json")
    return "storage/dictionary.json"


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

    # OpenRouter: choose an explicit model ID from openrouter.ai/models.
    OPENROUTER_API_KEY = os.environ.get("OPENROUTER_API_KEY", "").strip()
    OPENROUTER_MODEL = os.environ.get("OPENROUTER_MODEL", "").strip()

    # D1: default provider selected when a session has not chosen one yet.
    DEFAULT_PROVIDER = os.environ.get("DEFAULT_PROVIDER", "poe").strip().lower() or "poe"

    # Session cookies: Railway terminates TLS at its edge and serves the
    # public domain over https only, so the cookie can be marked Secure
    # there. Locally the app runs on plain http, where a Secure cookie
    # would never be sent back - hence the default follows the platform.
    SESSION_COOKIE_SECURE = _bool_env("SESSION_COOKIE_SECURE", ON_RAILWAY)
    SESSION_COOKIE_HTTPONLY = True
    # Lax, not Strict: the OAuth callback arrives as a top-level
    # cross-site GET redirect from Google, and Strict would drop the
    # session cookie on exactly that request.
    SESSION_COOKIE_SAMESITE = "Lax"

    # --- File handling ---
    OUTPUT_DIR = os.environ.get("OUTPUT_DIR") or _default_output_dir()
    MAX_UPLOAD_MB = _int_env("MAX_UPLOAD_MB", 10)

    # User dictionary: source terms and the exact 粵文 to use for them.
    DICTIONARY_PATH = os.environ.get("DICTIONARY_PATH") or _default_dictionary_path()

    # Optional S3-compatible bucket (e.g. a Railway Bucket) for the
    # dictionary. When all four of endpoint/bucket/key/secret are set it
    # takes precedence over DICTIONARY_PATH, so entries survive redeploys
    # without a volume. On Railway, reference the bucket's own variables,
    # e.g. S3_BUCKET=${{MyBucket.BUCKET}}.
    S3_ENDPOINT = os.environ.get("S3_ENDPOINT", "").strip()
    S3_BUCKET = os.environ.get("S3_BUCKET", "").strip()
    S3_REGION = os.environ.get("S3_REGION", "").strip()
    S3_ACCESS_KEY_ID = os.environ.get("S3_ACCESS_KEY_ID", "").strip()
    S3_SECRET_ACCESS_KEY = os.environ.get("S3_SECRET_ACCESS_KEY", "").strip()
    # "virtual" (bucket in the hostname, what Railway Buckets use) or "path".
    S3_URL_STYLE = os.environ.get("S3_URL_STYLE", "").strip().lower() or "virtual"

    # Exposed so the Dictionary page can warn when entries would be lost
    # on the next redeploy.
    ON_RAILWAY = ON_RAILWAY
    RAILWAY_VOLUME_MOUNT_PATH = os.environ.get("RAILWAY_VOLUME_MOUNT_PATH", "").strip()

    # D2: chunk target size in characters.
    CHUNK_SIZE_CHARS = _int_env("CHUNK_SIZE_CHARS", 1500)

    # D6: how many saved files to keep before pruning the oldest.
    FILE_RETENTION_COUNT = _int_env("FILE_RETENTION_COUNT", 50)

    # D3: how much of the previous chunk's translated output to carry
    # forward as a style anchor.
    CONTEXT_CARRYOVER_CHARS = _int_env("CONTEXT_CARRYOVER_CHARS", 200)

    # Networking. Railway injects PORT into the container and routes its
    # public domain to it; 8080 is only the local fallback.
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
