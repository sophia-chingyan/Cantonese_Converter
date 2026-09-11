import os

from flask import Flask, jsonify
from werkzeug.middleware.proxy_fix import ProxyFix

from config import Config
from auth import init_oauth
from web.routes import bp as web_bp


def _ensure_output_dir(path: str) -> None:
    """Create the saved-files directory up front, and fail with a message
    that names the actual problem. On Railway this is usually a volume
    whose mount path doesn't match OUTPUT_DIR, which would otherwise only
    surface as a 500 the first time someone clicks Save."""
    try:
        os.makedirs(path, exist_ok=True)
    except OSError as exc:
        raise RuntimeError(
            f"Cannot create OUTPUT_DIR {path!r}: {exc}. On Railway, either "
            "attach a volume and point OUTPUT_DIR inside its mount path, or "
            "leave OUTPUT_DIR unset to use the container filesystem."
        ) from exc

    if not os.access(path, os.W_OK):
        raise RuntimeError(
            f"OUTPUT_DIR {path!r} is not writable by this process."
        )


def create_app() -> Flask:
    Config.validate()

    # There's no top-level static/ directory - all static assets belong
    # to the web blueprint (web/static/). Flask's own default static
    # route would otherwise register at the same /static/<path:filename>
    # URL as the blueprint's and win (it's added first), 404ing every
    # asset the blueprint actually serves - including translate.js,
    # which silently breaks the translate page's JS-driven submit flow.
    app = Flask(__name__, static_folder=None)
    # Railway terminates TLS at its edge proxy and forwards plain HTTP to
    # this container, so without this Flask sees every request as http
    # and url_for(..., _external=True) (used for the OAuth redirect_uri)
    # builds an http:// URL that won't match the https:// URI registered
    # with Google, causing redirect_uri_mismatch.
    app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1, x_prefix=1)
    app.config.from_object(Config)
    # Flask's session signing specifically looks for SECRET_KEY.
    app.config["SECRET_KEY"] = Config.FLASK_SECRET_KEY
    app.config["MAX_CONTENT_LENGTH"] = Config.MAX_UPLOAD_MB * 1024 * 1024

    _ensure_output_dir(Config.OUTPUT_DIR)

    init_oauth(app)
    app.register_blueprint(web_bp)

    @app.errorhandler(413)
    def too_large(_exc):
        # Spec section 7: uploads exceeding the size limit are rejected
        # with a clear message.
        return jsonify({
            "error": f"File too large. Max upload size is {Config.MAX_UPLOAD_MB} MB."
        }), 413

    return app


app = create_app()

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=Config.PORT, debug=False)
