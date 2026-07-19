from __future__ import annotations

from bionodulo.nodes.builtin.protein_database_family import (
    AlphaFoldDBNode,
    AlphaFoldNode,
    PDBDownloadNode,
    PDBRetrieveNode,
    UniProtRetrieveNode,
    UniProtSearchNode,
)
from bionodulo.nodes.builtin.protein_database_family.alphafold_db import (
    ALPHAFOLD_OPENAPI_SHA256,
)
from bionodulo.nodes.builtin.protein_database_family.rcsb_pdb import RCSB_OPENAPI_SHA256
from bionodulo.nodes.builtin.protein_database_family.uniprot import (
    UNIPROT_QUERY_HELP_SHA256,
    UNIPROT_RETRIEVE_HELP_SHA256,
)


def test_authoritative_api_snapshots_are_pinned() -> None:
    assert AlphaFoldDBNode.VERSION == "1.0.0"
    assert AlphaFoldDBNode.SOURCE_SHA256 == ALPHAFOLD_OPENAPI_SHA256
    assert PDBDownloadNode.VERSION == "1.56.1"
    assert PDBDownloadNode.SOURCE_SHA256 == RCSB_OPENAPI_SHA256
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


def test_legacy_facades_resolve_to_focused_owners() -> None:
    from bionodulo.nodes.builtin import alphafold, rcsb_pdb, uniprot

    assert uniprot.UniProtSearchNode is UniProtSearchNode
    assert uniprot.UniProtRetrieveNode is UniProtRetrieveNode
    assert rcsb_pdb.PDBDownloadNode is PDBDownloadNode
    assert rcsb_pdb.PDBRetrieveNode is PDBRetrieveNode
    assert alphafold.AlphaFoldDBNode is AlphaFoldDBNode
    assert alphafold.AlphaFoldNode is AlphaFoldNode
    assert alphafold._LegacyAlphaFoldDBNode.NODE_ID == ""
    assert alphafold._LegacyAlphaFoldNode.NODE_ID == ""
