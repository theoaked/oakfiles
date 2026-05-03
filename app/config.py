import sys
import os
from pathlib import Path
from dataclasses import dataclass, field

try:
    import tomllib
except ImportError:
    import tomli as tomllib  # type: ignore


CONFIG_PATH = Path(__file__).parent.parent / "config.toml"


@dataclass
class ServerConfig:
    host: str = "0.0.0.0"
    port: int = 8080
    session_timeout_minutes: int = 30


@dataclass
class MdnsConfig:
    enabled: bool = True
    hostname: str = ""


@dataclass
class PathsConfig:
    roots: list[Path] = field(default_factory=list)
    zip_download_enabled: bool = True
    zip_max_size_mb: int = 2048


@dataclass
class SecurityConfig:
    bcrypt_cost: int = 12


@dataclass
class AppConfig:
    server: ServerConfig = field(default_factory=ServerConfig)
    mdns: MdnsConfig = field(default_factory=MdnsConfig)
    paths: PathsConfig = field(default_factory=PathsConfig)
    security: SecurityConfig = field(default_factory=SecurityConfig)


def load_config(path: Path = CONFIG_PATH) -> AppConfig:
    if not path.exists():
        print(f"ERROR: config file not found at {path}", file=sys.stderr)
        print("Copy config.default.toml to config.toml and fill in paths.roots", file=sys.stderr)
        sys.exit(1)

    with open(path, "rb") as f:
        raw = tomllib.load(f)

    server_raw = raw.get("server", {})
    mdns_raw = raw.get("mdns", {})
    paths_raw = raw.get("paths", {})
    security_raw = raw.get("security", {})

    roots_raw = paths_raw.get("roots", [])
    if not roots_raw:
        print("ERROR: config.toml has no paths.roots defined.", file=sys.stderr)
        print("Add at least one directory, e.g.:", file=sys.stderr)
        print('  roots = ["D:\\\\Files"]', file=sys.stderr)
        sys.exit(1)

    roots = []
    for r in roots_raw:
        p = Path(r)
        if not p.exists():
            print(f"ERROR: configured root does not exist: {r}", file=sys.stderr)
            sys.exit(1)
        if not p.is_dir():
            print(f"ERROR: configured root is not a directory: {r}", file=sys.stderr)
            sys.exit(1)
        roots.append(p.resolve())

    return AppConfig(
        server=ServerConfig(
            host=server_raw.get("host", "0.0.0.0"),
            port=server_raw.get("port", 8080),
            session_timeout_minutes=server_raw.get("session_timeout_minutes", 30),
        ),
        mdns=MdnsConfig(
            enabled=mdns_raw.get("enabled", True),
            hostname=mdns_raw.get("hostname", ""),
        ),
        paths=PathsConfig(
            roots=roots,
            zip_download_enabled=paths_raw.get("zip_download_enabled", True),
            zip_max_size_mb=paths_raw.get("zip_max_size_mb", 2048),
        ),
        security=SecurityConfig(
            bcrypt_cost=security_raw.get("bcrypt_cost", 12),
        ),
    )
