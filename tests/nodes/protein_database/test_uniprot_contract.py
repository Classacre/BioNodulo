from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from bionodulo.nodes.builtin.protein_database_family import uniprot


@pytest.mark.parametrize(
    ("database", "output_format", "is_valid"),
    [
        ("uniprotkb", "gff", True),
        ("uniref", "rdf", True),
        ("uniparc", "fasta", True),
        ("uniref", "gff", False),
        ("uniparc", "gff", False),
    ],
)
def test_search_formats_are_database_specific(
    database: str,
    output_format: str,
    is_valid: bool,
) -> None:
    validation = uniprot.UniProtSearchNode.VALIDATE_INPUTS(
        {"query": "protein_name:p53", "database": database, "format": output_format}
    )

    assert (validation is True) is is_valid
    if not is_valid:
        assert f"format' for {database}" in str(validation)


@pytest.mark.parametrize("restricted_input", ["reviewed_only", "include_isoform"])
def test_uniprotkb_only_search_flags_are_rejected_for_other_databases(
    restricted_input: str,
) -> None:
    validation = uniprot.UniProtSearchNode.VALIDATE_INPUTS(
        {
            "query": "identity:0.9",
            "database": "uniref",
            restricted_input: True,
        }
    )

    assert "supported only for database 'uniprotkb'" in str(validation)


@pytest.mark.asyncio
@pytest.mark.parametrize("database", ["uniref", "uniparc"])
async def test_non_uniprotkb_search_omits_uniprotkb_only_parameters(
    database: str,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    calls: list[tuple[str, dict[str, Any] | None]] = []

    async def fake_json(
        resource: str,
        *,
        params: dict[str, Any] | None = None,
        **_: Any,
    ) -> dict[str, Any]:
        calls.append((resource, params))
        return {"results": []}

    monkeypatch.setattr(uniprot, "_request_json", fake_json)

    await uniprot.UniProtSearchNode().run(
        query="identity:0.9",
        database=database,
        fields="accession,id",
        context=SimpleNamespace(node_dir=tmp_path),
    )

    assert calls == [
        (
            f"{database}/search",
            {"query": "identity:0.9", "format": "json", "size": 25},
        )
    ]


def test_search_size_alias_has_deterministic_precedence() -> None:
    assert uniprot._resolve_search_size({}) == 25
    assert uniprot._resolve_search_size({"max_results": 8}) == 8
    assert uniprot._resolve_search_size({"max_results": 25, "size": 7}) == 7
    assert uniprot._resolve_search_size({"max_results": 7, "size": 7}) == 7

    with pytest.raises(ValueError, match="must not conflict"):
        uniprot._resolve_search_size({"max_results": 8, "size": 7})


@pytest.mark.asyncio
async def test_retrieve_isoforms_uses_search_and_combines_fasta(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    calls: list[tuple[str, dict[str, Any] | None]] = []

    async def fake_json(
        resource: str,
        *,
        params: dict[str, Any] | None = None,
        **_: Any,
    ) -> dict[str, Any]:
        calls.append((resource, params))
        return {
            "results": [
                {"primaryAccession": "P04637", "uniProtkbId": "P53_HUMAN"},
                {"primaryAccession": "P04637-2", "uniProtkbId": "P53_HUMAN"},
            ]
        }

    async def fake_text(
        resource: str,
        *,
        params: dict[str, Any] | None = None,
        **_: Any,
    ) -> str:
        calls.append((resource, params))
        return ">sp|P04637|P53_HUMAN\nMSEQ\n>sp|P04637-2|P53_HUMAN\nMISEQ\n"

    monkeypatch.setattr(uniprot, "_request_json", fake_json)
    monkeypatch.setattr(uniprot, "_request_text", fake_text)

    result = await uniprot.UniProtRetrieveNode().run(
        uniprot_ids="P04637",
        include_isoform=True,
        include_fasta=True,
        context=SimpleNamespace(node_dir=tmp_path),
    )

    data = result["outputs"]["protein_data"]
    assert data["record_count"] == 2
    assert data["retrieved_accessions"] == ["P04637", "P04637-2"]
    assert Path(result["outputs"]["sequence"]).read_text(encoding="utf-8") == (
        ">sp|P04637|P53_HUMAN\nMSEQ\n>sp|P04637-2|P53_HUMAN\nMISEQ\n"
    )
    assert calls == [
        (
            "uniprotkb/search",
            {
                "query": "accession:P04637",
                "format": "json",
                "size": 500,
                "includeIsoform": "true",
            },
        ),
        (
            "uniprotkb/search",
            {
                "query": "accession:P04637",
                "format": "fasta",
                "size": 500,
                "includeIsoform": "true",
            },
        ),
    ]


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("inputs", "expects_fasta"),
    [
        ({"format": "json"}, False),
        ({"format": "fasta"}, True),
        ({"format": "json", "include_fasta": True}, True),
        ({"format": "fasta", "include_fasta": False}, False),
    ],
)
async def test_hidden_legacy_retrieve_format_only_controls_fasta_when_unspecified(
    inputs: dict[str, Any],
    expects_fasta: bool,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    text_calls: list[str] = []

    async def fake_json(resource: str, **_: Any) -> dict[str, Any]:
        return {"primaryAccession": "P04637", "uniProtkbId": "P53_HUMAN"}

    async def fake_text(resource: str, **_: Any) -> str:
        text_calls.append(resource)
        return ">sp|P04637|P53_HUMAN\nMSEQ\n"

    monkeypatch.setattr(uniprot, "_request_json", fake_json)
    monkeypatch.setattr(uniprot, "_request_text", fake_text)

    result = await uniprot.UniProtRetrieveNode().run(
        uniprot_ids="P04637",
        context=SimpleNamespace(node_dir=tmp_path),
        **inputs,
    )

    assert bool(result["outputs"]["sequence"]) is expects_fasta
    assert bool(text_calls) is expects_fasta
