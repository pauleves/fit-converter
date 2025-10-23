import logging

from flask import Flask, jsonify, render_template_string, request, send_file

from fit_converter import paths

from .converter import fit_to_csv

logger = logging.getLogger(__name__)
app = Flask(__name__)


@app.errorhandler(Exception)
def handle_unexpected(e):
    app.logger.exception("Unhandled error during request")
    return jsonify(error="Sorry, something went wrong while converting your file."), 400


@app.get("/health")
def health():
    return {"status": "ok"}


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


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
