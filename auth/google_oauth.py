"""
Google OAuth login restricted to one allowed email address (spec
section 2). Uses Authlib, which handles the OAuth/OIDC handshake
against Google's well-known configuration.
"""
from functools import wraps

from authlib.integrations.flask_client import OAuth
from flask import redirect, session, url_for, abort

oauth = OAuth()


def init_oauth(app):
    oauth.init_app(app)
    oauth.register(
        name="google",
        client_id=app.config["GOOGLE_CLIENT_ID"],
        client_secret=app.config["GOOGLE_CLIENT_SECRET"],
        server_metadata_url="https://accounts.google.com/.well-known/openid-configuration",
        client_kwargs={"scope": "openid email profile"},
    )
    return oauth


def login_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if not session.get("user_email"):
            return redirect(url_for("web.login"))
        return view(*args, **kwargs)

    return wrapped


def complete_login(user_info: dict, allowed_email: str) -> bool:
    """Called after the OAuth callback with the userinfo claims Google
    returned. Returns True and populates the session if the email
    matches the single allowed user; otherwise leaves the session
    untouched and returns False."""
    email = (user_info or {}).get("email", "")
    email_verified = (user_info or {}).get("email_verified", False)

    if not email_verified or email.lower() != allowed_email.lower():
        return False

    session["user_email"] = email
    session["user_name"] = user_info.get("name", email)
    return True


def logout():
    session.pop("user_email", None)
    session.pop("user_name", None)
    session.pop("provider", None)
