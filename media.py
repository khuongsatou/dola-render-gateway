"""Public reference media download and security validation (SSRF protected)."""
import asyncio
import ipaddress
import shutil
import socket
import tempfile
import weakref
from io import BytesIO
from pathlib import Path
from urllib.parse import urljoin, urlparse

import aiohttp
from PIL import Image

import auth_utils
import config

_ALLOWED_IMAGE_FORMATS = {"JPEG": ".jpg", "PNG": ".png", "WEBP": ".webp"}


def signed_video_path(filename: str, ttl: int | None = None) -> str:
    """Returns a /videos/<filename> path, signed when admin auth is configured."""
    path = f"/videos/{filename}"
    if not config.ADMIN_KEY:
        return path
    token = auth_utils.make_media_token(
        config.ADMIN_KEY, filename, ttl=ttl or config.MEDIA_TOKEN_TTL
    )
    return f"{path}?token={token}"

# Loop-local limits: concurrent downloads plus the aggregate temporary bytes held on disk.
_download_semaphores: weakref.WeakKeyDictionary = weakref.WeakKeyDictionary()
_byte_budgets: weakref.WeakKeyDictionary = weakref.WeakKeyDictionary()
_reserved_by_root: dict[str, tuple] = {}


class _ByteBudget:
    """Caps aggregate temporary bytes reserved by in-flight reference downloads."""

    def __init__(self, total_bytes: int):
        self.total_bytes = max(0, int(total_bytes or 0))
        self._used = 0
        self._condition = asyncio.Condition()

    async def reserve(self, amount: int) -> int:
        amount = max(0, int(amount))
        if self.total_bytes <= 0 or amount <= 0:
            return amount
        if amount > self.total_bytes:
            raise ValueError("Reference images exceed the temporary storage budget")
        async with self._condition:
            while self._used + amount > self.total_bytes:
                await self._condition.wait()
            self._used += amount
        return amount

    async def release(self, amount: int) -> None:
        amount = max(0, int(amount))
        if self.total_bytes <= 0 or amount <= 0:
            return
        async with self._condition:
            self._used = max(0, self._used - amount)
            self._condition.notify_all()


def _loop_scoped(store: weakref.WeakKeyDictionary, factory):
    loop = asyncio.get_running_loop()
    value = store.get(loop)
    if value is None:
        value = factory()
        store[loop] = value
    return value


def _download_semaphore() -> asyncio.Semaphore:
    return _loop_scoped(
        _download_semaphores,
        lambda: asyncio.Semaphore(max(1, config.REFERENCE_DOWNLOAD_CONCURRENCY)),
    )


def _byte_budget() -> _ByteBudget:
    return _loop_scoped(
        _byte_budgets,
        lambda: _ByteBudget(config.REFERENCE_TEMP_BUDGET_BYTES),
    )


def awaitable_getaddrinfo(host: str) -> list[str]:
    """Synchronous DNS resolution wrapper."""
    return [item[4][0] for item in socket.getaddrinfo(host, 443, type=socket.SOCK_STREAM)]


def _is_blocked_address(ip) -> bool:
    # is_global also covers non-standard internal ranges such as CGNAT
    # (100.64.0.0/10, used by Tailscale and cloud metadata endpoints) which are
    # neither is_private nor is_reserved on every Python version.
    if not ip.is_global:
        return True
    return (
        ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_reserved
        or ip.is_multicast or ip.is_unspecified
    )


def _check_addresses(host: str, addresses) -> list[str]:
    checked = []
    for raw in addresses:
        try:
            ip = ipaddress.ip_address(raw)
        except ValueError as exc:
            raise ValueError(f"Failed to resolve reference image domain: {host}") from exc
        if _is_blocked_address(ip):
            raise ValueError(
                "Reference image points to private or reserved IP address (SSRF blocked)"
            )
        checked.append(str(ip))
    if not checked:
        raise ValueError(f"Failed to resolve reference image domain: {host}")
    return sorted(set(checked))


async def resolve_public_host(host: str) -> list[str]:
    """Resolves a host once and returns only addresses validated as public."""
    try:
        ip = ipaddress.ip_address(host)
    except ValueError:
        try:
            resolved = await asyncio.to_thread(awaitable_getaddrinfo, host)
        except Exception as exc:
            raise ValueError(f"Failed to resolve reference image domain: {host}") from exc
        return _check_addresses(host, resolved)
    # SSRF check: a literal IP never reaches the resolver again, so pinning is implicit.
    return _check_addresses(host, [str(ip)])


