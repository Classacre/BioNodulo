from __future__ import annotations

import inspect
from pathlib import Path

import pytest

from bionodulo.nodes.builtin.wrapped_protein_taxonomy_family.hmmer import (
    HMMERHmmscanNode,
    HMMERHmmsearchNode,
    HMMERJackhmmerNode,
    HMMERNhmmerNode,
    HMMERNhmmscanNode,
    HMMERPhmmerNode,
)

COMMIT = "9acd8b6758a0ca5d21db6d167e0277484341929b"
EASEL_COMMIT = "07ca83ba9ef0414dba9ce0a9331d465b5eb58f2b"
SEARCH_WAVE = (
    (HMMERJackhmmerNode, "jackhmmer"),
    (HMMERPhmmerNode, "phmmer"),
    (HMMERNhmmerNode, "nhmmer"),
    (HMMERNhmmscanNode, "nhmmscan"),
    (HMMERHmmsearchNode, "hmmsearch"),
    (HMMERHmmscanNode, "hmmscan"),
)


def _pressed_inputs(base: str = "/db/profiles.hmm") -> dict[str, str]:
    return {
        "hmmdb": base,
        "hmmdb_h3f": f"{base}.h3f",
        "hmmdb_h3i": f"{base}.h3i",
        "hmmdb_h3m": f"{base}.h3m",
        "hmmdb_h3p": f"{base}.h3p",
    }


@pytest.mark.parametrize(("node_class", "command"), SEARCH_WAVE)
def test_search_wave_has_operation_local_hmmer_34_authority(node_class: type, command: str) -> None:
    assert node_class.VERSION == "3.4"
    assert node_class.GIT_COMMIT == COMMIT
    assert node_class.DOCUMENTATION_URL == (
        f"https://github.com/EddyRivasLab/hmmer/blob/{COMMIT}/documentation/man/{command}.man.in"
    )
    assert node_class.SOURCE_URL == f"https://github.com/EddyRivasLab/hmmer/blob/{COMMIT}/src/{command}.c"
    assert f"documentation/man/{command}.man.in" in node_class.SOURCE_PATHS
    assert f"src/{command}.c" in node_class.SOURCE_PATHS
    assert f"src/{command}.c::main" in node_class.UPSTREAM_SOURCE
    assert node_class.PACKAGE_CONSTRAINT == "hmmer==3.4"
    assert node_class.OPTION_PARSER_VERSION == "0.49"
    assert node_class.OPTION_PARSER_GIT_COMMIT == EASEL_COMMIT
    assert node_class.OPTION_PARSER_SOURCE_URL == (
        f"https://github.com/EddyRivasLab/easel/blob/{EASEL_COMMIT}/esl_getopts.c"
    )
    assert node_class.OPTION_PARSER_SOURCE == "esl_getopts.c::esl_opt_VerifyConfig"
    assert node_class.AUDIT_STATUS == "contract-checked-no-external-execution"
    assert all(".hmmer.adapter" not in base.__module__ for base in inspect.getmro(node_class))


@pytest.mark.parametrize(
    ("node_class", "inputs", "worker_count"),
    [
        (HMMERJackhmmerNode, {"seqfile": "query.fa", "seqdb": "target.fa"}, 2),
        (HMMERPhmmerNode, {"seqfile": "query.fa", "seqdb": "target.fa"}, 2),
        (HMMERNhmmerNode, {"hmmfile": "query.hmm", "seqfile": "target.fa"}, 2),
        (HMMERNhmmscanNode, {**_pressed_inputs(), "seqfile": "query.fa"}, 0),
        (HMMERHmmsearchNode, {"hmmfile": "query.hmm", "seqdb": "target.fa"}, 2),
        (HMMERHmmscanNode, {**_pressed_inputs(), "seqfile": "query.fa"}, 0),
    ],
)
def test_search_commands_use_direct_outputs_and_exact_worker_defaults(
    node_class: type,
    inputs: dict[str, object],
    worker_count: int,
) -> None:
    command = node_class.render_command({**inputs, "output": f"/work/{node_class.NODE_ID}"})
    assert command[0] in node_class.REQUIRED_EXECUTABLES
    assert ">" not in command
    assert "&&" not in command
    assert command[command.index("-o") + 1] == f"/work/{node_class.NODE_ID}/output.txt"
    assert command[command.index("--cpu") + 1] == str(worker_count)


