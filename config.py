"""Dola Pool Configuration: Environment variable based with smart defaults."""
import os
from pathlib import Path


def _load_local_env():
    """Load ignored .env.local for local/tunnel runs; real environment wins."""
    path = Path(__file__).with_name(".env.local")
    if not path.exists():
        return
    for raw in path.read_text(encoding="utf-8-sig").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


_load_local_env()
HOST = os.getenv("DOLA_HOST", "0.0.0.0")
PORT = int(os.getenv("DOLA_PORT", "8000"))

# Bind addresses that only accept connections from the local machine.
LOOPBACK_HOSTS = {"127.0.0.1", "::1", "localhost"}


def is_loopback_host(host: str | None) -> bool:
    """True when the configured bind address only accepts local connections."""
    return (host or "").strip().lower().strip("[]") in LOOPBACK_HOSTS


# Explicit opt-in for unauthenticated loopback development. Never enable this
# on a host that can accept remote connections.
ALLOW_UNAUTHENTICATED = os.getenv("DOLA_ALLOW_UNAUTHENTICATED", "0") == "1"

# Service API keys (comma-separated). Empty is only tolerated on a loopback bind.
API_KEYS = [k.strip() for k in os.getenv("DOLA_API_KEYS", "").split(",") if k.strip()]

# Longest accepted generation prompt (characters)
PROMPT_MAX_LENGTH = int(os.getenv("DOLA_PROMPT_MAX_LENGTH", "4000"))

# Account pool cookie file (one dola.com cookie per line)
COOKIES_FILE = os.getenv("DOLA_COOKIES_FILE", "cookies.txt")

# Max concurrent video generation tasks
MAX_CONCURRENCY = int(os.getenv("DOLA_MAX_CONCURRENCY", "3"))

# Global pending task queue limit (queued + processing), 0 = unlimited
MAX_PENDING_TASKS = int(os.getenv("DOLA_MAX_PENDING_TASKS", "100"))

# Video generation timeout in seconds
VIDEO_TIMEOUT = int(os.getenv("DOLA_VIDEO_TIMEOUT", "300"))

# SQLite database path
DB_PATH = os.getenv("DOLA_DB_PATH", "tasks.db")

# Account pool database path (quota + account metadata)
POOL_DB_PATH = os.getenv("DOLA_POOL_DB_PATH", "pool_usage.db")

# Video download storage directory (served statically by FastAPI)
DOWNLOAD_DIR = os.getenv("DOLA_DOWNLOAD_DIR", "downloads")

# Explicit browser proxy (must point to JP/KR egress; empty = system proxy)
PROXY = os.getenv("DOLA_PROXY", "")

# Run browser in headless mode (login always runs with head)
HEADLESS = os.getenv("DOLA_HEADLESS", "1") == "1"

# Run browser in incognito mode (default: disabled)
INCOGNITO = os.getenv("DOLA_INCOGNITO", "0") == "1"

# Base public URL for returning static video links
PUBLIC_BASE = os.getenv("DOLA_PUBLIC_BASE", f"http://127.0.0.1:{PORT}")

# Admin web dashboard password (empty is only tolerated on a loopback bind)
ADMIN_KEY = os.getenv("DOLA_ADMIN_KEY", "")

# Dola 30s / Watermark Removal Chromium extension path
EXTENSION_DIR = os.getenv("DOLA_EXTENSION_DIR", "extensions/dola30")
EXTENSION_ENABLED = os.getenv("DOLA_EXTENSION_ENABLED", "1") == "1"

# Daily quota reset timezone (Japan midnight by default)
LIMIT_RESET_TZ = os.getenv("DOLA_LIMIT_RESET_TZ", "Asia/Tokyo")

# Conservative credit check before video generation (default 2 points)
VIDEO_REQUIRED_POINTS = int(os.getenv("DOLA_VIDEO_REQUIRED_POINTS", "2"))

# Public reference image download limits
REFERENCE_IMAGE_MAX_BYTES = int(os.getenv("DOLA_REFERENCE_IMAGE_MAX_BYTES", str(15 * 1024 * 1024)))
REFERENCE_IMAGE_MAX_TOTAL_BYTES = int(
    os.getenv("DOLA_REFERENCE_IMAGE_MAX_TOTAL_BYTES", str(60 * 1024 * 1024))
)
REFERENCE_DOWNLOAD_CONCURRENCY = int(os.getenv("DOLA_REFERENCE_DOWNLOAD_CONCURRENCY", "4"))
# Aggregate temporary storage held by in-flight reference downloads
REFERENCE_TEMP_BUDGET_BYTES = int(
    os.getenv("DOLA_REFERENCE_TEMP_BUDGET_BYTES", str(512 * 1024 * 1024))
)
# Route reference downloads through DOLA_PROXY. Off by default because the proxy
# resolves the target hostname itself, which bypasses local DNS pinning.
REFERENCE_USE_PROXY = os.getenv("DOLA_REFERENCE_USE_PROXY", "0") == "1"
REFERENCE_DOWNLOAD_TIMEOUT = int(os.getenv("DOLA_REFERENCE_DOWNLOAD_TIMEOUT", "60"))
REFERENCE_IMAGE_MAX_COUNT = int(os.getenv("DOLA_REFERENCE_IMAGE_MAX_COUNT", "30"))

# Extended generation window for reference image tasks (seconds)
REFERENCE_VIDEO_TIMEOUT = int(os.getenv("DOLA_REFERENCE_VIDEO_TIMEOUT", "900"))

# Lifetime of signed /videos/<file> download links handed to the dashboard (seconds)
MEDIA_TOKEN_TTL = int(os.getenv("DOLA_MEDIA_TOKEN_TTL", "3600"))
