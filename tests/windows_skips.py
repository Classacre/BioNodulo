"""Shared Windows-skip markers for tests that exercise POSIX-only primitives.

Production code paths that these tests cover (symlinks, FIFOs, O_NOFOLLOW,
dir_fd, process groups, POSIX paths) explicitly require a POSIX platform;
the production code either falls back gracefully or refuses to run. The
tests verify POSIX-specific behavior that cannot be meaningfully tested on
Windows, so they skip rather than fail.

Usage:
    from tests.windows_skips import skip_on_windows
    @skip_on_windows
    def test_symlink_behavior(): ...
"""
import sys
import pytest

IS_WINDOWS = sys.platform == "win32"
skip_on_windows = pytest.mark.skipif(
    IS_WINDOWS, reason="POSIX-only primitive (symlink/fifo/dir_fd/process-group)"
)
skip_on_windows_symlink = pytest.mark.skipif(
    IS_WINDOWS, reason="symlink creation requires privilege on Windows"
)
skip_on_windows_path = pytest.mark.skipif(
    IS_WINDOWS, reason="POSIX path assertion (/tmp, /opt, /proc)"
)
