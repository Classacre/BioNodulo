"""Papers reach the model as Markdown, because tables carry the method.

Accession lists, tool versions and parameter values live in tables. A
page-by-page text dump interleaves their cells into prose, so the model reads
"HISAT2 2.2.2 DESeq2 1.50.2" as a sentence and loses which version belongs to
which tool. Markdown keeps the rows.
"""

from __future__ import annotations

import pytest

from bionodulo.ai import papers

HTML_PAPER = b"""<html><body>
<h1>Nodulation RNA-seq</h1>
<h2>Methods</h2>
<p>Reads were trimmed and aligned.</p>
<table><tr><th>Tool</th><th>Version</th></tr>
<tr><td>HISAT2</td><td>2.2.2</td></tr>
<tr><td>DESeq2</td><td>1.50.2</td></tr></table>
</body></html>"""

requires_markitdown = pytest.mark.skipif(
    not papers.markitdown_available(), reason="markitdown is an optional dependency"
)


@requires_markitdown
def test_headings_survive_conversion() -> None:
    markdown = papers.to_markdown(HTML_PAPER, filename="paper.html")

    assert markdown is not None
    assert "## Methods" in markdown


@requires_markitdown
def test_tables_survive_conversion() -> None:
    """The whole point: a row keeps its tool next to its version."""
    markdown = papers.to_markdown(HTML_PAPER, filename="paper.html")

    assert markdown is not None
    assert "| HISAT2 | 2.2.2 |" in markdown
    assert "| DESeq2 | 1.50.2 |" in markdown


@requires_markitdown
def test_output_is_capped() -> None:
    markdown = papers.to_markdown(HTML_PAPER, filename="paper.html", max_chars=20)

    assert markdown is not None
    assert len(markdown) <= 20


def test_empty_input_converts_to_nothing() -> None:
    assert papers.to_markdown(b"") is None


def test_unconvertible_input_returns_none_rather_than_raising() -> None:
    """Conversion is an improvement, never a gate: a file markitdown cannot read
    must fall through to plain text extraction, not fail the analysis."""
    assert papers.to_markdown(b"\x00\x01not a document", filename="paper.pdf") is None


@pytest.mark.parametrize(
    ("filename", "expected"),
    [
        ("paper.pdf", ".pdf"),
        ("paper.DOCX", ".docx"),
        ("archive.tar.gz", ".gz"),
        ("noextension", ".pdf"),
    ],
)
def test_the_extension_selects_the_converter(filename: str, expected: str) -> None:
    assert papers._extension(filename) == expected
