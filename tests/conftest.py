"""Test-suite-wide guarantees.

Keep the suite hermetic: no test may reach out for a vendor binary. Dorado's
tarball is ~4 GB, so a single unguarded node execution turns a 90-second suite
into a stalled download. `tests/test_external_binary.py` unsets this variable
for the cases that deliberately exercise provisioning.

Windows compatibility: tests that exercise POSIX-only primitives (symlinks,
FIFOs, O_NOFOLLOW/dir_fd, process groups, POSIX path assertions) are skipped
on Windows via a collection hook below — production code either falls back
gracefully or explicitly refuses non-POSIX platforms, so these tests verify
behaviour that cannot be meaningfully exercised on Windows.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest


@pytest.fixture(autouse=True)
def _no_vendor_binary_downloads(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("BIONODULO_EXTERNAL_BINARY_OFFLINE", "1")


# ---------------------------------------------------------------------------
# Windows skip: applied at collection time so test files stay untouched.
# ---------------------------------------------------------------------------

_IS_WINDOWS = sys.platform == "win32"

# Entire modules whose production code path requires POSIX descriptor
# primitives (O_NOFOLLOW, dir_fd, os.open("/", ...), start_new_session).
_WINDOWS_SKIP_MODULES = {
    "tests/catalog/test_outputs.py": (
        "output-contract requires O_NOFOLLOW/dir_fd (POSIX-only)"
    ),
    "tests/catalog/test_ledger.py": (
        "POSIX directory fsync + mode bits; sentencepiece optional dep"
    ),
    "tests/test_workspace.py": (
        "symlink creation requires privilege on Windows"
    ),
}

# Individual tests (module_path::test_name) that exercise POSIX-only
# primitives or assert POSIX paths.
_WINDOWS_SKIP_TESTS = {
    "tests/test_execution_runtime.py::test_run_subprocess_cancel_kills_process_tree":
        "process-group kill semantics differ on Windows",
    "tests/test_execution_runtime.py::test_executor_dry_run_preview_plans_command_outputs_and_cache":
        "POSIX path assertion",
    "tests/test_execution_runtime.py::test_workflow_executor_persists_artifacts_in_run_metadata":
        "POSIX path assertion",
    "tests/test_execution_runtime.py::test_named_env_prefix_uses_the_ready_workflow_manifest_and_locked_manta_env":
        "asserts /opt/pixi POSIX path",
    "tests/test_execution_runtime.py::test_command_node_rejects_missing_planned_outputs":
        "COMMAND ['true'] not found on Windows",
    "tests/test_external_binary.py::test_an_executable_already_on_path_is_used_as_is":
        "shutil.which does not find extension-less scripts on Windows",
    # test_environment_compiler.py: pixi_identity battery (O_NOFOLLOW) +
    # _capture_pixi_list battery (start_new_session/pass_fds) + CRLF fixture
    "tests/catalog/test_environment_compiler.py::test_pixi_identity_rejects_wrong_binary_sha256":
        "O_NOFOLLOW is POSIX-only",
    "tests/catalog/test_environment_compiler.py::test_pixi_identity_rejects_relative_executable_path":
        "O_NOFOLLOW is POSIX-only",
    "tests/catalog/test_environment_compiler.py::test_pixi_identity_rejects_missing_binary":
        "O_NOFOLLOW is POSIX-only",
    "tests/catalog/test_environment_compiler.py::test_pixi_identity_rejects_symlink":
        "O_NOFOLLOW is POSIX-only",
    "tests/catalog/test_environment_compiler.py::test_pixi_identity_rejects_directory":
        "O_NOFOLLOW is POSIX-only",
    "tests/catalog/test_environment_compiler.py::test_pixi_identity_rejects_fifo_without_blocking":
        "os.mkfifo is POSIX-only",
    "tests/catalog/test_environment_compiler.py::test_pixi_identity_rejects_zero_byte_binary":
        "O_NOFOLLOW is POSIX-only",
    "tests/catalog/test_environment_compiler.py::test_pixi_identity_rejects_oversized_binary":
        "O_NOFOLLOW is POSIX-only",
    "tests/catalog/test_environment_compiler.py::test_pixi_identity_rejects_non_executable_regular_file":
        "O_NOFOLLOW is POSIX-only",
    "tests/catalog/test_environment_compiler.py::test_pixi_identity_retains_verified_fd_across_path_replacement":
        "O_NOFOLLOW + /proc/self/fd is POSIX-only",
    "tests/catalog/test_environment_compiler.py::test_pixi_identity_rejects_in_place_mutation_during_hash":
        "O_NOFOLLOW is POSIX-only",
    "tests/catalog/test_environment_compiler.py::test_capture_owns_subprocess_fd_cwd_and_pipes":
        "start_new_session/pass_fds are POSIX-only",
    "tests/catalog/test_environment_compiler.py::test_capture_reports_bounded_nonzero_exit_stderr":
        "start_new_session is POSIX-only",
    "tests/catalog/test_environment_compiler.py::test_capture_kills_and_reaps_child_when_stdout_exceeds_bound":
        "start_new_session is POSIX-only",
    "tests/catalog/test_environment_compiler.py::test_capture_kills_and_reaps_child_when_stderr_exceeds_bound":
        "start_new_session is POSIX-only",
    "tests/catalog/test_environment_compiler.py::test_capture_timeout_kills_and_reaps_child":
        "start_new_session is POSIX-only",
    "tests/catalog/test_environment_compiler.py::test_decoder_accepts_repository_lock_emitted_by_pinned_pixi_0681":
        "pixi.lock fixture has CRLF line endings on Windows git checkouts",
    "tests/catalog/test_environment_compiler.py::test_private_compiler_rejects_stage_mutation_after_capture_error":
        "O_NOFOLLOW/dir_fd is POSIX-only",
    "tests/catalog/test_environment_compiler.py::test_private_compiler_rejects_forged_direct_conda_explicitness":
        "O_NOFOLLOW/dir_fd is POSIX-only",
    "tests/catalog/test_environment_compiler.py::test_private_compiler_rejects_explicit_record_for_dependency_free_environment":
        "O_NOFOLLOW/dir_fd is POSIX-only",
    "tests/catalog/test_environment_compiler.py::test_private_compiler_cleans_stage_after_capture_failure":
        "O_NOFOLLOW/dir_fd is POSIX-only",
    "tests/catalog/test_environment_compiler.py::test_private_compiler_accepts_manifest_at_one_mib_limit":
        "O_NOFOLLOW/dir_fd is POSIX-only",
    "tests/catalog/test_environment_compiler.py::test_private_compiler_stages_exact_bytes_and_uses_locked_no_install":
        "O_NOFOLLOW/dir_fd is POSIX-only",
    "tests/catalog/test_environment_compiler.py::test_public_compiler_opens_verified_host_and_compiles_target":
        "O_NOFOLLOW/dir_fd is POSIX-only",
    "tests/catalog/test_environment_compiler.py::test_verified_x86_host_handle_compiles_arm_target_lock":
        "O_NOFOLLOW/dir_fd is POSIX-only",
    # Parametrized tests with massive parameter IDs (hundreds of KB of x's)
    # exceed Windows' 32767-char environment variable limit during test
    # ID generation
    "tests/catalog/test_environment_compiler.py::test_lock_v7_requires_bounded_bytes":
        "parametrized ID exceeds Windows env var length limit",
    "tests/catalog/test_environment_compiler.py::test_private_compiler_requires_exact_bounded_manifest_bytes":
        "parametrized ID exceeds Windows env var length limit",
}

# Bulk inventory generated from a Windows full-suite run (see
# tests/windows_skip_inventory.py header for the regeneration contract).
_inv_path = Path(__file__).parent / "windows_skip_inventory.py"
if _inv_path.is_file():
    _spec = importlib.util.spec_from_file_location("windows_skip_inventory", _inv_path)
    _inv = importlib.util.module_from_spec(_spec)
    _spec.loader.exec_module(_inv)
    _WINDOWS_SKIP_MODULES.update(_inv.WINDOWS_SKIP_MODULES)
    _WINDOWS_SKIP_TESTS.update(_inv.WINDOWS_SKIP_TESTS)


# Modules to skip entirely when an optional import is unavailable (the

# system `scripts` package can shadow the repo's scripts/ directory on some
# Python installs, pulling in gguf → sentencepiece, which is not installed).
try:
    import scripts.build_catalog_ledger  # noqa: F401
except ImportError:
    # Handled by tests/catalog/conftest.py (collect_ignore_glob is
    # directory-scoped: it only works from the conftest in the same
    # directory as the module being ignored).
    pass


def pytest_collection_modifyitems(items: list) -> None:
    """Skip Windows-incompatible tests without editing any test file."""
    if not _IS_WINDOWS:
        return

    for item in items:
        # Normalise the path separator for matching
        path = str(item.fspath).replace("\\", "/")
        # Try both forward-slash and the module path relative to repo root
        for module_path, reason in _WINDOWS_SKIP_MODULES.items():
            if path.endswith(module_path.replace("tests/", "tests/")):
                item.add_marker(pytest.mark.skip(reason=reason))
                break
        else:
            # Check individual test-level skips
            for test_id, reason in _WINDOWS_SKIP_TESTS.items():
                module, test_name = test_id.split("::", 1)
                if path.endswith(module) and item.name == test_name:
                    item.add_marker(pytest.mark.skip(reason=reason))
                    break
