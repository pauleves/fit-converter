# Production Deployment on Raspberry Pi 4

This guide walks through hardening a Raspberry Pi 4, installing the FIT Converter stack, and running it as a managed service. Commands assume Raspberry Pi OS Bookworm (64‑bit) and that you have SSH access as `pi` (or another sudoer). Adjust paths/usernames to your environment.

## 1. Base OS Hardening

1. Flash the latest Raspberry Pi OS Lite (64‑bit). If you’re using Raspberry Pi Imager ≥1.7, open **Advanced Options** (gear icon) before flashing and set Wi‑Fi credentials, SSH (key-based) access, hostname, locale, and username/password there—no manual file edits needed. If you are flashing with another tool, prepare networking before the first boot by mounting the `boot` partition and adding:
   ```bash
   touch /path/to/boot/ssh
   cat <<'EOF' | sudo tee /path/to/boot/wpa_supplicant.conf
   country=US              # set to your ISO country code
   ctrl_interface=DIR=/var/run/wpa_supplicant GROUP=netdev
   update_config=1

   network={
       ssid="YourWifiSSID"
       psk="LongRandomPassphrase"
   }
   EOF
   ```
   This enables SSH on first boot and joins the configured Wi-Fi without needing a monitor or keyboard. Reserve a static DHCP lease (or configure a static IP inside `dhcpcd.conf`) so the server is reachable remotely.
2. Before exposing the device, connect via console or trusted network and:
   ```bash
   sudo raspi-config           # change password, enable SSH, set locale/timezone, disable auto-login
   sudo apt update && sudo apt full-upgrade -y
   sudo apt install -y unattended-upgrades
   sudo dpkg-reconfigure --priority=low unattended-upgrades
   ```
3. Create a dedicated, non-sudo runtime user with a usable shell (needed for `sudo -iu fitconv`) and lock down SSH:
   ```bash
   sudo adduser --disabled-password --shell /bin/bash --gecos "" fitconv
   sudo usermod -a -G dialout,plugdev fitconv     # optional: if FIT files arrive via USB
   sudo -u fitconv mkdir -p /home/fitconv/.ssh && sudo chmod 700 /home/fitconv/.ssh
   sudo cp ~/.ssh/authorized_keys /home/fitconv/.ssh/
   sudo chown -R fitconv:fitconv /home/fitconv/.ssh
   sudoedit /etc/ssh/sshd_config.d/10-hardening.conf
   ```
   Add:
   ```
   PasswordAuthentication no
   PermitRootLogin no
   AllowUsers fitconv
   ```
   If you keep a separate admin account for remote maintenance (e.g., `piadmin`), append it to `AllowUsers` so you do not lock yourself out. Then `sudo systemctl restart ssh`. If you already created the user and see `This account is currently not available` when running `sudo -iu fitconv`, fix the shell with `sudo usermod -s /bin/bash fitconv`.
4. Enable the firewall and only open required ports (SSH + HTTPS via Caddy):
   ```bash
   sudo apt install -y ufw
   sudo ufw allow 22/tcp
   sudo ufw allow 443/tcp
   sudo ufw enable
   ```
   The Flask app will listen on `127.0.0.1:8080` only; Caddy terminates TLS on port 443 and proxies requests internally, so there is no direct HTTP exposure.

## 2. Install Python 3.14 Toolchain

The project targets Python 3.14. On Raspberry Pi OS you’ll need to build it once under `/opt/python-3.14`.

```bash
sudo apt install -y build-essential zlib1g-dev libncursesw5-dev libgdbm-dev \
    libnss3-dev libssl-dev libreadline-dev libffi-dev libbz2-dev libsqlite3-dev \
    liblzma-dev uuid-dev tk-dev wget
cd /tmp
wget https://www.python.org/ftp/python/3.14.0/Python-3.14.0.tgz
tar xf Python-3.14.0.tgz
cd Python-3.14.0
./configure --enable-optimizations --with-ensurepip=install --prefix=/opt/python-3.14
make -j"$(nproc)"
sudo make altinstall
sudo ln -sfn /opt/python-3.14/bin/python3.14 /usr/local/bin/python3.14
```

## 3. Layout Application Directories

```bash
sudo mkdir -p /opt/fit-converter /var/lib/fit-converter/data /var/lib/fit-converter/state/logs
sudo chown -R fitconv:fitconv /opt/fit-converter /var/lib/fit-converter
sudo chmod 750 /opt/fit-converter
```

- `/opt/fit-converter` — code + virtual environment
- `/var/lib/fit-converter/data` — inbox/outbox
- `/var/lib/fit-converter/state` — log + state files

## 4. Install the App Inside a Virtual Environment

Log in as the service user (or use `sudo -u fitconv`):

```bash
sudo -iu fitconv
cd /opt/fit-converter
/usr/local/bin/python3.14 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install --upgrade wheel build
# Option A: install from PyPI/GitHub release
pip install fit-converter
# Option B: copy a signed wheel from CI and install
# pip install /path/to/dist/fit_converter-*-py3-none-any.whl
deactivate
exit
```

If you cloned the repository on the Pi, run `python -m build` inside it and install the generated wheel into `/opt/fit-converter/.venv`.

## 5. Configuration Files

Keep secrets and environment overrides out of the repo:

```bash
sudo mkdir -p /etc/fit-converter
sudo touch /etc/fit-converter/app.env /etc/fit-converter/watcher.env
sudo chown root:fitconv /etc/fit-converter/*.env
sudo chmod 640 /etc/fit-converter/*.env
```

Example `app.env`:
```
FIT_CONVERTER_DATA_DIR=/var/lib/fit-converter/data
FIT_CONVERTER_STATE_DIR=/var/lib/fit-converter/state
FIT_CONVERTER_LOGS_DIR=/var/lib/fit-converter/state/logs
FIT_CONVERTER_INBOX=inbox
FIT_CONVERTER_OUTBOX=outbox
FIT_CONVERTER_LOG_LEVEL=INFO
FIT_CONVERTER_LOG_TO_FILE=true
FLASK_SECRET_KEY=change-this-to-a-long-random-string
```

Systemd’s `ExecStart` pins the Flask process to `127.0.0.1:8080`, so you do not need to set `FLASK_HOST` or `FLASK_PORT` in the environment unless you change the unit file.

Optional transformations, poll intervals, and retry limits are controlled via additional `FIT_CONVERTER_*` variables (see `README.md`).

## 6. Systemd Services

Create a reusable environment drop-in:

```bash
sudo tee /etc/systemd/system/fit-converter-app.service > /dev/null <<'EOF'
[Unit]
Description=FIT Converter Flask API
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
User=fitconv
Group=fitconv
WorkingDirectory=/opt/fit-converter
EnvironmentFile=/etc/fit-converter/app.env
ExecStart=/opt/fit-converter/.venv/bin/python -m fit_converter.app --host 127.0.0.1 --port 8080
Restart=on-failure
RestartSec=5
RuntimeDirectory=fit-converter
NoNewPrivileges=true
ProtectSystem=full
ProtectHome=true
PrivateTmp=true
CapabilityBoundingSet=
AmbientCapabilities=

[Install]
WantedBy=multi-user.target
EOF

sudo tee /etc/systemd/system/fit-converter-watcher.service > /dev/null <<'EOF'
[Unit]
Description=FIT Converter Watcher
After=fit-converter-app.service
Requires=fit-converter-app.service

[Service]
Type=simple
User=fitconv
Group=fitconv
WorkingDirectory=/opt/fit-converter
EnvironmentFile=/etc/fit-converter/watcher.env
ExecStart=/opt/fit-converter/.venv/bin/python -m fit_converter.watcher --log-level INFO --poll 0.5 --retries 2
Restart=on-failure
RestartSec=5
NoNewPrivileges=true
ProtectSystem=full
ProtectHome=true
PrivateTmp=true
CapabilityBoundingSet=
AmbientCapabilities=

[Install]
WantedBy=multi-user.target
EOF
```

Populate `/etc/fit-converter/watcher.env` similarly to `app.env` (it can often just source the same file).

Enable and start both units:

```bash
sudo systemctl daemon-reload
sudo systemctl enable --now fit-converter-app.service fit-converter-watcher.service
sudo systemctl status fit-converter-app.service
sudo systemctl status fit-converter-watcher.service
```

## 7. Caddy Reverse Proxy & HTTPS (Required)

All external traffic should go through Caddy so clients only ever hit HTTPS:

```bash
sudo apt install -y caddy
sudo tee /etc/caddy/Caddyfile > /dev/null <<'EOF'
fit.example.com {
    encode gzip zstd
    log
    tls you@example.com
    reverse_proxy 127.0.0.1:8080
    header {
        Strict-Transport-Security "max-age=31536000; includeSubDomains; preload"
    }
}
EOF
sudo systemctl reload caddy
```
Replace `fit.example.com` with your DNS name (or use an internal CA if it is not public). Caddy listens on 443 (opened in UFW earlier) and forwards requests to the loopback-only Flask service on port 8080. This enforces HTTPS-only access; no direct HTTP port should be reachable from the network.

## 8. Operational Checks

1. Confirm services are healthy: `systemctl --failed` should return nothing.
2. Run diagnostics inside the venv:
   ```bash
   sudo -iu fitconv
   cd /opt/fit-converter
   source .venv/bin/activate
   python -m fit_converter.doctor
   deactivate
   ```
3. Upload a `.fit` file through the web UI (`https://fit.example.com/upload` if proxied) and verify CSV output lands in `/var/lib/fit-converter/data/outbox`.
4. Tail logs when debugging: `journalctl -u fit-converter-app -u fit-converter-watcher -f`.

## 9. Maintenance

- Apply OS updates monthly: `sudo apt update && sudo apt full-upgrade`.
- Rotate SSH keys regularly and keep `ufw` rules minimal.
- When upgrading the app:
  ```bash
  sudo systemctl stop fit-converter-app fit-converter-watcher
  sudo -iu fitconv bash -c 'cd /opt/fit-converter && source .venv/bin/activate && pip install --upgrade fit-converter && deactivate'
  sudo systemctl start fit-converter-app fit-converter-watcher
  ```
- Re-run `python -m fit_converter.doctor` after any configuration changes.

Following these steps gives you a locked-down Raspberry Pi 4 appliance that continuously ingests FIT files, converts them safely, and exposes a hardened web UI or watcher service with minimal manual intervention.
