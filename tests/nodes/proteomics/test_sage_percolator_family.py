from __future__ import annotations

import csv
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
    assert PercolatorNode.GIT_TAG == "rel-3-07-01"
    assert PercolatorNode.GIT_TAG_OBJECT == "93ea589f59bd3293d1b73b10db90ff88a9685840"
    assert PercolatorNode.SOURCE_ARCHIVE_SHA256 == (
        "f1c9833063cb4e99c51a632efc3f80c6b8f48a43fd440ea3eb0968af5c84b97a"
    )
    assert PercolatorNode.PACKAGE_CONSTRAINTS == ("percolator==3.7.1",)
    assert all(PercolatorNode.GIT_COMMIT in url for url in PercolatorNode.SOURCE_URLS)
    assert PercolatorNode.SAGE_COMPATIBILITY_VERSION == "0.14.7"
    assert PercolatorNode.SAGE_COMPATIBILITY_COMMIT == SageSearchNode.GIT_COMMIT
    assert EXECUTABLE_TO_CONDA_PACKAGE["sage"] == "sage-proteomics"
    assert PACKAGE_MIN_VERSIONS["sage-proteomics"] == "0.14.7"
    assert EXECUTABLE_TO_CONDA_PACKAGE["percolator"] == "percolator"
    assert PACKAGE_MIN_VERSIONS["percolator"] == "3.7.1"


def test_sage_prepares_native_config_command_and_outputs(tmp_path: Path) -> None:
    fasta = tmp_path / "target-decoy.fasta"
    fasta.write_text(">target\nPEPTIDE\n>DECOY_target\nEDITPEP\n", encoding="utf-8")
    inputs = {
        "spectra_files": ["run-a.mzML", "run-b.mgf"],
        "fasta_db": str(fasta),
        "precursor_tol_ppm": 20.0,
        "fragment_tol_da": 0.05,
        "precursor_tol_lower_ppm": -500.0,
        "precursor_tol_upper_ppm": 100.0,
        "fragment_tol_lower_da": -0.02,
        "fragment_tol_upper_da": 0.05,
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
        # Sage ignores `write_pin` in the config (skip_serializing, CLI-only), so
        # the PIN only exists when the flag is passed.
        "--write-pin",
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
            "fasta": str(fasta),
            "generate_decoys": False,
        },
        "fragment_tol": {"da": [-0.02, 0.05]},
        "mzml_paths": ["run-a.mzML", "run-b.mgf"],
        "output_directory": str(outputs[0].parent),
        "precursor_tol": {"ppm": [-500.0, 100.0]},
        "write_pin": True,
    }


def test_sage_contract_uses_exact_multiple_file_type_and_documented_defaults() -> None:
    inputs = SageSearchNode.INPUT_TYPES()
    assert inputs["required"]["spectra_files"] == (
        "FILE",
        {"multiple": True, "description": "One or more mzML, mzML.gz, MGF, or Bruker TDF inputs"},
    )
    assert inputs["optional"]["missed_cleavages"][1]["default"] == 1


def test_sage_preserves_symmetric_tolerance_ports(tmp_path: Path) -> None:
    inputs = {
        "spectra_files": ["run.mzML"],
        "fasta_db": "targets.fasta",
        "precursor_tol_ppm": 20.0,
        "fragment_tol_da": 0.05,
        "generate_decoys": True,
    }
    outputs = SageSearchNode.PLAN_OUTPUTS(inputs, tmp_path)
    SageSearchNode.PREPARE_EXECUTION(inputs, outputs)
    config = json.loads(outputs[2].read_text(encoding="utf-8"))
    assert config["precursor_tol"] == {"ppm": [-20.0, 20.0]}
    assert config["fragment_tol"] == {"da": [-0.05, 0.05]}
    assert config["database"]["enzyme"]["missed_cleavages"] == 1


