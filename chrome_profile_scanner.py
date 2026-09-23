"""Chrome Profile Scanner and Importer for Dola Render Gateway.

Scans local macOS Google Chrome profiles (Local State & Preferences) and provides
instant zero-credential import into Dola's account pool.
Adapted from mtips5s_scan_profile.
"""

import json
import os
import re
import shutil
import sqlite3
import subprocess
import time
from pathlib import Path

# Match allowed account names in Dola: 2-40 alphanumeric, _, -, .
NAME_RE = re.compile(r"^[a-zA-Z0-9_\-\.]{2,40}$")
EMAIL_RE = re.compile(r"[\w\.\-]+@[\w\.\-]+\.\w+")


def get_default_chrome_root() -> Path:
    """Returns the macOS Google Chrome user data directory."""
    custom = os.environ.get("CHROME_USER_DATA_DIR")
    if custom:
        return Path(custom).resolve()
    return Path.home() / "Library" / "Application Support" / "Google" / "Chrome"


def format_bytes(bytes_val: int | None) -> str:
    """Formats raw byte count into human-readable size string."""
    if not bytes_val or bytes_val <= 0:
        return "0 B"
    units = ["B", "KB", "MB", "GB", "TB"]
    val = float(bytes_val)
    idx = 0
    while val >= 1024 and idx < len(units) - 1:
        val /= 1024
        idx += 1
    return f"{val:.1f} {units[idx]}" if idx > 1 and val < 10 else f"{int(round(val))} {units[idx]}"


def chrome_color_to_hex(color_int: int | None) -> str | None:
    """Converts Chrome ARGB integer color to #RRGGBB hex string."""
    if not isinstance(color_int, int) or color_int == 0:
        return None
    r = (color_int >> 16) & 0xFF
    g = (color_int >> 8) & 0xFF
    b = color_int & 0xFF
    return f"#{r:02x}{g:02x}{b:02x}"


def sanitize_account_name(raw_name: str, existing_names: set[str], prefix: str = "p_") -> str:
    """Sanitizes an account name into a valid, unique Dola account identifier."""
    clean = re.sub(r"[^a-zA-Z0-9_\-\.]", "_", raw_name.strip()).strip("._-")
    if not clean:
        clean = "acc"
    if not clean.startswith(prefix) and not clean.startswith("acc_"):
        clean = f"{prefix}{clean}"
    clean = clean[:35]
    if len(clean) < 2:
        clean = f"{clean}_1"

    candidate = clean
    counter = 2
    while candidate.lower() in {e.lower() for e in existing_names}:
        candidate = f"{clean[:32]}_{counter}"
        counter += 1
    return candidate


def get_imported_accounts_map(accounts_dir: Path, db_path: str = "pool_usage.db") -> dict[str, dict]:
    """Returns a map of imported accounts by checking directory and pool_usage.db notes/emails."""
    imported_map = {}
    if not accounts_dir.exists():
        return imported_map

    meta_by_name = {}
    try:
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        for row in conn.execute("SELECT name, email, note FROM accounts_meta"):
            meta_by_name[row["name"]] = dict(row)
        conn.close()
    except Exception:
        pass

    for d in accounts_dir.iterdir():
        if d.is_dir() and not d.name.startswith("."):
            name = d.name
            meta = meta_by_name.get(name, {})
            note = meta.get("note", "")
            email = meta.get("email", "")

            # Check if note specifies source profile directory
            match = re.search(r"Imported from (Default|Profile \d+)", note)
            source_dir = match.group(1) if match else None
            imported_map[name] = {
                "name": name,
                "email": email,
                "note": note,
                "source_dir": source_dir,
            }
    return imported_map


