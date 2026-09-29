import io
import os

import pytest

from utils import cli_tools


class FakeStdin(io.StringIO):
    def isatty(self):
        return False


def _ready(stdin):
    return lambda r, w, x, t: ([stdin], [], [])


def _never(r, w, x, t):
    return ([], [], [])


def test_posix_line_returns_typed_line(capsys):
    stdin = FakeStdin("42\n")
    assert cli_tools._posix_line("> ", 1, stdin, _ready(stdin)) == "42"


def test_posix_line_times_out_with_none(capsys):
    assert cli_tools._posix_line("> ", 0.1, FakeStdin(), _never) is None
    assert "Time's up!" in capsys.readouterr().out


def test_posix_line_eof_raises():
    stdin = FakeStdin("")
    with pytest.raises(EOFError):
        cli_tools._posix_line("> ", 1, stdin, _ready(stdin))


def test_posix_key_returns_single_character():
    stdin = FakeStdin("yn")
    assert cli_tools._posix_key(1, stdin, _ready(stdin)) == "y"
    assert stdin.read() == "n"  # only one character consumed


def test_posix_key_times_out_with_none():
    assert cli_tools._posix_key(0.1, FakeStdin("y"), _never) is None


@pytest.mark.skipif(os.name == "nt", reason="select() on pipes and termios are POSIX-only")
def test_posix_functions_against_a_real_pipe(monkeypatch):
    read_fd, write_fd = os.pipe()
    stdin = os.fdopen(read_fd, "r")
    try:
        assert cli_tools._posix_key(0.05, stdin) is None       # nothing written yet
        os.write(write_fd, b"y")
        assert cli_tools._posix_key(1, stdin) == "y"
        os.write(write_fd, b"7\n")
        assert cli_tools._posix_line("", 1, stdin) == "7"
    finally:
        stdin.close()
        os.close(write_fd)


@pytest.mark.skipif(cli_tools.msvcrt is None, reason="Windows only")
def test_windows_ctrl_c_raises_keyboard_interrupt(monkeypatch):
    keys = iter([cli_tools.CTRL_C])
    monkeypatch.setattr(cli_tools.msvcrt, "kbhit", lambda: True)
    monkeypatch.setattr(cli_tools.msvcrt, "getwch", lambda: next(keys))
    with pytest.raises(KeyboardInterrupt):
        cli_tools.get_single_keypress_with_timeout(1)


def test_public_api_dispatches_by_platform(monkeypatch):
    monkeypatch.setattr(cli_tools, "msvcrt", None)
    monkeypatch.setattr(cli_tools, "_posix_line", lambda p, t: "posix")
    monkeypatch.setattr(cli_tools, "_posix_key", lambda t: "k")
    assert cli_tools.get_input_with_timeout("", 1) == "posix"
    assert cli_tools.get_single_keypress_with_timeout(1) == "k"
