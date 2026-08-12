from __future__ import annotations

from bionodulo.nodes.builtin.protein_database_family import (
    AlphaFoldDBNode,
    PDBDownloadNode,
    UniProtRetrieveNode,
    UniProtSearchNode,
)
from bionodulo.nodes.builtin.protein_database_family.alphafold_db import (
    ALPHAFOLD_OPENAPI_SHA256,
)
from bionodulo.nodes.builtin.protein_database_family.rcsb_pdb import (
    RCSB_OPENAPI_SHA256,
    RCSB_VOLUME_OPENAPI_SHA256,
)
from bionodulo.nodes.builtin.protein_database_family.uniprot import (
    UNIPROT_QUERY_HELP_SHA256,
    UNIPROT_RETRIEVE_HELP_SHA256,
)


def test_authoritative_api_snapshots_are_pinned() -> None:
    assert AlphaFoldDBNode.VERSION == "1.0.0"
    assert AlphaFoldDBNode.SOURCE_SHA256 == ALPHAFOLD_OPENAPI_SHA256
    assert PDBDownloadNode.VERSION == "1.56.1"
    assert PDBDownloadNode.SOURCE_SHA256 == RCSB_OPENAPI_SHA256
    assert PDBDownloadNode.SOURCE_AUTHORITIES["volume_server"] == (
        "https://maps.rcsb.org/openapi.json",
        RCSB_VOLUME_OPENAPI_SHA256,
    )
    assert UniProtSearchNode.VERSION == "2025-12-17"
    assert UniProtSearchNode.SOURCE_SHA256 == UNIPROT_QUERY_HELP_SHA256
    assert UniProtRetrieveNode.SOURCE_SHA256 == UNIPROT_RETRIEVE_HELP_SHA256


def test_template_nodes_have_explicit_validation_contracts() -> None:
    assert "non-empty" in str(UniProtSearchNode.VALIDATE_INPUTS({"query": ""}))
    assert "between 1 and 500" in str(
        UniProtSearchNode.VALIDATE_INPUTS({"query": "protein_name:p53", "max_results": 501})
    )
    assert "at least one" in str(AlphaFoldDBNode.VALIDATE_INPUTS({"uniprot_ids": ""}))
    assert "Invalid four-character PDB ID" in str(
        PDBDownloadNode.VALIDATE_INPUTS({"pdb_ids": "not-an-id", "format": "cif"})
    )

