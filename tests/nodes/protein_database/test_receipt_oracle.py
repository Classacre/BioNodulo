"""Independent oracle for the retained local queue run receipt.

This is deliberately *not* a re-run of the nodes. It checks the artifacts the
run produced against external ground truth and against each other, so a node
that wrote a plausible-looking but wrong file fails.

External ground truth used:

* UniProt ``P04637`` (``P53_HUMAN``, Cellular tumor antigen p53, *Homo sapiens*)
  is the canonical 393-residue TP53 protein.
* Its N-terminus begins ``MEEPQSDPSVEPPLSQETFSDLW``.
* AlphaFold DB model for P04637 is keyed ``AF-P04637-F1``.
* RCSB PDB entry ``4HHB`` is human deoxyhaemoglobin.

The workflow under test searched UniProt for "tp53", retrieved the sequence,
fetched the AlphaFold model plus its predicted aligned error, and downloaded a
PDB structure. The three sequence-bearing artifacts (FASTA, search TSV, PAE
matrix) are produced by *different* nodes, so agreement between them is a real
consistency check rather than one node confirming itself.

These tests skip when the receipt is absent. The receipt is retained evidence
under ``reports/run-receipts/``; a checkout without it has nothing to verify,
which is different from a passing run.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[3]
RECEIPT_DIR = REPO_ROOT / "reports" / "run-receipts" / "protein-structure-db"
RUN_ROOT = RECEIPT_DIR / "workspace" / "runs" / "receipt-protein_structure_database_workflow"

CANONICAL_TP53_ACCESSION = "P04637"
CANONICAL_TP53_LENGTH = 393
CANONICAL_TP53_N_TERMINUS = "MEEPQSDPSVEPPLSQETFSDLW"

pytestmark = pytest.mark.skipif(
    not (RECEIPT_DIR / "receipt.json").is_file(),
    reason="retained run receipt not present in this checkout",
)


@pytest.fixture(scope="module")
def receipt() -> dict:
    return json.loads((RECEIPT_DIR / "receipt.json").read_text(encoding="utf-8"))


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def test_run_completed_without_environment_provisioning(receipt: dict) -> None:
    assert receipt["status"] == "completed"
    # A pure-Python workflow must not have needed an external environment. If it
    # ever does, this receipt no longer demonstrates host-independent execution.
    assert receipt["environment"]["required"] is False
    assert receipt["environment"]["status"] == "not_required"
    assert receipt["node_errors"] == {}


def test_every_recorded_artifact_hash_matches_disk(receipt: dict) -> None:
    assert receipt["artifact_count"] > 0
    for artifact in receipt["artifacts"]:
        path = RECEIPT_DIR / artifact["path"]
        assert path.is_file(), f"recorded artifact missing: {artifact['path']}"
        assert path.stat().st_size == artifact["bytes"], artifact["path"]
        assert _sha256(path) == artifact["sha256"], artifact["path"]


def _read_fasta(path: Path) -> tuple[str, str]:
    header = ""
    chunks: list[str] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.startswith(">"):
            header = header or line[1:].strip()
        else:
            chunks.append(line.strip())
    return header, "".join(chunks)


def test_retrieved_sequence_is_canonical_human_tp53() -> None:
    fasta = RUN_ROOT / "uniprot_retrieve_001" / "uniprot_retrieve" / "tp53.fasta"
    header, sequence = _read_fasta(fasta)
    assert CANONICAL_TP53_ACCESSION in header
    assert "TP53" in header
    assert "Homo sapiens" in header
    assert len(sequence) == CANONICAL_TP53_LENGTH
    assert sequence.startswith(CANONICAL_TP53_N_TERMINUS)
    # A protein, not a nucleotide record.
    assert set(sequence) <= set("ACDEFGHIKLMNPQRSTVWYBXZJUO*")


def test_search_table_agrees_with_retrieved_sequence() -> None:
    """Cross-artifact check: a different node produced this table."""
    tsv = RUN_ROOT / "uniprot_search_001" / "uniprot_search" / "tp53_uniprot.tsv"
    lines = tsv.read_text(encoding="utf-8").splitlines()
    header = lines[0].split("\t")
    rows = [dict(zip(header, line.split("\t"), strict=False)) for line in lines[1:] if line.strip()]
    assert rows, "search returned no rows"
    match = next((row for row in rows if row.get("accession") == CANONICAL_TP53_ACCESSION), None)
    assert match is not None, "canonical accession absent from search results"
    assert match["entry_name"] == "P53_HUMAN"
    assert match["gene_names"].split(";")[0] == "TP53"
    # The search table's independently reported length must equal the FASTA length.
    assert int(match["sequence_length"]) == CANONICAL_TP53_LENGTH


def test_predicted_aligned_error_is_consistent_with_sequence_length() -> None:
    pae_path = RUN_ROOT / "alphafold_db_001" / "alphafold_db" / "P04637_pae.json"
    payload = json.loads(pae_path.read_text(encoding="utf-8"))
    assert isinstance(payload, list) and len(payload) == 1
    block = payload[0]
    matrix = block["predicted_aligned_error"]
    assert len(matrix) == CANONICAL_TP53_LENGTH
    assert all(len(row) == CANONICAL_TP53_LENGTH for row in matrix)
    assert block["max_predicted_aligned_error"] > 0
    # Diagonal is self-alignment: must be exactly zero.
    assert all(matrix[index][index] == 0 for index in range(len(matrix)))


def test_structure_files_carry_their_expected_entry_identifiers() -> None:
    alphafold_cif = RUN_ROOT / "alphafold_db_001" / "alphafold_db" / "P04637.cif"
    text = alphafold_cif.read_text(encoding="utf-8", errors="replace")[:4000]
    assert "AF-P04637-F1" in text

    pdb_cif = RUN_ROOT / "pdb_download_001" / "pdb_download" / "4HHB.cif"
    pdb_text = pdb_cif.read_text(encoding="utf-8", errors="replace")[:4000]
    assert "data_4HHB" in pdb_text
    assert "mmcif" in pdb_text.lower()