def validate_public_url(url: str) -> str:
    """Accepts only public HTTP(S) URLs, blocks localhost, private network, and credentials."""
    if not isinstance(url, str) or len(url) > 4096:
        raise ValueError("Invalid reference image URL")
    parsed = urlparse(url)
    if parsed.scheme.lower() not in {"http", "https"} or not parsed.hostname:
        raise ValueError("Reference image only supports public http/https URLs")
    if parsed.username or parsed.password:
        raise ValueError("Reference image URL must not contain authentication credentials")
    host = parsed.hostname
    try:
        ip = ipaddress.ip_address(host)
    except ValueError:
        try:
            resolved = awaitable_getaddrinfo(host)
        except Exception as exc:
            raise ValueError(f"Failed to resolve reference image domain: {host}") from exc
        _check_addresses(host, resolved)
    else:
        _check_addresses(host, [str(ip)])
    return url


async def _validate_and_resolve(url: str) -> tuple[str, str, list[str]]:
    """Validates one URL and returns (url, host, pinned public addresses)."""
    if not isinstance(url, str) or len(url) > 4096:
        raise ValueError("Invalid reference image URL")
    parsed = urlparse(url)
    if parsed.scheme.lower() not in {"http", "https"} or not parsed.hostname:
        raise ValueError("Reference image only supports public http/https URLs")
    if parsed.username or parsed.password:
        raise ValueError("Reference image URL must not contain authentication credentials")
    host = parsed.hostname
    return url, host, await resolve_public_host(host)


async def _validate_url_async(url: str) -> str:
    url, _host, _addresses = await _validate_and_resolve(url)
    return url


class _PinnedResolver(aiohttp.abc.AbstractResolver):
    """Resolves exactly one hostname to addresses validated before connecting.

    aiohttp resolves hostnames again at connect time; without pinning, a DNS
    rebinding answer could send an already validated request to a private IP.
    """

    def __init__(self, host: str, addresses: list[str]):
        self._host = host.lower()
        self._addresses = list(addresses)

    async def resolve(self, host, port=0, family=socket.AF_UNSPEC):
        if str(host).lower() != self._host:
            raise OSError(f"DNS pinning violation: unexpected host {host}")
        results = []
        for address in self._addresses:
            address_family = socket.AF_INET6 if ":" in address else socket.AF_INET
            if family not in (socket.AF_UNSPEC, address_family):
                continue
            results.append({
                "hostname": host,
                "host": address,
                "port": port,
                "family": address_family,
                "proto": socket.IPPROTO_TCP,
                "flags": 0,
            })
        if not results:
            raise OSError(f"No pinned address available for {host}")
        return results

    async def close(self):
        return None


def _pinned_session(host: str, addresses: list[str]) -> aiohttp.ClientSession:
    """Direct connections reuse the validated addresses instead of re-resolving DNS."""
    connector = aiohttp.TCPConnector(resolver=_PinnedResolver(host, addresses))
    return aiohttp.ClientSession(connector=connector)


async def validate_reference_urls(urls: list[str]) -> list[str]:
    if len(urls) > config.REFERENCE_IMAGE_MAX_COUNT:
        raise ValueError(f"Maximum of {config.REFERENCE_IMAGE_MAX_COUNT} reference images allowed")
    normalized = []
    seen = set()
    for raw in urls:
        url, _host, _addresses = await _validate_and_resolve(raw)
        if url not in seen:
            normalized.append(url)
            seen.add(url)
    return normalized


async def _read_response_image(resp: aiohttp.ClientResponse, max_bytes: int) -> tuple[bytes, str]:
    content_length = resp.headers.get("Content-Length")
    if content_length and int(content_length) > max_bytes:
        raise ValueError("Reference image exceeds single file size limit")
    chunks = []
    total = 0
    async for chunk in resp.content.iter_chunked(64 * 1024):
        total += len(chunk)
        if total > max_bytes:
            raise ValueError("Reference image exceeds single file size limit")
        chunks.append(chunk)
    data = b"".join(chunks)
    try:
        with Image.open(BytesIO(data)) as image:
            image.verify()
            fmt = image.format
    except Exception as exc:
        raise ValueError("Reference file is not a valid image") from exc
    if fmt not in _ALLOWED_IMAGE_FORMATS:
        raise ValueError("Reference image only supports JPEG, PNG, WEBP")
    return data, _ALLOWED_IMAGE_FORMATS[fmt]


