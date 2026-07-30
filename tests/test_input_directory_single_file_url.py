"""A directory input pointed at a single-file URL must still work.

Dorado takes a POD5 *directory*, but the public test dataset is published as one
`.pod5` file. Before this, such a URL downloaded fine and then failed validation
with "Expected a directory input, got file" -- pressuring the file to be
committed to the repo instead of fetched from its real source.
"""

from __future__ import annotations

from pathlib import Path

from bionodulo.nodes.builtin.input_family import adapter


def test_a_downloaded_file_is_wrapped_in_a_directory(tmp_path: Path) -> None:
    downloaded = tmp_path / "test.pod5"
    downloaded.write_bytes(b"POD5-ish")

    wrapper = adapter._wrap_file_in_directory(downloaded)

    assert wrapper.is_dir()
    assert (wrapper / "test.pod5").is_file()
    assert (wrapper / "test.pod5").read_bytes() == b"POD5-ish"


def test_wrapping_is_idempotent(tmp_path: Path) -> None:
    """Re-running a workflow reuses the URL cache, so this runs again."""
    downloaded = tmp_path / "test.pod5"
    downloaded.write_bytes(b"x")

    first = adapter._wrap_file_in_directory(downloaded)
    second = adapter._wrap_file_in_directory(downloaded)

    assert first == second
    assert [p.name for p in sorted(second.iterdir())] == ["test.pod5"]


def test_the_wrapper_does_not_shadow_the_original(tmp_path: Path) -> None:
    downloaded = tmp_path / "test.pod5"
    downloaded.write_bytes(b"x")

    wrapper = adapter._wrap_file_in_directory(downloaded)

    assert downloaded.is_file(), "the cached download must survive wrapping"
    assert wrapper != downloaded


def test_a_local_file_path_still_fails_for_a_directory_input(tmp_path: Path) -> None:
    """Wrapping is URL-only: a local file here is a mistake, not an intent."""
    from bionodulo.nodes.builtin.input_family.directory import InputDirectoryNode

    a_file = tmp_path / "not_a_dir.txt"
    a_file.write_text("x", encoding="utf-8")

    try:
        InputDirectoryNode._validate_resolved_source(a_file)
    except ValueError as exc:
        assert "got file" in str(exc)
    else:  # pragma: no cover - the guard must stay
        raise AssertionError("a local file must not pass a directory input")
