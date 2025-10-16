from flask import Flask

app = Flask(__name__)

@app.get("/health")
def health():
    return {"status": "ok"}

@app.get("/")
def home():
    return "<h1>FIT → CSV</h1><p>Drag-and-drop coming soon.</p>"

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
