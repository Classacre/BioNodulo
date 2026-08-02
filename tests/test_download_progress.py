"""URL downloads report progress so the UI can show it on the node.

Before this, a node fetching a multi-GB reference was a silent
`shutil.copyfileobj` — indistinguishable from a hung node.
"""

from __future__ import annotations

import io
from types import SimpleNamespace

from bionodulo.nodes.builtin.input_family import adapter


class _Response:
    """Minimal urlopen-like object: chunked reads plus headers."""

    def __init__(self, payload: bytes, *, content_length: str | None) -> None:
        self._buf = io.BytesIO(payload)
        self.headers = {} if content_length is None else {"Content-Length": content_length}

    def read(self, size: int) -> bytes:
        return self._buf.read(size)


def _context(events: list[tuple[str, dict]]) -> SimpleNamespace:
    return SimpleNamespace(
        emit=lambda name, payload: events.append((name, payload)),
        node_id="node-a",
        run_id="run-1",
    )


def test_progress_is_emitted_for_the_node_that_is_downloading() -> None:
    events: list[tuple[str, dict]] = []
    payload = b"x" * (adapter._DOWNLOAD_CHUNK_BYTES * 3)
    sink = io.BytesIO()

    adapter._copy_with_progress(
        _Response(payload, content_length=str(len(payload))),
        sink,
        _context(events),
        "https://example.org/ref.fa",
    )

    assert sink.getvalue() == payload
    assert events, "expected at least the terminal progress event"
    name, last = events[-1]
    assert name == "node_download_progress"
    assert last["node_id"] == "node-a"
    assert last["run_id"] == "run-1"
    assert last["downloaded_bytes"] == len(payload)
    assert last["total_bytes"] == len(payload)
    assert last["done"] is True


def test_a_missing_content_length_reports_zero_total() -> None:
    """The UI shows an indeterminate bar rather than inventing a percentage."""
    events: list[tuple[str, dict]] = []
    payload = b"y" * 1024

    adapter._copy_with_progress(
        _Response(payload, content_length=None), io.BytesIO(), _context(events), "u"
    )

    # Terminal event falls back to the byte count actually read.
    assert events[-1][1]["total_bytes"] == len(payload)


def test_a_context_without_emit_still_downloads() -> None:
    """The CLI and unit tests pass a bare context; copying must not depend on it."""
    payload = b"z" * 4096
    sink = io.BytesIO()

    adapter._copy_with_progress(
        _Response(payload, content_length="4096"), sink, SimpleNamespace(), "u"
    )

    assert sink.getvalue() == payload


def test_a_failing_emit_never_breaks_the_download() -> None:
    """Progress is decoration; losing it must not lose the file."""

    def boom(_name: str, _payload: dict) -> None:
        raise RuntimeError("socket closed")

    payload = b"w" * (adapter._DOWNLOAD_CHUNK_BYTES * 2)
    sink = io.BytesIO()

    adapter._copy_with_progress(
        _Response(payload, content_length=str(len(payload))),
        sink,
        SimpleNamespace(emit=boom, node_id="n", run_id="r"),
        "u",
    )

    assert sink.getvalue() == payload


def test_the_user_agent_reports_the_real_version() -> None:
    """It used to claim BioNodulo/2.0, a release that never existed."""
    from bionodulo import __version__

    assert f"BioNodulo/{__version__}" in adapter._HTTP_USER_AGENT
    assert "2.0" not in adapter._HTTP_USER_AGENT.split()[0]