async def download_one_image(url: str, dest: Path, max_bytes: int | None = None) -> Path:
    limit = config.REFERENCE_IMAGE_MAX_BYTES if max_bytes is None else min(
        max(1, int(max_bytes)), config.REFERENCE_IMAGE_MAX_BYTES
    )
    # Direct connections pin the validated IPs. Going through DOLA_PROXY hands DNS
    # resolution to the proxy, so it is opt-in via DOLA_REFERENCE_USE_PROXY.
    proxies: list[str | None] = []
    if config.REFERENCE_USE_PROXY and config.PROXY:
        proxies.append(config.PROXY)
    proxies.append(None)
    last_error = None
    for proxy in proxies:
        try:
            current, host, addresses = await _validate_and_resolve(url)
            for _ in range(5):
                # A pinned resolver is used for every direct hop, including redirects.
                session = aiohttp.ClientSession() if proxy else _pinned_session(host, addresses)
                async with session:
                    async with session.get(
                        current,
                        allow_redirects=False,
                        proxy=proxy,
                        timeout=aiohttp.ClientTimeout(total=config.REFERENCE_DOWNLOAD_TIMEOUT),
                        headers={"User-Agent": "dola-pool-reference-fetch/1.0"},
                    ) as resp:
                        if 300 <= resp.status < 400 and resp.headers.get("Location"):
                            current, host, addresses = await _validate_and_resolve(
                                urljoin(current, resp.headers["Location"])
                            )
                            continue
                        if resp.status != 200:
                            raise ValueError(f"Failed to download reference image: HTTP {resp.status}")
                        data, suffix = await _read_response_image(resp, limit)
                        path = dest.with_suffix(suffix)
                        path.write_bytes(data)
                        return path
            raise ValueError("Too many redirects while downloading reference image")
        except Exception as exc:
            last_error = exc
    raise ValueError(str(last_error) if last_error else "Failed to download reference image")


async def download_reference_images(urls: list[str], task_id: str) -> tuple[Path | None, list[str]]:
    """Downloads reference images to temp folder, returns (root_dir, local_paths). Caller must cleanup."""
    urls = await validate_reference_urls(urls)
    if not urls:
        return None, []
    budget = _byte_budget()
    semaphore = _download_semaphore()
    task_limit = max(0, config.REFERENCE_IMAGE_MAX_TOTAL_BYTES)
    root = Path(tempfile.mkdtemp(prefix=f"dola_ref_{task_id}_"))
    reserved_total = 0
    committed = False
    try:
        paths = []
        for index, url in enumerate(urls):
            if task_limit:
                remaining = task_limit - reserved_total
                if remaining <= 0:
                    raise ValueError(
                        "Reference images exceed the per-task download size limit"
                    )
                per_file = min(config.REFERENCE_IMAGE_MAX_BYTES, remaining)
            else:
                per_file = config.REFERENCE_IMAGE_MAX_BYTES
            reserved = await budget.reserve(per_file)
            try:
                async with semaphore:
                    path = await download_one_image(url, root / f"image_{index}", per_file)
                actual = path.stat().st_size
                if actual > per_file:
                    raise ValueError("Reference image exceeds single file size limit")
                reserved_total += actual
                await budget.release(reserved - actual)
                paths.append(str(path))
            except BaseException:
                await budget.release(reserved)
                raise
        _reserved_by_root[str(root)] = (budget, reserved_total)
        committed = True
        return root, paths
    finally:
        if not committed:
            await budget.release(reserved_total)
            shutil.rmtree(root, ignore_errors=True)


async def cleanup_reference_images(root: Path | None) -> None:
    """Removes a reference temp folder and releases its reserved storage budget."""
    if root is None:
        return
    entry = _reserved_by_root.pop(str(root), None)
    shutil.rmtree(root, ignore_errors=True)
    if entry is not None:
        budget, amount = entry
        await budget.release(amount)
