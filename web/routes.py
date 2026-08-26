import os
import time

from flask import (
    Blueprint,
    current_app,
    jsonify,
    redirect,
    render_template,
    request,
    send_from_directory,
    session,
    url_for,
)
from werkzeug.utils import secure_filename

from auth import complete_login, login_required, logout, oauth
from extractors import ExtractionError, extract_pasted_text, extract_upload
from jobs import registry, start_job
from translator import PROVIDERS
from writers import output_extension_for

bp = Blueprint("web", __name__, template_folder="templates", static_folder="static")


# --------------------------------------------------------------------------
# Auth
# --------------------------------------------------------------------------

@bp.route("/login")
def login():
    if session.get("user_email"):
        return redirect(url_for("web.translate_page"))
    return render_template("login.html")


@bp.route("/auth/google")
def auth_google():
    redirect_uri = url_for("web.auth_callback", _external=True)
    return oauth.google.authorize_redirect(redirect_uri)


@bp.route("/auth/callback")
def auth_callback():
    token = oauth.google.authorize_access_token()
    user_info = token.get("userinfo") or oauth.google.userinfo(token=token)

    ok = complete_login(user_info, current_app.config["ALLOWED_EMAIL"])
    if not ok:
        return render_template(
            "login.html",
            error="This Google account isn't authorized for this app.",
        ), 403

    return redirect(url_for("web.translate_page"))


@bp.route("/logout")
def logout_route():
    logout()
    return redirect(url_for("web.login"))


@bp.route("/")
def index():
    if session.get("user_email"):
        return redirect(url_for("web.translate_page"))
    return redirect(url_for("web.login"))


@bp.route("/healthz")
def healthz():
    return "ok", 200


# --------------------------------------------------------------------------
# Translate page
# --------------------------------------------------------------------------

@bp.route("/translate")
@login_required
def translate_page():
    provider = session.get("provider", current_app.config["DEFAULT_PROVIDER"])
    return render_template("translate.html", provider=provider, providers=PROVIDERS)


@bp.route("/api/translate", methods=["POST"])
@login_required
def api_translate():
    provider = request.form.get("provider", current_app.config["DEFAULT_PROVIDER"])
    if provider not in PROVIDERS:
        return jsonify({"error": f"Unknown provider '{provider}'."}), 400
    session["provider"] = provider

    uploaded = request.files.get("file")
    pasted_text = request.form.get("pasted_text", "").strip()

    try:
        if uploaded and uploaded.filename:
            raw = uploaded.read()
            doc = extract_upload(raw, uploaded.filename)
        elif pasted_text:
            doc = extract_pasted_text(pasted_text)
        else:
            return jsonify({"error": "Paste some text or choose a file first."}), 400
    except ExtractionError as exc:
        return jsonify({"error": str(exc)}), 400

    if doc.is_empty():
        return jsonify({"error": "No text found to translate."}), 400

    job_id = start_job(doc, provider, current_app.config)
    return jsonify({"job_id": job_id})


@bp.route("/api/jobs/<job_id>")
@login_required
def api_job_status(job_id):
    job = registry.get_job(job_id)
    if job is None:
        return jsonify({
            "error": "Job not found. The server may have restarted - please translate again."
        }), 404
    return jsonify(job)


@bp.route("/api/save", methods=["POST"])
@login_required
def api_save():
    data = request.get_json(silent=True) or {}
    job_id = data.get("job_id")
    text = data.get("text", "")

    if not job_id or not text.strip():
        return jsonify({"error": "Nothing to save."}), 400

    job = registry.get_job(job_id)
    if job is None:
        return jsonify({
            "error": "This job is no longer available (server may have restarted). Please translate again before saving."
        }), 404

    output_ext = output_extension_for(job["source_ext"])
    base_name = _derive_base_name(job.get("source_filename"))
    output_dir = current_app.config["OUTPUT_DIR"]
    filename = _unique_filename(output_dir, base_name, output_ext)

    os.makedirs(output_dir, exist_ok=True)
    with open(os.path.join(output_dir, filename), "wb") as f:
        f.write(text.encode("utf-8"))

    _apply_retention(output_dir, current_app.config["FILE_RETENTION_COUNT"])

    return jsonify({"filename": filename})


def _derive_base_name(source_filename):
    if source_filename:
        stem = os.path.splitext(source_filename)[0]
        safe = secure_filename(stem) or "translation"
        return safe
    return "cantonese-translation-" + time.strftime("%Y%m%d-%H%M%S")


def _unique_filename(output_dir, base_name, ext):
    candidate = f"{base_name}.{ext}"
    if not os.path.exists(os.path.join(output_dir, candidate)):
        return candidate
    suffix = time.strftime("%Y%m%d-%H%M%S")
    return f"{base_name}-{suffix}.{ext}"


def _apply_retention(output_dir, keep_count):
    """D6: keep the N most recent files, delete the rest."""
    try:
        entries = [
            os.path.join(output_dir, name)
            for name in os.listdir(output_dir)
            if os.path.isfile(os.path.join(output_dir, name))
        ]
    except FileNotFoundError:
        return

    entries.sort(key=os.path.getmtime, reverse=True)
    for stale_path in entries[keep_count:]:
        try:
            os.remove(stale_path)
        except OSError:
            pass


# --------------------------------------------------------------------------
# Files page
# --------------------------------------------------------------------------

@bp.route("/files")
@login_required
def files_page():
    output_dir = current_app.config["OUTPUT_DIR"]
    files = []
    if os.path.isdir(output_dir):
        for name in os.listdir(output_dir):
            path = os.path.join(output_dir, name)
            if os.path.isfile(path):
                stat = os.stat(path)
                files.append({
                    "name": name,
                    "size": stat.st_size,
                    "mtime": stat.st_mtime,
                })
    files.sort(key=lambda f: f["mtime"], reverse=True)
    return render_template("files.html", files=files)


@bp.route("/files/download/<path:filename>")
@login_required
def download_file(filename):
    safe_name = secure_filename(filename)
    output_dir = current_app.config["OUTPUT_DIR"]
    if not safe_name or not os.path.isfile(os.path.join(output_dir, safe_name)):
        return "File not found.", 404
    return send_from_directory(output_dir, safe_name, as_attachment=True)


@bp.route("/files/delete/<path:filename>", methods=["POST"])
@login_required
def delete_file(filename):
    safe_name = secure_filename(filename)
    output_dir = current_app.config["OUTPUT_DIR"]
    path = os.path.join(output_dir, safe_name)
    if safe_name and os.path.isfile(path):
        os.remove(path)
    return redirect(url_for("web.files_page"))
