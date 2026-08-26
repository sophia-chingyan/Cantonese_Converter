import os

from flask import Flask, jsonify

from config import Config
from auth import init_oauth
from web.routes import bp as web_bp


def create_app() -> Flask:
    Config.validate()

    app = Flask(__name__)
    app.config.from_object(Config)
    # Flask's session signing specifically looks for SECRET_KEY.
    app.config["SECRET_KEY"] = Config.FLASK_SECRET_KEY
    app.config["MAX_CONTENT_LENGTH"] = Config.MAX_UPLOAD_MB * 1024 * 1024

    os.makedirs(Config.OUTPUT_DIR, exist_ok=True)

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
