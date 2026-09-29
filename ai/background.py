"""Run AI calls on a background thread so the CLI never blocks on the network."""

from concurrent.futures import Future, ThreadPoolExecutor
from typing import Callable, Optional, TypeVar

T = TypeVar("T")

_executor = ThreadPoolExecutor(max_workers=2, thread_name_prefix="ai")


def submit(fn: Callable[..., T], *args, **kwargs) -> "Future[T]":
    return _executor.submit(fn, *args, **kwargs)


def result_or_none(future: Optional["Future[T]"], timeout: float = 0.0) -> Optional[T]:
    """Return the future's result if ready within `timeout` seconds, else None (errors count as None)."""
    if future is None:
        return None
    try:
        return future.result(timeout=timeout)
    except Exception:
        return None
