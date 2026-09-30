"""Terminal helpers: screen clearing and input with a timeout (Windows and POSIX)."""

# msvcrt / termios exist on only one platform each and the matching branch is chosen at runtime,
# which a type checker cannot follow.
# pyright: reportOptionalMemberAccess=false, reportAttributeAccessIssue=false

import os
import select
import sys
import time

try:
    import msvcrt
except ImportError:  # not Windows
    msvcrt = None

try:
    import termios
    import tty
except ImportError:  # Windows
    termios = tty = None

CTRL_C = "\x03"


def clear_screen():
    os.system('cls' if os.name == 'nt' else 'clear')


# ── Windows ──────────────────────────────────────────────────────────────────

def _windows_line(prompt: str, timeout_sec: float):
    print(prompt, end="", flush=True)
    start_time = time.time()
    result = ""

    while True:
        if msvcrt.kbhit():
            char = msvcrt.getwche()
            if char == CTRL_C:  # msvcrt swallows Ctrl+C as a plain character
                raise KeyboardInterrupt
            if char == '\r' or char == '\n':
                print()
                return result
            elif char == '\b':
                result = result[:-1]
            else:
                result += char

        if time.time() - start_time > timeout_sec:
            print("\nTime's up!")
            return None

        time.sleep(0.01)


def _windows_key(timeout_sec: float):
    start_time = time.time()
    while time.time() - start_time < timeout_sec:
        if msvcrt.kbhit():
            char = msvcrt.getwch()
            if char == CTRL_C:
                raise KeyboardInterrupt
            return char
        time.sleep(0.01)
    return None


# ── POSIX ────────────────────────────────────────────────────────────────────
# `stdin` and `select_fn` are parameters so the logic can be tested without a real terminal.

def _discard_pending_input(stdin) -> None:
    """Drop keystrokes typed after a timeout so they don't leak into the next prompt."""
    if termios is not None and stdin.isatty():
        try:
            termios.tcflush(stdin.fileno(), termios.TCIFLUSH)
        except (termios.error, OSError):
            pass


def _posix_line(prompt: str, timeout_sec: float, stdin=None, select_fn=select.select):
    """Read a line, giving up after `timeout_sec` seconds (the line is delivered on Enter)."""
    stdin = stdin or sys.stdin
    print(prompt, end="", flush=True)
    ready, _, _ = select_fn([stdin], [], [], timeout_sec)
    if not ready:
        _discard_pending_input(stdin)
        print("\nTime's up!")
        return None
    line = stdin.readline()
    if line == "":  # EOF
        raise EOFError
    return line.rstrip("\r\n")


def _posix_key(timeout_sec: float, stdin=None, select_fn=select.select):
    """Wait for one keystroke without needing Enter; restores the terminal even on Ctrl+C."""
    stdin = stdin or sys.stdin
    is_tty = stdin.isatty() and termios is not None
    old_settings = None
    if is_tty:
        fd = stdin.fileno()
        old_settings = termios.tcgetattr(fd)
        tty.setcbreak(fd)  # unbuffered, no echo; Ctrl+C still raises KeyboardInterrupt
    try:
        ready, _, _ = select_fn([stdin], [], [], timeout_sec)
        if not ready:
            return None
        if is_tty:  # bypass Python's text buffer so select() and read agree on what is pending
            return os.read(stdin.fileno(), 1).decode("utf-8", errors="ignore") or None
        return stdin.read(1) or None
    finally:
        if old_settings is not None:
            termios.tcsetattr(stdin.fileno(), termios.TCSADRAIN, old_settings)


# ── Public API ───────────────────────────────────────────────────────────────

def get_input_with_timeout(prompt: str, timeout_sec: float):
    """Read a line of input. Returns None if `timeout_sec` passes first."""
    if msvcrt is not None:
        return _windows_line(prompt, timeout_sec)
    return _posix_line(prompt, timeout_sec)


def get_single_keypress_with_timeout(timeout_sec: float):
    """Wait for a single keystroke for a given duration. Returns None if timed out."""
    if msvcrt is not None:
        return _windows_key(timeout_sec)
    return _posix_key(timeout_sec)
