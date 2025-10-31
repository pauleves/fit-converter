import argparse
import logging
import os
from datetime import datetime
from pathlib import Path

from flask import (
    Flask,
    Response,
    flash,
    jsonify,
    redirect,
    render_template,
    request,
    send_file,
    url_for,
)
from werkzeug.exceptions import HTTPException
from werkzeug.utils import secure_filename

from fit_converter import paths
from fit_converter.cfg import effective_config
from fit_converter.logging_setup import configure_logging

from .converter import ConversionError, convert_with_report

# --- Bootstrap: config → logging → log effective config ---
_cfg = effective_config(log=False)
_log_cfg = _cfg["logging"]
configure_logging(**_log_cfg)
config = effective_config(log=True)

logger = logging.getLogger(__name__)
paths.warn_if_running_inside_src(logger)
app = Flask(__name__)
app.secret_key = (
    os.environ.get("FLASK_SECRET_KEY")
    or (config.get("flask") or {}).get("secret_key")
    or "dev-not-secret"
)


# -------------------------
# Error handlers
# -------------------------
@app.errorhandler(ConversionError)
def handle_conversion_error(e: ConversionError):
    # Expected, user-facing error (bad/corrupted FIT, etc.)
    logger.warning("ConversionError: %s", e)
    return jsonify(error=str(e)), 400


@app.errorhandler(HTTPException)
def handle_http_exc(e: HTTPException):
    level = logging.WARNING if 400 <= e.code < 500 else logging.ERROR
    logger.log(level, "HTTP %s %s: %s", e.code, e.name, e.description)
    return jsonify(error=e.description), e.code


@app.errorhandler(Exception)
def handle_unexpected(e: Exception):
    app.logger.exception("Unhandled error during request")
    return jsonify(error="Sorry, something went wrong while converting your file."), 500


@app.get("/healthz")
def healthz():
    return {"status": "ok"}, 200


# -------------------------
# UI
# -------------------------


@app.get("/")
def index():
    return render_template(
        "upload.html", transform_default=config["converter"]["transform_default"]
    )


# -------------------------
# Upload/convert
# -------------------------
@app.post("/upload")
def upload_file():
    if "fitfile" not in request.files:
        flash("❌ No file part named 'fitfile'.", "error")
        return redirect(url_for("index"))
    uploaded = request.files["fitfile"]
    if not uploaded or uploaded.filename == "":
        flash("❌ No file selected.", "error")
        return redirect(url_for("index"))

    safe_name = secure_filename(uploaded.filename)
    inbox_path = paths.INBOX / safe_name
    out_name = Path(safe_name).with_suffix(".csv").name
    out_path = paths.OUTBOX / out_name

    try:
        uploaded.save(inbox_path)
    except Exception:
        logger.exception("Failed to save uploaded file: %s", inbox_path)
        flash("❌ Could not save uploaded file.", "error")
        return redirect(url_for("index"))

    try:
        do_transform = "transform" in request.form
        report = convert_with_report(
            inbox_path,
            out_path,
            transform=do_transform,
            logger=logger,
            quiet_logs=True,
        )
        if report.ok:
            flash(
                f"✅ Converted {inbox_path.name} → {out_path.name} "
                f"({report.rows or '?'} rows, {report.seconds:.2f}s) — "
                f"<a href='{url_for('download_csv', filename=out_name)}'>Download CSV</a>",
                "success",
            )
        else:
            flash(f"❌ {inbox_path.name} — {report.message}", "error")
    except NotImplementedError:
        flash("⚠️ Conversion not yet implemented.", "error")
    except Exception:
        logger.exception("Conversion failed for: %s", inbox_path)
        flash("❌ Conversion failed.", "error")

    return redirect(url_for("index"))


@app.get("/download/<path:filename>")
def download_csv(filename):
    out_path = paths.OUTBOX / filename
    if not out_path.exists():
        flash("❌ File not found.", "error")
        return redirect(url_for("index"))
    return send_file(out_path, as_attachment=True, download_name=out_path.name)


@app.route("/favicon.ico")
def favicon_empty():
    return Response(status=204)


# -------------------------
# CLI defaults (env-based)
# -------------------------
def _default_host():
    return os.getenv("FLASK_HOST", "127.0.0.1")


def _default_port():
    return int(os.getenv("FLASK_PORT", "5000"))


def _default_debug():
    return bool(int(os.getenv("FLASK_DEBUG", "0")))


# -------------------------
# Entrypoint
# -------------------------
def main() -> None:
    parser = build_parser()
    args = parser.parse_args()

    logger.info(
        "Starting Flask app on %s:%s (debug=%s)", args.host, args.port, args.debug
    )
    _banner_app(config, args.host, args.port, args.debug, logger)
    app.run(host=args.host, port=args.port, debug=args.debug)


def build_parser() -> argparse.ArgumentParser:
    # Safe fallback for optional helper
    _default_debug_fn = globals().get("_default_debug")
    debug_default = _default_debug_fn() if callable(_default_debug_fn) else False

    parser = argparse.ArgumentParser(
        prog="fit-converter",
        description="Run the FIT→CSV web UI",
        formatter_class=argparse.RawTextHelpFormatter,
        epilog=(
            "Examples:\n"
            "  # Start on defaults\n"
            '  fit-converter\n\n'
            "  # Bind to all interfaces on port 8080\n"
            "  fit-converter --host 0.0.0.0 --port 8080\n\n"
            "  # Enable Flask debug/reloader\n"
            "  fit-converter --debug\n"
        ),
    )
    parser.add_argument("--host", default=_default_host(), help="Bind host")
    parser.add_argument("--port", type=int, default=_default_port(), help="Bind port")
    parser.add_argument(
        "--debug",
        action=argparse.BooleanOptionalAction,
        default=debug_default,
        help="Enable Flask debug / reloader",
    )
    return parser


def _banner_app(cfg, host, port, debug, logger):
    """Log a concise startup summary for the web UI."""
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    logger.info("┌─ FIT→CSV — Web UI")
    logger.info("│ time: %s", now)
    logger.info("│ host: %s", host)
    logger.info("│ port: %s", port)
    logger.info("│ debug: %s", debug)
    cfg_path = cfg.get("config_path") if isinstance(cfg, dict) else None
    if cfg_path:
        logger.info("│ config: %s", cfg_path)
    logger.info("└────────────────────────")


if __name__ == "__main__":
    main()
