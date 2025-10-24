import argparse
import logging
import os

from flask import Flask, Response, jsonify, render_template_string, request, send_file
from werkzeug.exceptions import HTTPException

from fit_converter import cfg, paths

from .converter import fit_to_csv

logger = logging.getLogger(__name__)
app = Flask(__name__)


@app.errorhandler(HTTPException)
def handle_http_exc(e: HTTPException):
    # 4xx are client issues; 5xx are server issues
    level = logging.WARNING if 400 <= e.code < 500 else logging.ERROR
    logger.log(level, "HTTP %s %s: %s", e.code, e.name, e.description)
    return jsonify(error=e.description), e.code


@app.errorhandler(Exception)
def handle_unexpected(e):
    app.logger.exception("Unhandled error during request")
    return jsonify(error="Sorry, something went wrong while converting your file."), 500


@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/healthz")
def healthz():
    return {"status": "ok"}, 200


@app.get("/")
def upload_form():
    return render_template_string(
        """
        <h1>Upload a FIT file</h1>
        <form action="/upload" method="post" enctype="multipart/form-data">
            <input type="file" name="fitfile" accept=".fit" required>
            <label style="display:block;margin-top:8px">
            <input type="checkbox" name="transform" checked>
            Transform for readability (pace mm:ss, SPM, degrees)
            </label>
            <button type="submit" style="margin-top:8px">Upload & Convert</button>
        </form>
    """
    )


@app.post("/upload")
def upload_file():
    uploaded = request.files["fitfile"]
    inbox_path = paths["inbox"] / uploaded.filename
    out_path = paths["outbox"] / (uploaded.filename + ".csv")

    uploaded.save(inbox_path)

    try:
        do_transform = "transform" in request.form
        fit_to_csv(inbox_path, out_path, transform=do_transform)
    except NotImplementedError:
        return "<p>Conversion not yet implemented.</p>", 501

    return send_file(out_path, as_attachment=True)


@app.route("/favicon.ico")
def favicon_empty():
    return Response(status=204)


def _default_host():
    return os.getenv("FLASK_HOST", cfg.get("flask", {}).get("host", "127.0.0.1"))


def _default_port():
    return int(os.getenv("FLASK_PORT", cfg.get("flask", {}).get("port", 5000)))


def _default_debug():
    return bool(
        int(
            os.getenv("FLASK_DEBUG", str(int(cfg.get("flask", {}).get("debug", False))))
        )
    )


def main() -> None:
    parser = argparse.ArgumentParser(
        prog="fit-converter", description="Run the FIT→CSV web UI"
    )
    parser.add_argument(
        "--host", default=_default_host(), help="Bind host (default from config/env)"
    )
    parser.add_argument(
        "--port",
        type=int,
        default=_default_port(),
        help="Bind port (default from config/env)",
    )
    parser.add_argument(
        "--debug",
        action=argparse.BooleanOptionalAction,
        default=_default_debug(),
        help="Enable Flask debug",
    )
    args = parser.parse_args()

    logger.info(
        "Starting Flask app on %s:%s (debug=%s)", args.host, args.port, args.debug
    )
    app.run(host=args.host, port=args.port, debug=args.debug)


if __name__ == "__main__":
    main()