def scan_chrome_profiles(
    chrome_root: Path | None = None,
    accounts_dir: Path | None = None,
    db_path: str = "pool_usage.db",
) -> list[dict]:
    """Scans all Google Chrome profiles from the local system with rich metadata."""
    root = chrome_root or get_default_chrome_root()
    acc_dir = accounts_dir or Path("accounts")

    if not root.exists():
        return []

    local_state_path = root / "Local State"
    info_cache: dict = {}

    if local_state_path.exists():
        try:
            raw = local_state_path.read_text(encoding="utf-8", errors="ignore")
            data = json.loads(raw)
            info_cache = data.get("profile", {}).get("info_cache", {})
        except Exception:
            pass

    imported_accounts = get_imported_accounts_map(acc_dir, db_path)
    imported_dirs = {
        item["source_dir"]: item["name"]
        for item in imported_accounts.values()
        if item.get("source_dir")
    }

    profiles_map: dict[str, dict] = {}

    # 1. Inspect Local State info_cache
    for directory, item in info_cache.items():
        if not isinstance(item, dict):
            continue
        dir_name = directory.strip()
        dir_path = root / dir_name
        exists = dir_path.exists()

        name = str(item.get("name", "")).strip() or dir_name
        email = str(item.get("user_name", "")).strip() or None
        gaia_name = str(item.get("gaia_name", "")).strip() or None
        avatar_icon = item.get("avatar_icon")
        highlight_color = chrome_color_to_hex(
            item.get("profile_highlight_color") or item.get("default_avatar_fill_color")
        )

        # Regex fallback for email if not explicitly set
        if not email:
            m = EMAIL_RE.search(name) or (EMAIL_RE.search(gaia_name) if gaia_name else None)
            if m:
                email = m.group(0)

        is_default = dir_name.lower() == "default"
        is_imported = dir_name in imported_dirs
        imported_name = imported_dirs.get(dir_name)

        # Suggest account name
        if is_default:
            suggested_seed = "default"
        else:
            seed = dir_name.replace("Profile ", "p").lower()
            if email:
                user_part = email.split("@")[0]
                user_part_clean = re.sub(r"[^a-zA-Z0-9_]", "", user_part)[:12]
                suggested_seed = f"{user_part_clean}_{seed}" if user_part_clean else seed
            else:
                suggested_seed = seed

        profiles_map[dir_name] = {
            "directory": dir_name,
            "absolute_path": str(dir_path),
            "name": name,
            "email": email or "",
            "gaia_name": gaia_name or "",
            "avatar_icon": avatar_icon,
            "highlight_color": highlight_color,
            "exists": exists,
            "is_default": is_default,
            "is_imported": is_imported,
            "imported_name": imported_name,
            "suggested_name": suggested_seed,
        }

    # 2. Check filesystem for directories missed in info_cache
    for entry in root.iterdir():
        if not entry.is_dir():
            continue
        dir_name = entry.name
        if dir_name != "Default" and not dir_name.startswith("Profile "):
            continue
        if dir_name in profiles_map:
            continue

        pref_path = entry / "Preferences"
        pref_name = None
        pref_email = None

        if pref_path.exists():
            try:
                pdata = json.loads(pref_path.read_text(encoding="utf-8", errors="ignore"))
                if isinstance(pdata, dict):
                    pref_name = pdata.get("profile", {}).get("name")
                    accs = pdata.get("account_info", [])
                    if accs and isinstance(accs, list) and accs[0].get("email"):
                        pref_email = accs[0].get("email")
            except Exception:
                pass

        name = pref_name or dir_name
        email = pref_email or ""
        if not email:
            m = EMAIL_RE.search(name)
            if m:
                email = m.group(0)

        is_default = dir_name.lower() == "default"
        is_imported = dir_name in imported_dirs
        imported_name = imported_dirs.get(dir_name)

        seed = "default" if is_default else dir_name.replace("Profile ", "p").lower()
        profiles_map[dir_name] = {
            "directory": dir_name,
            "absolute_path": str(entry),
            "name": name,
            "email": email,
            "gaia_name": "",
            "avatar_icon": None,
            "highlight_color": None,
            "exists": True,
            "is_default": is_default,
            "is_imported": is_imported,
            "imported_name": imported_name,
            "suggested_name": seed,
        }

    # 3. Sort: Default first, then natural ordering by name
    def sort_key(p):
        is_def = 0 if p["is_default"] else 1
        return (is_def, p["name"].lower(), p["directory"])

    return sorted(profiles_map.values(), key=sort_key)


