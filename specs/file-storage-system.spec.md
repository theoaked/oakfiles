# File Storage and Management System — Specification

## 1. Overview

A self-hosted file storage and management system running on a home server and accessible from any device on the same local network (WiFi or cable) via a web browser. The system provides authenticated access to the server's filesystem with role-based permissions, a responsive web interface, and runs as an OS-level service.

---

## 2. Goals

- Expose server directories to authorized users on the local network via browser
- Support full file management operations for admin users
- Support browsing and downloading for read-only users
- Run persistently as a background service on Windows (initially) and Linux (future)
- Be accessible and usable on mobile phones, tablets, and desktops/laptops
- Advertise itself on the local network via mDNS so devices can reach it by hostname

## 3. Non-Goals (for this version)

- Internet / remote access (no port forwarding, no reverse proxy)
- HTTPS / TLS (deferred to a future version)
- WebDAV / native OS drive mounting
- File versioning or history
- Real-time collaboration or locking

---

## 4. User Roles & Permissions

### 4.1 Roles

| Role      | Description                                      |
|-----------|--------------------------------------------------|
| `admin`   | Full access to allowed paths; manages users      |
| `readonly`| Can browse and download only; no write operations|

### 4.2 Permission Matrix

| Operation              | admin | readonly |
|------------------------|-------|----------|
| Browse directories     | ✓     | ✓        |
| Download files         | ✓     | ✓        |
| Download folder as ZIP | ✓     | ✓        |
| Search                 | ✓     | ✓        |
| Preview files          | ✓     | ✓        |
| Upload files           | ✓     | ✗        |
| Create folders         | ✓     | ✗        |
| Rename files/folders   | ✓     | ✗        |
| Move files/folders     | ✓     | ✗        |
| Delete files/folders   | ✓     | ✗        |
| Show hidden files      | ✓     | ✗        |
| Manage users           | ✓     | ✗        |
| View audit log         | ✓     | ✗        |

### 4.3 User Management (admin only)

- Create, edit, and delete users
- Assign role (admin or readonly) per user
- Force logout / invalidate sessions of a specific user
- Passwords stored as bcrypt hashes — never in plaintext

---

## 5. Directory Access Rules

### 5.1 Locked Paths (inaccessible to all users, including admin)

The following paths and their subtrees are permanently blocked at the application level regardless of role:

**Windows:**
- `C:\Windows`
- `C:\Program Files`
- `C:\Program Files (x86)`
- `C:\ProgramData`
- `C:\Users\<username>\AppData`
- Any path containing system junctions or reparse points that resolve outside the allowed tree

**Linux (future):**
- `/proc`
- `/sys`
- `/dev`
- `/boot`
- `/etc`
- `/bin`, `/sbin`, `/usr/bin`, `/usr/sbin`
- `/root`
- `/var/run`, `/run`

### 5.2 Allowed Paths

All paths not on the locked list are browsable and accessible according to the user's role. The admin configures one or more root paths at startup (via configuration file). Users cannot navigate above a configured root path.

### 5.3 Path Traversal Protection

The application must reject any request where the resolved absolute path does not begin with a configured root path. This prevents `../` traversal attacks.

---

## 6. Functional Requirements

### 6.1 Authentication

- Login form with username and password fields
- Failed login attempts must not reveal whether the username or password was wrong ("Invalid credentials" only)
- Session created on successful login, stored server-side
- Session expires after a configurable period of inactivity (default: 30 minutes)
- Logout endpoint that invalidates the server-side session immediately

### 6.2 File Browser

- Displays current directory contents: folders listed before files, both sorted alphabetically (case-insensitive)
- Each entry shows: name, type (file/folder), size (files only), last modified date
- Breadcrumb navigation showing the full path from the configured root, each segment clickable
- Clicking a folder navigates into it
- Clicking a file either previews it (if supported) or downloads it

**Hidden file filtering**

By default, the following entries are hidden from all users:
- Files and folders whose name starts with `.` (e.g. `.git`, `.env`, `.DS_Store`)
- Windows system noise: `desktop.ini`, `Thumbs.db`, `pagefile.sys`, `hiberfil.sys`, `swapfile.sys`, `$Recycle.Bin`, `System Volume Information`, `RECYCLER`, `$SysReset`, `$Windows.~BT`, `$Windows.~WS`

Admin users see a "Show hidden" checkbox in the toolbar. Checking it immediately reloads the current folder with hidden entries visible. The preference is not persisted across page loads. The server enforces the restriction — a non-admin passing `show_hidden=true` in the URL is silently ignored.

### 6.3 File Operations (admin only)

