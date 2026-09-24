"""Real subprocess artifact capture, including bytes invalid as UTF-8."""
import asyncio
import hashlib
import sys

import pytest

from bionodulo.execution.subprocess_runner import CommandOutputLimitError, run_subprocess


def test_binary_stdout_is_byte_exact_and_not_logged(tmp_path):
    output = tmp_path / "binary.dat"
    events = []
    result = asyncio.run(run_subprocess(
        [sys.executable, "-c", "import sys; sys.stdout.buffer.write(bytes(range(256))*4096)"],
        stdout_path=output, stdout_binary=True, timeout=15,
        emit=lambda kind, data: events.append((kind, data)),
    ))
    expected = bytes(range(256)) * 4096
    assert output.stat().st_size == len(expected)
    assert hashlib.sha256(output.read_bytes()).digest() == hashlib.sha256(expected).digest()
    assert result["returncode"] == 0 and result["stdout"] == ""
    assert not any(data["level"] == "stdout" for _, data in events)


def test_binary_stdout_cannot_silently_discard_artifact():
    with pytest.raises(ValueError, match="requires stdout_path"):
        asyncio.run(run_subprocess([sys.executable, "-c", "raise SystemExit(99)"], stdout_binary=True))


def test_binary_capture_refuses_preexisting_file_before_running(tmp_path):
    target = tmp_path / "keep.dat"
    target.write_bytes(b"must survive")
    marker = tmp_path / "executed"
    with pytest.raises(FileExistsError):
        asyncio.run(run_subprocess(
            [sys.executable, "-c", "from pathlib import Path; Path('executed').touch()"],
            cwd=tmp_path, stdout_path=target, stdout_binary=True,
        ))
    assert target.read_bytes() == b"must survive"
    assert not marker.exists()


def test_binary_capture_refuses_symlink_before_running(tmp_path):
    target = tmp_path / "keep.dat"
    target.write_bytes(b"must survive")
    link = tmp_path / "capture.dat"
    try:
        link.symlink_to(target)
    except OSError:
        pytest.skip("host cannot create symlinks")
    with pytest.raises(FileExistsError):
        asyncio.run(run_subprocess([sys.executable, "-c", "print('clobber')"],
                                  stdout_path=link, stdout_binary=True))
    assert target.read_bytes() == b"must survive"


def test_binary_capture_stops_a_noisy_process_at_the_declared_limit(tmp_path):
    target = tmp_path / "bounded.dat"
    with pytest.raises(CommandOutputLimitError, match="1024-byte"):
        asyncio.run(asyncio.wait_for(run_subprocess(
            [sys.executable, "-c", "import os; chunk=b'x'*65536\nwhile True: os.write(1,chunk)"],
            stdout_path=target, stdout_binary=True, stdout_max_bytes=1024, timeout=10,
        ), timeout=15))
    assert target.read_bytes() == b"x" * 1024
