from flask import Flask, request, send_file, render_template_string
from pathlib import Path
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
    return render_template_string("""
        <h1>Upload a FIT file</h1>
        <form action="/upload" method="post" enctype="multipart/form-data">
            <input type="file" name = "fitfile" accept=".fit" required>
            <button type="submit">Upload & Convert</button>
        </form>
    """)

@app.post("/upload")
def upload_file():
    uploaded = request.files["fitfile"]
    inbox_path = INBOX / uploaded.filename
    out_path = OUTBOX / (uploaded.filename + ".csv")

    INBOX.mkdir(exist_ok=True)
    OUTBOX.mkdir(exist_ok=True)
    uploaded.save(inbox_path)

    try:
        rows = fit_to_csv(inbox_path, out_path)
    except NotImplementedError:
        return "<p>Conversion not yet implemented.</p>", 501

    return send_file(out_path, as_attachment=True)

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