**Upload**
- Drag-and-drop zone covering the current directory view
- Fallback "Select Files" button for devices without drag-and-drop
- Multiple file upload in a single operation
- Progress indicator per file and overall
- Uploading a file with a name that already exists prompts the user: overwrite or keep both (auto-rename with suffix)

**Create Folder**
- Button/action in the current directory
- Validates folder name: no forbidden characters (`\ / : * ? " < > |`), not empty, not already existing

**Rename**
- Inline rename triggered from a context menu or icon on each entry
- Same name validation as folder creation

**Move**
- Select one or more items, then choose a destination folder via a folder picker dialog
- Moving into a locked path is rejected with a clear error message

**Delete**
- Requires explicit confirmation dialog listing the items to be deleted
- Deleting a non-empty folder deletes its contents recursively after confirmation

### 6.4 Download

- Single file: direct download via browser
- Folder as ZIP: server compresses the folder on the fly and streams it to the browser; this feature is optional and can be disabled via configuration

### 6.5 In-Browser Preview

Supported preview types opened in a modal or inline panel:

| Type              | Formats                              |
|-------------------|--------------------------------------|
| Images            | JPG, PNG, GIF, WEBP, SVG, BMP        |
| Video             | MP4, WEBM, OGG                       |
| Audio             | MP3, OGG, WAV, FLAC                  |
| PDF               | PDF (browser native viewer)          |
| Plain text / code | TXT, MD, JSON, XML, CSV, YAML, and common source code extensions |

Files not in this list are downloaded directly.

### 6.6 Search

- Search bar accessible from any directory view
- Searches filenames within the current directory and all subdirectories (recursive)
- Results show full path relative to the configured root, file size, and last modified date
- Clicking a result navigates to the containing folder and highlights the file
- Search is scoped to the configured root paths; locked paths are excluded from results
- Hidden files and directories (see §6.2) are excluded from search results by default; admin users with "Show hidden" enabled will see them in results

### 6.7 Audit Log (admin only)

Records the following events with timestamp (UTC), username, source IP, and relevant details:

| Event              | Details recorded                              |
|--------------------|-----------------------------------------------|
| Login success      | Username, IP                                  |
| Login failure      | Username attempted, IP                        |
| Logout             | Username, IP                                  |
| Session expiry     | Username                                      |
| File downloaded    | File path, size                               |
| File uploaded      | File path, size                               |
| File deleted       | File path (file or folder + item count)       |
| File renamed       | Old path → new path                           |
| File moved         | Source path → destination path                |
| Folder created     | Folder path                                   |
| Folder downloaded  | Folder path, ZIP size                         |
| User created       | New username, role                            |
| User edited        | Target username, field changed                |
| User deleted       | Target username                               |

Audit log is viewable in the admin panel with basic filtering by date range, event type, and username. Log entries are stored in an append-only SQLite database.

### 6.8 mDNS / Network Discovery

The service announces itself on the local network using mDNS (via the `zeroconf` Python library) so that devices can reach it at `<hostname>.local` instead of a raw IP address.

- The hostname defaults to the machine's OS hostname
- Can be overridden in the configuration file
- Announced service type: `_http._tcp.local.`
- No configuration required on client devices on macOS, iOS, or Windows 11
- On Android: works with modern Chrome; older versions may require IP fallback

---

## 7. Non-Functional Requirements

### 7.1 UI Theme

The interface uses a dark color scheme by default:

| Token               | Value     | Usage                              |
|---------------------|-----------|------------------------------------|
| `--color-bg`        | `#0f1117` | Page background                    |
| `--color-surface`   | `#1a1d27` | Cards, toolbar, table background   |
| `--color-border`    | `#2e3144` | Dividers, input borders            |
| `--color-text`      | `#e2e4ed` | Primary text                       |
| `--color-muted`     | `#8b90a7` | Secondary / hint text              |
| `--color-primary`   | `#6c8ef5` | Links, buttons, focus rings        |
| `--color-danger`    | `#f05252` | Destructive actions, error states  |
| `--color-success`   | `#34d399` | Active / success indicators        |

All colors are defined as CSS custom properties in `static/css/main.css` under `:root`, making a future light-mode or user-selectable theme straightforward to add.

### 7.2 Responsiveness

The UI must be fully functional on:
- Mobile phones (portrait and landscape, screen width ≥ 320px)
- Tablets (portrait and landscape)
- Desktop / laptop browsers

Touch targets must be at minimum 44×44px. No horizontal scrolling on mobile.

### 7.3 Performance

- Directory listings for up to 10,000 items must render in under 2 seconds on the local network
- File streaming must not buffer the entire file in memory (use chunked/streaming responses)
- ZIP folder download must stream on the fly without writing the archive to disk first

### 7.4 Security