def extract_chrome_dola_cookies(src_dir: Path) -> list[dict]:
    """Extracts and decrypts Dola cookies from Chrome SQLite on macOS."""
    cookie_db = src_dir / "Cookies"
    if not cookie_db.exists():
        cookie_db = src_dir / "Network" / "Cookies"
    if not cookie_db.exists():
        return []

    import platform
    if platform.system() != "Darwin":
        return []

    try:
        import hashlib
        cmd = ["security", "find-generic-password", "-w", "-s", "Chrome Safe Storage"]
        password = subprocess.check_output(cmd, stderr=subprocess.DEVNULL).strip()
        salt = b"saltysalt"
        key = hashlib.pbkdf2_hmac("sha1", password, salt, 1003, 16)
        hex_key = key.hex()
        hex_iv = (b" " * 16).hex()

        conn = sqlite3.connect(f"file:{cookie_db}?immutable=1", uri=True)
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT host_key, name, path, is_secure, is_httponly, expires_utc, encrypted_value 
            FROM cookies 
            WHERE host_key LIKE "%dola.com%"
            """
        )
        rows = cursor.fetchall()
        conn.close()

        def decrypt_val(enc):
            if not enc or not enc.startswith(b"v10"):
                return ""
            raw = enc[3:]
            p = subprocess.Popen(
                ["openssl", "enc", "-d", "-aes-128-cbc", "-K", hex_key, "-iv", hex_iv],
                stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE
            )
            out, _ = p.communicate(raw)
            if len(out) > 32 and all(32 <= b <= 126 for b in out[32:]):
                return out[32:].decode("utf-8", errors="ignore")
            m = re.search(rb"[\x20-\x7e]{3,}", out)
            if m:
                return m.group(0).decode("utf-8", errors="ignore")
            return out.decode("utf-8", errors="ignore")

        cookies = []
        for host_key, name, path, is_secure, is_httponly, expires_utc, enc in rows:
            val = decrypt_val(enc)
            if val:
                cookies.append({
                    "name": name,
                    "value": val,
                    "domain": host_key,
                    "path": path,
                    "secure": bool(is_secure),
                    "httpOnly": bool(is_httponly),
                })
        return cookies
    except Exception:
        return []


def import_chrome_profile(
    directory: str,
    target_name: str | None = None,
    email: str | None = None,
    chrome_root: Path | None = None,
    accounts_dir: Path | None = None,
    db_path: str = "pool_usage.db",
) -> dict:
    """Imports a local Chrome profile into Dola accounts pool via lightweight copy."""
    root = chrome_root or get_default_chrome_root()
    acc_dir = accounts_dir or Path("accounts")
    acc_dir.mkdir(parents=True, exist_ok=True)

    src_dir = root / directory
    if not src_dir.exists() or not src_dir.is_dir():
        raise FileNotFoundError(f"Chrome profile directory not found: {src_dir}")

    # Determine existing account names
    existing = {d.name for d in acc_dir.iterdir() if d.is_dir()}

    if target_name:
        clean_name = target_name.strip()
        if not NAME_RE.match(clean_name):
            raise ValueError(f"Invalid account name '{clean_name}'. Must match {NAME_RE.pattern}")
        if clean_name in existing:
            raise ValueError(f"Account name '{clean_name}' already exists in pool.")
        acc_name = clean_name
    else:
        seed = "default" if directory.lower() == "default" else directory.replace("Profile ", "p").lower()
        if email:
            user_part = re.sub(r"[^a-zA-Z0-9_]", "", email.split("@")[0])[:12]
            if user_part:
                seed = f"{user_part}_{seed}"
        acc_name = sanitize_account_name(seed, existing)

    dest_dir = acc_dir / acc_name
    dest_default = dest_dir / "Default"
    dest_default.mkdir(parents=True, exist_ok=True)

    # 1. Copy profile contents using rsync (excluding caches)
    rsync_cmd = [
        "rsync", "-a",
        "--exclude=Cache",
        "--exclude=Code Cache",
        "--exclude=GPUCache",
        "--exclude=DawnGraphiteCache",
        "--exclude=DawnWebGPUCache",
        "--exclude=GraphiteDawnCache",
        "--exclude=Service Worker/CacheStorage",
        "--exclude=blob_storage",
        "--exclude=SingletonLock",
        "--exclude=SingletonCookie",
        "--exclude=SingletonSocket",
        f"{str(src_dir)}/",
        f"{str(dest_default)}/",
    ]
    res = subprocess.run(rsync_cmd, capture_output=True, text=True)
    if res.returncode != 0:
        # Fallback to copytree if rsync is not available
        def _ignore_caches(_path, names):
            return {"Cache", "Code Cache", "GPUCache", "SingletonLock", "SingletonCookie", "SingletonSocket"}
        for item in src_dir.iterdir():
            target_item = dest_default / item.name
            if item.is_dir():
                if item.name not in {"Cache", "Code Cache", "GPUCache"}:
                    shutil.copytree(item, target_item, ignore=_ignore_caches, dirs_exist_ok=True)
            elif item.name not in {"SingletonLock", "SingletonCookie", "SingletonSocket"}:
                shutil.copy2(item, target_item)

    # 2. Copy Local State
    local_state_src = root / "Local State"
    if local_state_src.exists():
        shutil.copy2(local_state_src, dest_dir / "Local State")

    # 3. Clean up lock files
    for lock_file in ("SingletonLock", "SingletonCookie", "SingletonSocket"):
        (dest_dir / lock_file).unlink(missing_ok=True)
        (dest_default / lock_file).unlink(missing_ok=True)

    # 4. Decrypt & save cookies.json for seamless Playwright session injection
    try:
        decrypted_cookies = extract_chrome_dola_cookies(src_dir)
        if decrypted_cookies:
            (dest_dir / "cookies.json").write_text(json.dumps(decrypted_cookies, indent=2), encoding="utf-8")
    except Exception:
        pass

    # 5. Detect email if not provided
    if not email:
        pref_path = dest_default / "Preferences"
        if pref_path.exists():
            try:
                pdata = json.loads(pref_path.read_text(encoding="utf-8", errors="ignore"))
                accs = pdata.get("account_info", [])
                if accs and isinstance(accs, list) and accs[0].get("email"):
                    email = accs[0].get("email")
            except Exception:
                pass

    # 6. Insert metadata into pool_usage.db
    note = f"Imported from {directory}"
    now = time.time()
    try:
        conn = sqlite3.connect(db_path)
        conn.execute(
            """
            INSERT INTO accounts_meta (name, email, note, created_at, scheduling, incognito)
            VALUES (?, ?, ?, ?, 1, 0)
            ON CONFLICT(name) DO UPDATE SET
                email=excluded.email,
                note=excluded.note
            """,
            (acc_name, email or "", note, now),
        )
        conn.commit()
        conn.close()
    except Exception as e:
        print(f"[Scanner] Warning: Could not update accounts_meta: {e}", flush=True)

    return {
        "ok": True,
        "name": acc_name,
        "directory": directory,
        "email": email or "",
        "path": str(dest_dir),
    }


def bulk_import_chrome_profiles(
    directories: list[str],
    prefix: str = "p_",
    chrome_root: Path | None = None,
    accounts_dir: Path | None = None,
    db_path: str = "pool_usage.db",
) -> dict:
    """Imports multiple profiles into Dola accounts pool."""
    root = chrome_root or get_default_chrome_root()
    acc_dir = accounts_dir or Path("accounts")

    # Get metadata for detected profiles
    scanned = {p["directory"]: p for p in scan_chrome_profiles(root, acc_dir, db_path)}

    results = []
    errors = []

    for dir_name in directories:
        if dir_name not in scanned:
            errors.append({"directory": dir_name, "error": "Profile not found"})
            continue
        p = scanned[dir_name]
        if p.get("is_imported"):
            results.append({"directory": dir_name, "name": p.get("imported_name"), "skipped": True})
            continue

        try:
            res = import_chrome_profile(
                directory=dir_name,
                email=p.get("email"),
                chrome_root=root,
                accounts_dir=acc_dir,
                db_path=db_path,
            )
            results.append(res)
        except Exception as e:
            errors.append({"directory": dir_name, "error": str(e)})

    return {
        "ok": len(errors) == 0,
        "imported_count": len([r for r in results if not r.get("skipped")]),
        "skipped_count": len([r for r in results if r.get("skipped")]),
        "failed_count": len(errors),
        "results": results,
        "errors": errors,
    }
