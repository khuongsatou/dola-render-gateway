"""Shared per-account locks and browser execution slots."""
import asyncio
import weakref
from contextlib import asynccontextmanager

import config

_locks_by_loop: weakref.WeakKeyDictionary = weakref.WeakKeyDictionary()
_semaphores_by_loop: weakref.WeakKeyDictionary = weakref.WeakKeyDictionary()


def _loop_locks() -> dict[str, asyncio.Lock]:
    loop = asyncio.get_running_loop()
    locks = _locks_by_loop.get(loop)
    if locks is None:
        locks = {}
        _locks_by_loop[loop] = locks
    return locks


def get_account_lock(account: str) -> asyncio.Lock:
    """Returns the shared lock for one Chrome profile in the current event loop."""
    locks = _loop_locks()
    lock = locks.get(account)
    if lock is None:
        lock = asyncio.Lock()
        locks[account] = lock
    return lock


def get_execution_semaphore(max_concurrency: int | None = None) -> asyncio.Semaphore:
    """Returns the shared browser execution semaphore for the current event loop."""
    loop = asyncio.get_running_loop()
    semaphore = _semaphores_by_loop.get(loop)
    if semaphore is None:
        semaphore = asyncio.Semaphore(max(1, max_concurrency or config.MAX_CONCURRENCY))
        _semaphores_by_loop[loop] = semaphore
    return semaphore


async def acquire_account_execution(account: str, max_concurrency: int | None = None):
    """Acquires a global browser slot, then the shared lock for the selected account."""
    semaphore = get_execution_semaphore(max_concurrency)
    await semaphore.acquire()
    try:
        await get_account_lock(account).acquire()
    except BaseException:
        semaphore.release()
        raise


def release_account_execution(account: str, max_concurrency: int | None = None):
    """Releases the account lock and its global browser slot."""
    lock = get_account_lock(account)
    if lock.locked():
        lock.release()
    get_execution_semaphore(max_concurrency).release()


@asynccontextmanager
async def account_execution(account: str, max_concurrency: int | None = None):
    await acquire_account_execution(account, max_concurrency)
    try:
        yield
    finally:
        release_account_execution(account, max_concurrency)