@pytest.mark.parametrize(
    ("contents", "message"),
    [
        (">target\nPEPTIDE\n", "contains no accession with decoy_tag"),
        (">DECOY_empty\n>target\nPEPTIDE\n", "contains no accession with decoy_tag"),
        (">target_empty\n>DECOY_target\nEDITPEP\n", "no target accession"),
    ],
)
def test_sage_rejects_supplied_decoy_mode_without_nonempty_records(
    tmp_path: Path,
    contents: str,
    message: str,
) -> None:
    fasta = tmp_path / "targets-only.fasta"
    fasta.write_text(contents, encoding="utf-8")
    inputs = {
        "spectra_files": ["run.mzML"],
        "fasta_db": str(fasta),
        "precursor_tol_ppm": 20.0,
        "fragment_tol_da": 0.05,
        "decoy_tag": "DECOY_",
        "generate_decoys": False,
    }
    outputs = SageSearchNode.PLAN_OUTPUTS(inputs, tmp_path)
    with pytest.raises(ValueError, match=message):
        SageSearchNode.PREPARE_EXECUTION(inputs, outputs)


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
        (
            {
                "spectra_files": ["a.mzML"],
                "fasta_db": "db.fa",
                "precursor_tol_ppm": 20.0,
                "fragment_tol_da": 0.05,
                "precursor_tol_lower_ppm": -20.0,
            },
            "must be provided together",
        ),
        (
            {
                "spectra_files": ["a.mzML"],
                "fasta_db": "db.fa",
                "precursor_tol_ppm": 20.0,
                "fragment_tol_da": 0.05,
                "fragment_tol_lower_da": 0.1,
                "fragment_tol_upper_da": -0.1,
            },
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
        "pin_dialect": "native",
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


def test_percolator_stages_sage_full_digest_pin_for_picked_protein(tmp_path: Path) -> None:
    source = tmp_path / "results.sage.pin"
    source.write_text(
        "SpecId\tLabel\tScanNr\tln(hyperscore)\tPeptide\tProteins\n"
        "target-1\t1\t1\t12.5\t[+42.0106]-PEPTIDEK-[+17.0027]\tP1;P2\n"
        "decoy-1\t-1\t2\t8.0\tEDITPEPK\tDECOY_P1\n",
        encoding="utf-8",
    )
    inputs: dict[str, Any] = {
        "pin_file": source,
        "fasta_db": tmp_path / "target-decoy.fasta",
        "pin_dialect": "sage_0_14_7_full_digest",
        "search_input": "concatenated",
        "decoy_prefix": "DECOY_",
    }
    outputs = PercolatorNode.PLAN_OUTPUTS(inputs, tmp_path / "run")

    PercolatorNode.PREPARE_EXECUTION(inputs, outputs)

    staged = outputs[0].parent / "sage.percolator.pin"
    assert inputs["pin_file"] == str(staged)
    assert source.read_text(encoding="utf-8").endswith("EDITPEPK\tDECOY_P1\n")
    with staged.open("r", encoding="utf-8", newline="") as handle:
        assert list(csv.reader(handle, delimiter="\t")) == [
            ["SpecId", "Label", "ScanNr", "ln(hyperscore)", "Peptide", "Proteins"],
            ["target-1", "1", "1", "12.5", "-.n[+42.0106]PEPTIDEKc[+17.0027].-", "P1", "P2"],
            ["decoy-1", "-1", "2", "8.0", "-.EDITPEPK.-", "DECOY_P1"],
        ]


@pytest.mark.asyncio
async def test_percolator_fake_execution_uses_staged_sage_pin_and_native_outputs(tmp_path: Path) -> None:
    pin = tmp_path / "results.sage.pin"
    pin.write_text(
        "SpecId\tLabel\tScanNr\tfeature\tPeptide\tProteins\n"
        "target\t1\t1\t1.0\tPEPTIDEK\tP1\n"
        "decoy\t-1\t2\t0.0\tEDITPEPK\tDECOY_P1\n",
        encoding="utf-8",
    )
    fasta = tmp_path / "target-decoy.fasta"
    fasta.write_text(">P1\nPEPTIDEK\n>DECOY_P1\nEDITPEPK\n", encoding="utf-8")

    class Context:
        node_dir = tmp_path / "run"
        command: list[str] | None = None
        kwargs: dict[str, Any] | None = None

        async def run_command(self, command: list[str], **kwargs: Any) -> dict[str, Any]:
            self.command = command
            self.kwargs = kwargs
            staged_pin = Path(command[-1])
            assert "-.PEPTIDEK.-" in staged_pin.read_text(encoding="utf-8")
            Path(command[command.index("--results-psms") + 1]).write_text(
                "PSMId\tscore\n",
                encoding="utf-8",
            )
            Path(command[command.index("--results-proteins") + 1]).write_text(
                "ProteinId\tq-value\n",
                encoding="utf-8",
            )
            return {"returncode": 0, "stdout": "peptide table", "stderr": "diagnostics"}

    context = Context()
    result = await PercolatorNode().run(
        pin_file=pin,
        fasta_db=fasta,
        pin_dialect="sage_0_14_7_full_digest",
        search_input="concatenated",
        decoy_prefix="DECOY_",
        context=context,
    )

    assert result == (
        str(tmp_path / "run" / "percolator" / "percolator_psms.tsv"),
        str(tmp_path / "run" / "percolator" / "percolator_proteins.tsv"),
    )
    assert context.command is not None
    assert context.command[-1] == str(tmp_path / "run" / "percolator" / "sage.percolator.pin")
    assert context.kwargs == {"env": None, "cwd": tmp_path / "run"}


@pytest.mark.parametrize(
    ("inputs", "message"),
    [
        ({"pin_file": "", "fasta_db": "db.fa"}, "pin_file"),
        ({"pin_file": "a.pin", "fasta_db": "db.fa", "search_input": "paired"}, "search_input"),
        ({"pin_file": "a.pin", "fasta_db": "db.fa", "pin_dialect": "sage"}, "pin_dialect"),
        ({"pin_file": "a.pin", "fasta_db": "db.fa", "test_fdr": 1.1}, "at most 1"),
        ({"pin_file": "a.pin", "fasta_db": "db.fa", "post_processing_tdc": "yes"}, "boolean"),
    ],
)
def test_percolator_rejects_invalid_source_values(inputs: dict[str, Any], message: str) -> None:
    assert message in str(PercolatorNode.VALIDATE_INPUTS(inputs))


def test_percolator_sage_staging_fails_closed_on_decoy_prefix_mismatch(tmp_path: Path) -> None:
    source = tmp_path / "bad.sage.pin"
    source.write_text(
        "SpecId\tLabel\tScanNr\tfeature\tPeptide\tProteins\n"
        "decoy\t-1\t1\t0.0\tEDITPEPK\tnot_prefixed\n",
        encoding="utf-8",
    )
    inputs: dict[str, Any] = {
        "pin_file": source,
        "fasta_db": "db.fa",
        "pin_dialect": "sage_0_14_7_full_digest",
        "decoy_prefix": "DECOY_",
    }
    outputs = PercolatorNode.PLAN_OUTPUTS(inputs, tmp_path / "run")

    with pytest.raises(ValueError, match="decoy proteins must start"):
        PercolatorNode.PREPARE_EXECUTION(inputs, outputs)
