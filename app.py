from pathlib import Path

from flask import Flask, render_template_string, request, send_file

from fit_to_csv import fit_to_csv

app = Flask(__name__)
BASE_DIR = Path(__file__).parent
INBOX = BASE_DIR / "inbox"
OUTBOX = BASE_DIR / "outbox"


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
            Transform for readability (pace, SPM, degrees)
            </label>
            <button type="submit" style="margin-top:8px">Upload & Convert</button>
        </form>
    """
    )


@app.post("/upload")
def upload_file():
    uploaded = request.files["fitfile"]
    inbox_path = INBOX / uploaded.filename
    out_path = OUTBOX / (uploaded.filename + ".csv")

    INBOX.mkdir(exist_ok=True)
    OUTBOX.mkdir(exist_ok=True)
    uploaded.save(inbox_path)

    try:
        do_transform = "transform" in request.form
        fit_to_csv(inbox_path, out_path, transform=do_transform)
    except NotImplementedError:
        return "<p>Conversion not yet implemented.</p>", 501

    return send_file(out_path, as_attachment=True)


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
