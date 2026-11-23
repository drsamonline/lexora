"""REQ-RES-003 — the pipeline runs offline, and here is the proof rather than the promise.

The requirement: *"Offline operation after dependency installation"* (verification: a
network-disabled smoke test). The register carried it as **Not started** — the test the
requirement names did not exist.

**How the network is actually disabled.** Each verb runs in a child process whose very first act
is to replace the socket constructors and the resolver with functions that raise. That is stricter
than an unplugged interface: a library cannot quietly reach the network through a path the test
did not think of, because there is no path — `socket.socket` itself is gone. It also means the
guard is testable, which matters more than it sounds: a network guard that does not actually
guard produces green ticks and no evidence.

The control test at the bottom asserts the guard blocks a real connection attempt, so this file
cannot pass by accident.

**What is covered:** canonicalize → pack → verify → unpack (byte-identical), then the query path
(init → add → search → stats), then `doctor`. That is every operation a user performs on their own
machine, which is the claim "offline" is making.
"""

from __future__ import annotations

import pathlib
import subprocess
import sys

import pytest

REPO = pathlib.Path(__file__).resolve().parents[1]

#: Prepended to every child process. Replacing the constructors, not the callers, is the point:
#: anything that wants a socket has to come through here.
NETWORK_GUARD = '''
import socket

_real_socket = socket.socket


def _deny(*args, **kwargs):
    raise RuntimeError("network access attempted in an offline test")


class _DeniedSocket(_real_socket):
    """A subclass, not a function: `ssl` does `class SSLSocket(socket)` at import time, so
    replacing the name with a function breaks the interpreter instead of the network."""

    def __init__(self, *args, **kwargs):
        raise RuntimeError("network access attempted in an offline test")


socket.socket = _DeniedSocket
socket.create_connection = _deny
socket.getaddrinfo = _deny
socket.gethostbyname = _deny
socket.gethostbyname_ex = _deny
'''

SAMPLE = (
    "Offline operation is the requirement. A tool that quietly phones home is not offline,\n"
    "and a test that only pretends to unplug the network proves nothing about either.\n"
) * 40


def run_offline(argv: list[str], *, cwd: pathlib.Path | None = None) -> subprocess.CompletedProcess:
    """Run the CLI in a child process whose network is removed before lexora is imported."""
    script = NETWORK_GUARD + "\nfrom lexora.cli import main\nraise SystemExit(main(%r))\n" % (argv,)
    return subprocess.run(
        [sys.executable, "-c", script],
        cwd=str(cwd or REPO), capture_output=True, text=True, timeout=120,
    )


@pytest.fixture(scope="module")
def workspace(tmp_path_factory) -> pathlib.Path:
    ws = tmp_path_factory.mktemp("offline")
    (ws / "sample.txt").write_text(SAMPLE, encoding="utf-8")
    return ws


def test_the_guard_actually_blocks_the_network() -> None:
    """The control. Without this, every test below could be passing for the wrong reason."""
    script = NETWORK_GUARD + """
import socket, urllib.request

attempts = {
    "socket.socket()": lambda: socket.socket(),
    "create_connection": lambda: socket.create_connection(("example.com", 80), timeout=2),
    "urlopen": lambda: urllib.request.urlopen("http://example.com", timeout=2),
}
blocked = 0
for name, attempt in attempts.items():
    try:
        attempt()
    except Exception as exc:
        blocked += 1
        print(f"blocked {name}: {type(exc).__name__}")
    else:
        print(f"NOT BLOCKED: {name}")
raise SystemExit(0 if blocked == len(attempts) else 1)
"""
    proc = subprocess.run([sys.executable, "-c", script], capture_output=True, text=True, timeout=60)
    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert proc.stdout.count("blocked ") == 3, proc.stdout
    assert "RuntimeError" in proc.stdout, (
        "the socket constructor itself must refuse — anything weaker is a guard a library can "
        "slip past"
    )


def test_the_whole_pipeline_runs_with_no_network(workspace) -> None:
    """canon → pack → verify → unpack, and the bytes that come back are the bytes that went in."""
    canon = workspace / "canonical.txt"
    archive = workspace / "archive.lxz"
    restored = workspace / "restored.txt"

    for argv in (
        ["canon", "--in", str(workspace / "sample.txt"), "--out", str(canon)],
        ["pack", "--in", str(canon), "--out", str(archive)],
        ["verify", "--in", str(archive)],
        ["unpack", "--in", str(archive), "--out", str(restored)],
        ["inspect", "--in", str(archive), "--verify"],
        ["doctor"],
    ):
        proc = run_offline(argv)
        assert proc.returncode == 0, f"{argv[0]} failed offline:\n{proc.stdout}\n{proc.stderr}"

    assert restored.read_bytes() == canon.read_bytes(), "the offline round trip was not byte-exact"
    assert archive.stat().st_size > 0


def test_the_query_path_runs_with_no_network(workspace) -> None:
    """A catalog is built and queried offline — the archive a user actually works with."""
    root = workspace / "catalog"

    for argv in (
        ["db", "init", "--root", str(root)],
        ["db", "add", "--root", str(root), "--in", str(workspace / "sample.txt"),
         "--path", "sample.txt", "--title", "offline sample"],
        ["db", "search", "--root", str(root), "--query", "offline", "--json"],
        ["db", "stats", "--root", str(root)],
    ):
        proc = run_offline(argv)
        assert proc.returncode == 0, f"db {argv[1]} failed offline:\n{proc.stdout}\n{proc.stderr}"

    search = run_offline(["db", "search", "--root", str(root), "--query", "phones", "--json"])
    assert search.returncode == 0, search.stderr
    assert "sample.txt" in search.stdout, "the offline catalog did not find a word it was given"


def test_no_package_reaches_for_the_network_at_import_time(workspace) -> None:
    """Importing lexora with sockets removed must not raise — a lazy fetch at import is a bug."""
    proc = run_offline(["doctor"])
    assert proc.returncode == 0, proc.stderr
    assert "network" not in proc.stderr.lower()
