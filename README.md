# OakFiles

A self-hosted file storage and management system for your home network. Run it on any machine and access your files from any device on the same WiFi or cable network — phone, tablet, laptop — through a web browser.

## Features

- **File browser** — navigate directories with breadcrumb navigation
- **Upload** — drag-and-drop or select files, with per-file progress bar
- **File operations** — rename, move, delete, create folders (admin only)
- **Download** — single files or entire folders as a ZIP archive
- **In-browser preview** — images, video, audio, PDF, and text/code files open directly in the browser
- **Search** — find files by name across the entire directory tree
- **Role-based access** — `admin` (full access) and `readonly` (browse and download only)
- **Audit log** — every login, upload, delete, and move is recorded and viewable by admins
- **Network discovery** — the server announces itself via mDNS so other devices can reach it at `http://<hostname>.local` without knowing the IP address
- **Runs as a service** — Windows (NSSM) and Linux (systemd) service scripts included
- **Mobile-friendly** — responsive interface that works on phones and desktops

## Requirements

- Python 3.11 or newer
- Windows 10/11 or Linux (Ubuntu 22.04+)

## Installation

**1. Create a local virtual environment and install dependencies:**

Windows:
```bat
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
```

Linux / macOS:
```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

All packages are installed inside the `.venv` folder in the project directory — nothing is installed globally. You need to activate the environment every time you open a new terminal before running the server manually. The service scripts handle this automatically.

**2. Configure the server:**

Open `config.toml` and set the directories you want to expose:

```toml
[paths]
roots = ["D:\\Files", "E:\\Media"]
```

You can list as many root paths as you want. Sensitive system directories (Windows, Program Files, AppData, etc.) are blocked even if you add them here.

Other settings you may want to adjust:

```toml
[server]
port = 8080
session_timeout_minutes = 30

[mdns]
enabled = true   # set to false to disable hostname.local discovery
```

**3. Run:**

Windows (with the virtual environment active):
```bat
.venv\Scripts\activate
python main.py
```

Linux / macOS:
```bash
source .venv/bin/activate
python main.py
```

On the **first run**, a default `admin` account is created and its password is printed to the console:

```
============================================================
  FIRST RUN — default admin account created
  Username : admin
  Password : <generated-password>
  Change this password after your first login!
============================================================
```

**4. Open the browser:**

From the same machine:
```
http://localhost:8080
```

From any other device on the same network (if mDNS is enabled):
```
http://<your-machine-hostname>.local:8080
```

If mDNS doesn't work on a device, use the server's local IP address directly, e.g. `http://192.168.1.42:8080`.

## Running as a Service

### Windows (requires [NSSM](https://nssm.cc))

Run as Administrator:

```bat
install-service.bat
```

This registers OakFiles as a Windows service named `OakFilesService` that starts automatically on boot. Logs are written to `logs\service.log`.

To stop or remove:
```bat
nssm stop OakFilesService
nssm remove OakFilesService confirm
```

### Linux (systemd)

```bash
# Create a dedicated user
sudo useradd -r -s /sbin/nologin oakfiles

# Copy project to /opt
sudo cp -r . /opt/oakfiles
sudo chown -R oakfiles:oakfiles /opt/oakfiles

# Create a local virtual environment
sudo -u oakfiles python3 -m venv /opt/oakfiles/.venv
sudo -u oakfiles /opt/oakfiles/.venv/bin/pip install -r /opt/oakfiles/requirements.txt

# Install and enable the service
sudo cp oakfiles.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now oakfiles
```

## User Management

Log in as `admin`, then go to **Users** in the top navigation bar to:

- Create new users and assign them the `admin` or `readonly` role
- Change usernames and passwords
- Disable accounts

## Project Structure

```
oakfiles/
├── main.py                  # Entry point
├── config.toml              # Your configuration (not committed)
├── config.default.toml      # Reference configuration with all defaults
├── requirements.txt
├── app/
│   ├── config.py            # Config loader
│   ├── database.py          # SQLite setup and first-run bootstrap
│   ├── models.py            # Request/response models
│   ├── auth/                # Session management, password hashing, middleware
│   ├── api/                 # REST API routes
│   ├── core/                # Path guards, filesystem helpers, ZIP streaming, audit
│   ├── mdns.py              # mDNS network discovery
│   └── web/                 # HTML page routes
├── templates/               # Jinja2 HTML templates
├── static/                  # CSS, JavaScript, vendored HTMX
├── logs/                    # Runtime logs (not committed)
├── install-service.bat      # Windows service installer
└── oakfiles.service         # Linux systemd unit file
```

## Data Storage

OakFiles creates a single SQLite database file (`oakfiles.db`) in the project root. It stores:
- User accounts (passwords stored as bcrypt hashes)
- Active sessions
- Audit log entries

The database is created automatically on first run and is not committed to version control.
