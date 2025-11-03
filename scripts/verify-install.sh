# 0) Tools
python -m pip install --upgrade pip
python -m pip install build twine

# 1) Clean build artifacts
rm -rf dist build *.egg-info

# 2) Build wheel + sdist
python -m build

# 3) Check metadata (no network)
python -m twine check dist/*

# 4) Create clean venv and install from wheel
python -m venv .pkgtest && . .pkgtest/bin/activate
pip install --upgrade pip
pip install dist/fit_converter-*.whl

# 5) Quick doctor
fit-converter-doctor

# 6) Web UI health check
fit-converter --host 127.0.0.1 --port 5001 &
PID=$!; sleep 1.5
curl -fsS http://127.0.0.1:5001/healthz
kill $PID

# 7) Watcher start/stop
fit-converter-watcher --log-level INFO --retries 1 --poll 0.2 &
PID=$!; sleep 1
kill $PID

# 8) Cleanup
deactivate
rm -rf .pkgtest
