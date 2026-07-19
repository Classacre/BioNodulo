from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from bionodulo.environments.constants import EXECUTABLE_TO_CONDA_PACKAGE, PACKAGE_MIN_VERSIONS
from bionodulo.nodes.builtin.proteomics_family.percolator import PercolatorNode
from bionodulo.nodes.builtin.proteomics_family.sage_search import SageSearchNode
from bionodulo.nodes.registry import NodeRegistry


def test_focused_proteomics_nodes_are_source_pinned_and_discoverable() -> None:
    registry = NodeRegistry.create_isolated()
    registry.load_builtin_nodes()

    assert registry.get("sage_search") is SageSearchNode
    assert SageSearchNode.VERSION == "0.14.7"
    assert SageSearchNode.GIT_COMMIT == "99407db6e3754b31a9b88b7316a0aee67293c93f"
    assert registry.get("percolator") is PercolatorNode
    assert PercolatorNode.VERSION == "3.7.1"
    assert PercolatorNode.GIT_COMMIT == "310f92447357d6cb5132b4ee25f7640d7cff9eda"
    assert EXECUTABLE_TO_CONDA_PACKAGE["sage"] == "sage-proteomics"
    assert PACKAGE_MIN_VERSIONS["sage-proteomics"] == "0.14.7"
    assert EXECUTABLE_TO_CONDA_PACKAGE["percolator"] == "percolator"
    assert PACKAGE_MIN_VERSIONS["percolator"] == "3.7.1"


def test_sage_prepares_native_config_command_and_outputs(tmp_path: Path) -> None:
    inputs = {
        "spectra_files": ["run-a.mzML", "run-b.mgf"],
        "fasta_db": "target-decoy.fasta",
        "precursor_tol_ppm": 20.0,
        "fragment_tol_da": 0.05,
        "batch_size": 2,
        "missed_cleavages": 2,
        "min_peptide_length": 7,
        "max_peptide_length": 40,
        "decoy_tag": "DECOY_",
        "generate_decoys": False,
    }
    outputs = SageSearchNode.PLAN_OUTPUTS(inputs, tmp_path)
    SageSearchNode.PREPARE_EXECUTION(inputs, outputs)

    assert [path.name for path in outputs] == [
        "results.sage.tsv",
        "results.json",
        "sage_config.json",
        "results.sage.pin",
    ]
    assert SageSearchNode.render_command(inputs) == [
        "sage",
        "--batch-size",
        "2",
        str(outputs[2]),
    ]
    config = json.loads(outputs[2].read_text(encoding="utf-8"))
    assert config == {
        "database": {
            "decoy_tag": "DECOY_",
            "enzyme": {
                "c_terminal": True,
                "cleave_at": "KR",
                "max_len": 40,
                "min_len": 7,
                "missed_cleavages": 2,
                "restrict": "P",
                "semi_enzymatic": False,
            },
            "fasta": "target-decoy.fasta",
            "generate_decoys": False,
        },
        "fragment_tol": {"da": [-0.05, 0.05]},
        "mzml_paths": ["run-a.mzML", "run-b.mgf"],
        "output_directory": str(outputs[0].parent),
        "precursor_tol": {"ppm": [-20.0, 20.0]},
        "write_pin": True,
    }


@pytest.mark.parametrize(
    ("inputs", "message"),
    [
        (
            {"spectra_files": [], "fasta_db": "db.fa", "precursor_tol_ppm": 20.0, "fragment_tol_da": 0.05},
            "at least one",
        ),
        (
            {"spectra_files": ["a.mzML"], "fasta_db": "db.fa", "precursor_tol_ppm": 20.0, "fragment_tol_da": 0.05, "batch_size": 0},
            "at least 1",
        ),
        (
            {"spectra_files": ["a.mzML"], "fasta_db": "db.fa", "precursor_tol_ppm": 20.0, "fragment_tol_da": 0.05, "min_peptide_length": 51, "max_peptide_length": 50},
            "must not exceed",
        ),
    ],
)
def test_sage_rejects_invalid_source_values(inputs: dict[str, Any], message: str) -> None:
    assert message in str(SageSearchNode.VALIDATE_INPUTS(inputs))


def test_percolator_renders_native_tabular_output_flags(tmp_path: Path) -> None:
    inputs = {
        "pin_file": "results.sage.pin",
        "fasta_db": "target-decoy.fasta",
        "search_input": "concatenated",
        "decoy_prefix": "DECOY_",
        "test_fdr": 0.01,
        "train_fdr": 0.02,
        "protein_enzyme": "trypsin",
        "output": "/work/percolator",
    }
    command = PercolatorNode.render_command(inputs)
    assert command == [
        "percolator",
        "--results-psms",
        "/work/percolator/percolator_psms.tsv",
        "--picked-protein",
        "target-decoy.fasta",
        "--results-proteins",
        "/work/percolator/percolator_proteins.tsv",
        "--protein-decoy-pattern",
        "DECOY_",
        "--protein-enzyme",
        "trypsin",
        "--testFDR",
        "0.01",
        "--trainFDR",
        "0.02",
        "--search-input",
        "concatenated",
        "results.sage.pin",
    ]
    assert "-X" not in command
    assert "--protein-fdr" not in command
    assert PercolatorNode.PLAN_OUTPUTS(inputs, tmp_path) == [
        tmp_path / "percolator" / "percolator_psms.tsv",
        tmp_path / "percolator" / "percolator_proteins.tsv",
    ]


@pytest.mark.parametrize(
    ("inputs", "message"),
    [
        ({"pin_file": "", "fasta_db": "db.fa"}, "pin_file"),
        ({"pin_file": "a.pin", "fasta_db": "db.fa", "search_input": "paired"}, "search_input"),
        ({"pin_file": "a.pin", "fasta_db": "db.fa", "test_fdr": 1.1}, "at most 1"),
    ],
)
def test_percolator_rejects_invalid_source_values(inputs: dict[str, Any], message: str) -> None:
    assert message in str(PercolatorNode.VALIDATE_INPUTS(inputs))
