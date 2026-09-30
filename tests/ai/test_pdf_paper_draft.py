"""Uploaded papers must contain bounded, readable evidence before drafting."""
from __future__ import annotations

import base64
from io import BytesIO

import pytest

from bionodulo.ai import assistant
from bionodulo.ai.runtime import ModelTurn


def _pdf(*pages: str) -> bytes:
    """Make a small searchable PDF without depending on a test-only renderer."""
    objects = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [" + b" ".join(f"{4 + 2 * i} 0 R".encode() for i in range(len(pages)))
        + f"] /Count {len(pages)} >>".encode(),
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
    ]
    for i, text in enumerate(pages):
        encoded = text.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)").encode("ascii")
        stream = b"BT /F1 12 Tf 72 720 Td (" + encoded + b") Tj ET"
        objects.append(b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Resources "
                       + b"<< /Font << /F1 3 0 R >> >> " + f"/Contents {5 + 2 * i} 0 R >>".encode())
        objects.append(f"<< /Length {len(stream)} >>\nstream\n".encode() + stream + b"\nendstream")
    out = BytesIO()
    out.write(b"%PDF-1.4\n")
    offsets = [0]
    for number, body in enumerate(objects, 1):
        offsets.append(out.tell())
        out.write(f"{number} 0 obj\n".encode() + body + b"\nendobj\n")
    xref = out.tell()
    out.write(f"xref\n0 {len(objects) + 1}\n0000000000 65535 f \n".encode())
    for offset in offsets[1:]:
        out.write(f"{offset:010} 00000 n \n".encode())
    out.write(f"trailer\n<< /Size {len(objects) + 1} /Root 1 0 R >>\nstartxref\n{xref}\n%%EOF".encode())
    return out.getvalue()


def _attachment(data: bytes) -> list[dict[str, str]]:
    return [{"name": "paper.pdf", "mime_type": "application/pdf",
             "content": "data:application/pdf;base64," + base64.b64encode(data).decode()}]


def test_pdf_extractor_prioritizes_late_methods_and_marks_excerpt() -> None:
    introduction = "This paper studies count data and biological variation. " * 160
    methods = "Materials and methods. We normalize a count matrix with sample design metadata. " * 8
    text = assistant._extract_pdf_text(_attachment(_pdf(introduction, "Materials and methods\n" + methods))[0]["content"],
                                       max_chars=1000)
    assert text is not None
    assert "sample design metadata" in text
    assert "PDF excerpt truncated" in text


@pytest.mark.asyncio
async def test_unreadable_pdf_fails_before_model(monkeypatch: pytest.MonkeyPatch) -> None:
    async def forbidden_model(**_kwargs):
        raise AssertionError("Unreadable PDF must not reach the model")

    monkeypatch.setattr(assistant, "_call_llm", forbidden_model)
    response = await assistant.chat_with_tools("Please draft from this paper", workflow=None, history=[],
                                               api_key="test", files=_attachment(_pdf("")))
    assert response.steps[-1].type == "error"
    assert "searchable PDF" in response.steps[-1].content


@pytest.mark.asyncio
async def test_uploaded_searchable_pdf_reaches_model_as_untrusted_source(monkeypatch: pytest.MonkeyPatch) -> None:
    received = []

    async def model(**kwargs):
        received.append(kwargs["messages"])
        return ModelTurn("Draft only; source does not supply local input files or a contrast.")

    monkeypatch.setattr(assistant, "_call_llm", model)
    paper = _pdf("This method uses a count matrix and sample design metadata. " * 5)
    response = await assistant.chat_with_tools("Draft from this attached paper", workflow=None, history=[],
                                               api_key="test", files=_attachment(paper))
    assert "Draft only" in response.reply
    assert "Untrusted PDF source text" in str(received[0])
    assert "count matrix and sample design metadata" in str(received[0])


def test_pdf_size_and_page_bounds() -> None:
    assert assistant._extract_pdf_text(_attachment(b"%PDF-" + b"x" * (assistant.MAX_PDF_BYTES + 1))[0]["content"]) is None
    many_pages = _pdf(*(["A readable page with sufficient scientific method details. " * 4]
                        * (assistant.MAX_PDF_PAGES + 1)))
    assert assistant._extract_pdf_text(_attachment(many_pages)[0]["content"]) is None