- All endpoints (except `/login`) require an authenticated session; unauthenticated requests redirect to the login page
- Path traversal protection enforced on every file operation (see §5.3)
- Locked paths enforced on every file operation regardless of role
- Passwords stored as bcrypt hashes with a minimum cost factor of 12
- Session tokens must be cryptographically random (minimum 128 bits)
- CSRF protection on all state-changing requests
- File type validation on upload must check actual file content (magic bytes), not only the extension

### 7.5 Cross-Platform

The application must run without modification on:
- Windows 10 / 11 (primary target)
- Ubuntu 22.04 LTS and later (future target)

No OS-specific code paths outside of the locked-path list and the service installation mechanism.

---

## 8. Technical Stack

| Layer              | Technology                                              |
|--------------------|---------------------------------------------------------|
| Language           | Python 3.11+                                            |
| Web framework      | FastAPI                                                 |
| ASGI server        | Uvicorn                                                 |
| Frontend           | HTML + CSS (responsive) + vanilla JS or HTMX            |
| Session storage    | Server-side (in-memory or SQLite-backed)                |
| Database           | SQLite (users, sessions, audit log)                     |
| Password hashing   | `bcrypt` (direct, `>=4.0.0`)                            |
| mDNS               | `zeroconf`                                              |
| ZIP streaming      | Python standard library `zipfile` (streaming mode)      |
| Configuration      | TOML file (`config.toml`)                               |
| Service (Windows)  | NSSM (Non-Sucking Service Manager) or `pywin32`         |
| Service (Linux)    | systemd unit file                                       |

---

## 9. Configuration File (`config.toml`)

```toml
[server]
host = "0.0.0.0"       # listen on all interfaces
port = 8080
session_timeout_minutes = 30

[mdns]
enabled = true
hostname = ""          # empty = use OS hostname

[paths]
roots = [
  "D:\\Files",
  "E:\\Media"
]
zip_download_enabled = true
zip_max_size_mb = 2048  # refuse ZIP generation above this threshold

[security]
bcrypt_cost = 12
```

---

## 10. API Design (REST)

### Authentication
| Method | Path       | Description                        |
|--------|------------|------------------------------------|
| POST   | `/login`   | Submit credentials, create session |
| POST   | `/logout`  | Invalidate current session         |

### File Browser
| Method | Path             | Description                                                              |
|--------|------------------|--------------------------------------------------------------------------|
| GET    | `/api/ls`        | List directory contents (`?path=...&show_hidden=false`)                  |
| GET    | `/api/search`    | Search filenames (`?q=...&path=...&show_hidden=false`)                   |
| GET    | `/api/download`  | Download a file (`?path=...`)                                            |
| GET    | `/api/zip`       | Download folder as ZIP (`?path=...`)                                     |

`show_hidden` defaults to `false`; setting it to `true` is only honoured for admin sessions — the server silently resets it to `false` for readonly users.

### File Operations (admin only)
| Method | Path             | Description                                          |
|--------|------------------|------------------------------------------------------|
| POST   | `/api/upload`    | Upload one or more files (`multipart/form-data`)     |
| POST   | `/api/mkdir`     | Create a folder                                      |
| POST   | `/api/rename`    | Rename a file or folder                              |
| POST   | `/api/move`      | Move one or more items to a destination              |
| DELETE | `/api/delete`    | Delete one or more items                             |

### Admin
| Method | Path                   | Description                     |
|--------|------------------------|---------------------------------|
| GET    | `/api/users`           | List users                      |
| POST   | `/api/users`           | Create user                     |
| PATCH  | `/api/users/{id}`      | Edit user                       |
| DELETE | `/api/users/{id}`      | Delete user                     |
| GET    | `/api/audit`           | Query audit log (with filters)  |

---

## 11. Service Setup

### Windows
- Application packaged with a `install-service.bat` script
- Uses NSSM to register the Uvicorn process as a Windows Service
- Service name: `OakFilesService`
- Auto-start on system boot
- Logs written to `logs/service.log` (rotating, max 10 MB × 5 files)

### Linux (future)
- A `oakfiles.service` systemd unit file is included in the repository
- `install-service.sh` script copies it to `/etc/systemd/system/` and enables it
- Runs as a dedicated non-root user `oakfiles`

---

## 12. Future Considerations

- **HTTPS / TLS**: Add support via `mkcert`-generated certificates. The server will serve the CA certificate at a well-known URL for easy device-side installation. A setup wizard in the admin panel will guide the process.
- **Thumbnail generation**: Image and video thumbnails in the file browser grid view
- **Configurable per-user home directories**: Restrict each user to a specific subdirectory
- **Public share links**: Generate time-limited, unauthenticated download links for specific files
- **Storage quotas**: Per-user upload limits
- **WebDAV**: Expose root paths as WebDAV endpoints for native OS drive mounting
