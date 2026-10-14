from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

from bionodulo.manager.example_data import EXAMPLE_DATA_MANIFEST


ROOT = Path(__file__).resolve().parents[1]


def _workflow(name: str) -> dict:
    return json.loads((ROOT / "templates" / f"{name}.json").read_text(encoding="utf-8"))


def _note(workflow: dict) -> str:
    return next(node["params"]["text"] for node in workflow["nodes"] if node["type"] == "note")


def test_assembly_inputs_retain_the_fully_verified_matched_plasmid_fixture() -> None:
    evidence = json.loads((Path(__file__).parent / "fixtures" / "assembly_source_verification.json").read_text())
    files = {entry["file"]: entry for entry in evidence["files"]}
    workflow = _workflow("assembly_pipeline")
    nodes = {node["id"]: node for node in workflow["nodes"]}
    assert nodes["reads_001"]["params"]["reads"] == [files["R1.fq.gz"]["url"], files["R2.fq.gz"]["url"]]
    assert nodes["ref_001"]["params"]["reference"] == files["test.fna"]["url"]
    assert evidence["paired_headers_match"] is True
    accession = files["test.fna"]["header"].split()[0]
    for name in ("R1.fq.gz", "R2.fq.gz"):
        assert accession in files[name]["first_header"]
        assert files[name]["reads_with_exact_reference_31mer"] / files[name]["records"] > 0.99
    assert accession in _note(workflow)
    assert "plasmid" in _note(workflow)


def test_assembly_manifest_can_materialize_the_same_compressed_pair_and_reference() -> None:
    manifest = {item.filename: item for item in EXAMPLE_DATA_MANIFEST if item.category == "assembly"}
    nodes = {node["id"]: node for node in _workflow("assembly_pipeline")["nodes"]}
    assert [manifest["R1.fq"].url, manifest["R2.fq"].url] == nodes["reads_001"]["params"]["reads"]
    assert manifest["R1.fq"].gunzip and manifest["R2.fq"].gunzip
    assert manifest["reference.fna"].url == nodes["ref_001"]["params"]["reference"]


@pytest.mark.parametrize("name", ["rna_seq_pipeline", "differential_expression"])
def test_rna_template_notes_name_their_actual_read_accession(name: str) -> None:
    workflow = _workflow(name)
    reads = next(node["params"]["reads"] for node in workflow["nodes"] if node["type"] == "input_fastq")
    accessions = {re.search(r"SRR\d+", source).group() for source in reads}
    assert len(accessions) == 1
    assert next(iter(accessions)) in _note(workflow)


def test_deseq_note_identifies_the_real_airway_inputs() -> None:
    workflow = _workflow("deseq2_differential_expression")
    sources = [entry.url for entry in EXAMPLE_DATA_MANIFEST if entry.category == "deseq2"]
    assert all("airway" in source for source in sources)
    assert "airway" in _note(workflow)
    assert "simulated" not in _note(workflow).lower()


def test_proteomics_note_matches_the_enabled_decoy_generation() -> None:
    workflow = _workflow("proteomics_sage_percolator_pipeline")
    sage = next(node for node in workflow["nodes"] if node["type"] == "sage_search")
    assert sage["params"]["generate_decoys"] is True
    assert "target-only" in _note(workflow)
    assert sage["params"]["decoy_tag"] in _note(workflow)
