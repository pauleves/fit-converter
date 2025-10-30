import argparse
import logging
import os
from datetime import datetime

from flask import Flask, Response, jsonify, render_template_string, request, send_file
from werkzeug.exceptions import HTTPException
from werkzeug.utils import secure_filename

from fit_converter import paths
from fit_converter.cfg import effective_config
from fit_converter.logging_setup import configure_logging

from .converter import ConversionError, fit_to_csv

# --- Bootstrap: config → logging → log effective config ---
_cfg = effective_config(log=False)
_log_cfg = _cfg["logging"]
configure_logging(**_log_cfg)
config = effective_config(log=True)

logger = logging.getLogger(__name__)
app = Flask(__name__)


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
def upload_form():
    checked_attr = "checked" if config.get("transform", True) else ""
    return render_template_string(
        """
        <h1>Upload a FIT file</h1>
        <form action="/upload" method="post" enctype="multipart/form-data">
            <input type="file" name="fitfile" accept=".fit" required>
            <label style="display:block;margin-top:8px">
                <input type="checkbox" name="transform" {{ checked }}>
                Transform for readability (pace mm:ss, SPM, degrees)
            </label>
            <button type="submit" style="margin-top:8px">Upload & Convert</button>
        </form>
        """,
        checked=checked_attr,
    )


# -------------------------
# Upload/convert
# -------------------------
@app.post("/upload")
def upload_file():
    if "fitfile" not in request.files:
        return jsonify(error="No file part named 'fitfile'."), 400
    uploaded = request.files["fitfile"]
    if not uploaded or uploaded.filename == "":
        return jsonify(error="No file selected."), 400

    filename = secure_filename(uploaded.filename)
    inbox_path = paths.INBOX / filename
    out_path = paths.OUTBOX / (filename + ".csv")

    try:
        uploaded.save(inbox_path)
    except Exception:
        logger.exception("Failed to save uploaded file: %s", inbox_path)
        return jsonify(error="Could not save uploaded file."), 500

    try:
        do_transform = "transform" in request.form
        fit_to_csv(inbox_path, out_path, transform=do_transform)
    except NotImplementedError:
        return "<p>Conversion not yet implemented.</p>", 501
    except Exception:
        logger.exception("Conversion failed for: %s", inbox_path)
        return jsonify(error="Conversion failed."), 500

    try:
        return send_file(out_path, as_attachment=True, download_name=out_path.name)
    except Exception:
        logger.exception("Failed to send converted file: %s", out_path)
        return jsonify(error="Could not return converted file."), 500


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