def test_jackhmmer_renders_documented_exclusive_construction_and_filter_options() -> None:
    command = HMMERJackhmmerNode.render_command(
        {
            "seqfile": "query.fa",
            "seqdb": "target.fa",
            "effective_weighting": "eent",
            "max": True,
            "threads": 7,
            "output": "/work/jackhmmer",
        }
    )
    assert "--eent" in command
    assert "--eset" not in command
    assert "--max" in command
    assert not {"--F1", "--F2", "--F3", "--nobias"}.intersection(command)
    assert command[command.index("--cpu") + 1] == "7"
    assert "--wgiven" not in HMMERJackhmmerNode.INPUT_TYPES()["optional"]["relative_weighting"][1]["options"]
    assert (
        HMMERJackhmmerNode.VALIDATE_INPUTS(
            {"seqfile": "query.fa", "seqdb": "target.fa", "effective_weighting": "eent", "eset": 2.0}
        )
        == "Input 'eset' is only valid when effective_weighting is eset"
    )


def test_nhmmer_uses_pinned_source_defaults_and_only_it_declares_alignment_scores() -> None:
    optional = HMMERNhmmerNode.INPUT_TYPES()["optional"]
    assert optional["popen"][1]["default"] == 0.03125
    assert optional["pextend"][1]["default"] == 0.75
    assert optional["F2"][1]["default"] == 0.003
    assert optional["F3"][1]["default"] == 3e-5
    assert "source" in HMMERNhmmerNode.AUDIT_CAVEATS[0]
    command = HMMERNhmmerNode.render_command(
        {
            "hmmfile": "query.sto",
            "seqfile": "target.fa",
            "singlemx": True,
            "output": "/work/nhmmer",
        }
    )
    assert "--singlemx" in command
    assert "--aliscoresout" in command
    assert "domz" not in HMMERNhmmerNode.INPUT_TYPES()["optional"]
    assert "aliscoresout" not in HMMERNhmmscanNode.RETURN_NAMES
    assert "--aliscoresout" not in HMMERNhmmscanNode.render_command(
        {**_pressed_inputs(), "seqfile": "query.fa", "output": "/work/nhmmscan"}
    )


@pytest.mark.parametrize("node_class", [HMMERHmmscanNode, HMMERNhmmscanNode])
def test_scan_nodes_require_and_stage_all_four_hmmpress_siblings(node_class: type, tmp_path: Path) -> None:
    assert node_class.SIDECAR_DOCUMENTATION_URL == (
        f"https://github.com/EddyRivasLab/hmmer/blob/{COMMIT}/documentation/man/hmmpress.man.in"
    )
    assert node_class.SIDECAR_SOURCE_PATHS == ("documentation/man/hmmpress.man.in",)
    source = tmp_path / "source" / "profiles.hmm"
    source.parent.mkdir()
    source.write_text("HMMER3/f\n")
    inputs: dict[str, object] = {"hmmdb": str(source), "seqfile": "query.fa"}
    for suffix in (".h3f", ".h3i", ".h3m", ".h3p"):
        sidecar = Path(f"{source}{suffix}")
        sidecar.write_text(suffix)
        inputs[f"hmmdb_{suffix[1:]}"] = str(sidecar)

    missing = dict(inputs)
    missing.pop("hmmdb_h3p")
    assert "hmmdb_h3p" in str(node_class.VALIDATE_INPUTS(missing))
    wrong = dict(inputs, hmmdb_h3p=str(tmp_path / "wrong.h3p"))
    assert "exact sibling" in str(node_class.VALIDATE_INPUTS(wrong))

    outputs = node_class.PLAN_OUTPUTS(inputs, tmp_path / "results")
    node_class.PREPARE_EXECUTION(inputs, outputs)
    staged = Path(str(inputs["hmmdb"]))
    assert staged == outputs[0].parent / "inputs" / "profiles.hmm"
    assert staged.read_text() == "HMMER3/f\n"
    for suffix in (".h3f", ".h3i", ".h3m", ".h3p"):
        assert Path(f"{staged}{suffix}").read_text() == suffix
    assert node_class.VALIDATE_INPUTS(inputs) is True


@pytest.mark.parametrize(
    ("node_class", "filenames"),
    [
        (HMMERJackhmmerNode, ("output.txt", "results.tblout", "domains.domtblout")),
        (HMMERPhmmerNode, ("output.txt", "results.tblout", "domains.domtblout", "pfam.tblout")),
        (HMMERNhmmerNode, ("output.txt", "results.tblout", "dfam.tblout", "alignment_scores.txt")),
        (HMMERNhmmscanNode, ("output.txt", "results.tblout", "dfam.tblout")),
        (HMMERHmmsearchNode, ("output.txt", "results.tblout", "domains.domtblout", "pfam.tblout")),
        (HMMERHmmscanNode, ("output.txt", "results.tblout", "domains.domtblout", "pfam.tblout")),
    ],
)
def test_search_output_plans_are_fixed_runtime_lists(
    node_class: type,
    filenames: tuple[str, ...],
    tmp_path: Path,
) -> None:
    outputs = node_class.PLAN_OUTPUTS({}, tmp_path)
    assert isinstance(outputs, list)
    assert tuple(path.name for path in outputs) == filenames
    assert len(outputs) == len(node_class.RETURN_NAMES)
