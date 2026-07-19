from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path
from typing import Any

import pytest

from bionodulo.environments.constants import EXECUTABLE_TO_CONDA_PACKAGE, PACKAGE_MIN_VERSIONS
from bionodulo.execution.subprocess_runner import CommandExecutionError
from bionodulo.nodes.builtin import pangenomics as legacy_pangenomics
from bionodulo.nodes.builtin.pangenomics_family.odgi_build import ODGIBuildNode
from bionodulo.nodes.builtin.pangenomics_family.odgi_stats import ODGIStatsNode
from bionodulo.nodes.builtin.pangenomics_family.odgi_view import ODGIViewNode
from bionodulo.nodes.builtin.pangenomics_family.odgi_visualize import ODGIVisualizeNode
from bionodulo.nodes.builtin.pangenomics_family.odgi_viz import ODGIVizNode
from bionodulo.nodes.builtin.pangenomics_family.pggb import PGGBNode
from bionodulo.nodes.builtin.pangenomics_family.pggb_build import PGGBBuildNode
from bionodulo.nodes.registry import NodeRegistry
from bionodulo.workflow.validation import validate_workflow


ODGI_CLASSES = (
    ODGIBuildNode,
    ODGIStatsNode,
    ODGIViewNode,
    ODGIVizNode,
    ODGIVisualizeNode,
)
ALL_CLASSES = (*ODGI_CLASSES, PGGBNode, PGGBBuildNode)


def _write_executable(path: Path, script: str) -> None:
    path.write_text(script, encoding="utf-8")
    path.chmod(0o755)


def _install_fake_pggb_tools(bin_dir: Path) -> None:
    bin_dir.mkdir()
    _write_executable(
        bin_dir / "samtools",
        """#!/usr/bin/env bash
set -euo pipefail
[[ "${1:-}" == "faidx" ]]
printf 'sample#1#chr1\t4\t0\t4\t5\n' > "${2}.fai"
""",
    )
    _write_executable(
        bin_dir / "pggb",
        """#!/usr/bin/env bash
set -euo pipefail
input=''
output=''
while (( $# )); do
    case "$1" in
        -i) input="$2"; shift 2 ;;
        -o) output="$2"; shift 2 ;;
        *) shift ;;
    esac
done
[[ -s "${input}.fai" ]] || { printf 'missing sibling FASTA index\n' >&2; exit 80; }
printf '%s\n' "$input" > "${output}/seen-input.txt"
case "${FAKE_PGGB_MODE:-success}" in
    success)
        printf 'H\tVN:Z:1.0\nS\t1\tACGT\n' > "${output}/fake.final.gfa"
        printf 'fake odgi\n' > "${output}/fake.final.og"
        ;;
    missing)
        printf 'H\tVN:Z:1.0\n' > "${output}/fake.final.gfa"
        ;;
    ambiguous)
        printf 'H\tVN:Z:1.0\n' > "${output}/one.final.gfa"
        printf 'H\tVN:Z:1.0\n' > "${output}/two.final.gfa"
        printf 'fake odgi\n' > "${output}/fake.final.og"
        ;;
esac
""",
    )


def test_registry_owns_all_seven_ids_in_focused_modules() -> None:
    registry = NodeRegistry.create_isolated()
    registry.load_builtin_nodes()

    expected = {
        "odgi_build": ODGIBuildNode,
        "odgi_stats": ODGIStatsNode,
        "odgi_view": ODGIViewNode,
        "odgi_viz": ODGIVizNode,
        "odgi_visualize": ODGIVisualizeNode,
        "pggb": PGGBNode,
        "pggb_build": PGGBBuildNode,
    }
    assert {node_id: registry.get(node_id) for node_id in expected} == expected
    assert all("pangenomics_family" in node_class.__module__ for node_class in expected.values())


def test_legacy_module_exports_the_focused_classes() -> None:
    assert legacy_pangenomics.ODGIBuildNode is ODGIBuildNode
    assert legacy_pangenomics.ODGIStatsNode is ODGIStatsNode
    assert legacy_pangenomics.ODGIViewNode is ODGIViewNode
    assert legacy_pangenomics.ODGIVizNode is ODGIVizNode
    assert legacy_pangenomics.ODGIVisualizeNode is ODGIVisualizeNode
    assert legacy_pangenomics.PGGBNode is PGGBNode
    assert legacy_pangenomics.PGGBBuildNode is PGGBBuildNode


def test_odgi_metadata_is_pinned_to_the_audited_source() -> None:
    for node_class in ODGI_CLASSES:
        assert node_class.VERSION == "0.9.2"
        assert node_class.UPSTREAM_TAG == "v0.9.2"
        assert node_class.GIT_COMMIT == "be6a0202501d7ea2ac57f9ad89d4d10ed5dbd7c6"
        assert node_class.BIOCONDA_RECIPE_COMMIT == "aac8e6e4ee3d12bd497495dddfc32825393c35da"
        assert node_class.UPSTREAM_SOURCE
        assert node_class.CITATION_DOIS == ["10.1093/bioinformatics/btac308"]
        assert node_class.REQUIRED_EXECUTABLES == ["odgi"]
        assert node_class.REQUIRED_CONDA_PACKAGES == ["odgi"]


def test_pggb_metadata_is_pinned_with_its_odgi_runtime() -> None:
    for node_class in (PGGBNode, PGGBBuildNode):
        assert node_class.VERSION == "0.7.4"
        assert node_class.UPSTREAM_TAG == "v0.7.4"
        assert node_class.GIT_COMMIT == "e25486b9b219877eca82631a13953129386c8b09"
        assert node_class.BIOCONDA_RECIPE_COMMIT == "d9929a470a5703120551635efbad7d27aed87ebd"
        assert node_class.BIOCONDA_ODGI_RUNTIME == "0.9.2"
        assert node_class.FAIDX_VERSION == "1.23.1"
        assert node_class.CITATION_DOIS == ["10.1038/s41592-024-02430-3"]
        assert node_class.REQUIRED_EXECUTABLES == ["pggb", "samtools"]


def test_odgi_input_contracts_match_the_operations() -> None:
    assert set(ODGIBuildNode.INPUT_TYPES()["optional"]) == {
        "threads",
        "compact_ids",
        "validate",
        "output_name",
    }
    assert ODGIStatsNode.INPUT_TYPES()["required"]["gfa_graph"][0] == "GFA"
    assert ODGIViewNode.INPUT_TYPES()["required"] == {
        "graph": ("ODGI", {"description": "Readable ODGI graph"})
    }
    assert set(ODGIViewNode.INPUT_TYPES()["optional"]) == {"threads", "node_annotations"}
    assert set(ODGIVizNode.INPUT_TYPES()["optional"]) == {
        "width",
        "height",
        "show_paths",
        "viz_mode",
        "threads",
    }


def test_odgi_validation_rejects_missing_empty_and_invalid_values(tmp_path: Path) -> None:
    missing = tmp_path / "missing.gfa"
    empty = tmp_path / "empty.gfa"
    empty.touch()
    graph = tmp_path / "graph.gfa"
    graph.write_text("H\tVN:Z:1.0\n", encoding="utf-8")

    assert "does not exist or is not readable" in str(
        ODGIBuildNode.VALIDATE_INPUTS({"gfa_graph": missing, "threads": 1})
    )
    assert "is empty" in str(ODGIStatsNode.VALIDATE_INPUTS({"gfa_graph": empty, "threads": 1}))
    assert ODGIBuildNode.VALIDATE_INPUTS({"gfa_graph": graph, "threads": 0}) == (
        "threads must be at least 1"
    )
    assert ODGIVizNode.VALIDATE_INPUTS(
        {"gfa_graph": graph, "threads": 1, "viz_mode": "heatmap"}
    ) == "Unsupported ODGI Viz mode: heatmap"

    odgi_graph = tmp_path / "graph.og"
    odgi_graph.write_text("odgi\n", encoding="utf-8")
    assert "legacy odgi_view visualization inputs" in str(
        ODGIViewNode.VALIDATE_INPUTS({
            "graph": odgi_graph,
            "threads": 1,
            "mode": "png",
        })
    )


def test_odgi_build_renders_documented_build_validate_and_summary_operations() -> None:
    inputs = {
        "gfa_graph": "/data/input graph.gfa",
        "threads": 3,
        "compact_ids": True,
        "validate": True,
        "output_name": "../study graph",
        "output": "/tmp/node output",
    }

    assert ODGIBuildNode.build_argv(inputs) == [
        "odgi",
        "build",
        "-g",
        "/data/input graph.gfa",
        "-o",
        "/tmp/node output/study_graph.odgi",
        "-O",
        "-t",
        "3",
    ]
    command = ODGIBuildNode.render_command(inputs)
    assert command[:4] == ["bash", "-o", "pipefail", "-c"]
    script = command[4]
    assert "odgi validate -i '/tmp/node output/study_graph.odgi' -t 3" in script
    assert "odgi stats -i '/tmp/node output/study_graph.odgi' -S -t 3" in script
    assert " -j" not in script
    assert script.endswith("test -s '/tmp/node output/study_graph.stats.json'")


def test_odgi_stats_pipeline_adapts_tabular_stdout_to_deterministic_json(
    tmp_path: Path,
) -> None:
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    _write_executable(
        bin_dir / "odgi",
        """#!/usr/bin/env bash
printf '#length\tnodes\tedges\tpaths\tsteps\n42\t5\t6\t2\t9\n'
""",
    )
    output = tmp_path / "output with spaces"
    output.mkdir()
    command = ODGIStatsNode.render_command(
        {"gfa_graph": tmp_path / "input graph.gfa", "threads": 2, "output": output}
    )

    completed = subprocess.run(
        command,
        check=False,
        capture_output=True,
        text=True,
        env={**os.environ, "PATH": f"{bin_dir}:{os.environ['PATH']}"},
    )

    stats_path = output / "stats.json"
    assert completed.returncode == 0, completed.stderr
    assert stats_path.read_text(encoding="utf-8") == (
        '{"edges":6,"length":42,"nodes":5,"paths":2,"steps":9}\n'
    )
    assert json.loads(stats_path.read_text(encoding="utf-8"))["length"] == 42


def test_odgi_stats_pipeline_propagates_upstream_failure(tmp_path: Path) -> None:
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    _write_executable(bin_dir / "odgi", "#!/usr/bin/env bash\nexit 7\n")
    output = tmp_path / "output"
    output.mkdir()

    completed = subprocess.run(
        ODGIStatsNode.render_command({"gfa_graph": "graph.og", "threads": 1, "output": output}),
        check=False,
        capture_output=True,
        text=True,
        env={**os.environ, "PATH": f"{bin_dir}:{os.environ['PATH']}"},
    )

    assert completed.returncode != 0
    assert (output / "stats.json").stat().st_size == 0


@pytest.mark.asyncio
async def test_odgi_view_captures_gfa_stdout_as_its_artifact(tmp_path: Path) -> None:
    graph = tmp_path / "graph.og"
    graph.write_text("non-empty odgi fixture\n", encoding="utf-8")

    class Context:
        node_dir = tmp_path
        command: list[str] | None = None

        async def run_command(self, command: list[str], **kwargs: Any) -> dict[str, Any]:
            self.command = command
            stdout_path = Path(kwargs["stdout_path"])
            stdout_path.parent.mkdir(parents=True, exist_ok=True)
            stdout_path.write_text("H\tVN:Z:1.0\n", encoding="utf-8")
            return {"returncode": 0, "stdout": "", "stderr": ""}

    context = Context()
    result = await ODGIViewNode().run(
        graph=graph,
        threads=4,
        node_annotations=True,
        context=context,
        output_dir=tmp_path / "run",
    )

    expected = tmp_path / "run" / "odgi_view" / "graph.gfa"
    assert context.command == ["odgi", "view", "-i", str(graph), "-g", "-a", "-t", "4"]
    assert result == (str(expected),)
    assert expected.read_text(encoding="utf-8") == "H\tVN:Z:1.0\n"


def test_odgi_viz_maps_legacy_controls_to_documented_flags() -> None:
    command = ODGIVizNode.render_command(
        {
            "gfa_graph": "graph.gfa",
            "width": 1600,
            "height": 260,
            "show_paths": False,
            "viz_mode": "gradient",
            "threads": 4,
            "output": "/tmp/odgi_viz",
        }
    )

    assert command == [
        "odgi",
        "viz",
        "-i",
        "graph.gfa",
        "-o",
        "/tmp/odgi_viz/viz_image.png",
        "-x",
        "1600",
        "-y",
        "260",
        "-H",
        "-d",
        "-t",
        "4",
    ]
    assert "-p" not in command


def test_odgi_visualize_is_an_explicit_five_operation_compatibility_composite() -> None:
    command = ODGIVisualizeNode.render_command(
        {
            "gfa_graph": "graph.gfa",
            "threads": 3,
            "show_path_names": False,
            "color_paths": True,
            "output": "/tmp/odgi_visualize",
        }
    )
    script = command[4]

    assert ODGIVisualizeNode.COMPATIBILITY_COMPOSITE is True
    assert command[:4] == ["bash", "-o", "pipefail", "-c"]
    for operation in ("odgi build", "odgi viz", "odgi sort", "odgi layout", "odgi draw"):
        assert operation in script
    assert "odgi sort -i /tmp/odgi_visualize/graph.og" in script
    assert "-p Ygs -O -t 3" in script
    assert "graph_2d.png -H 1000 -C -t 3" in script


def test_all_nodes_plan_stable_operation_specific_outputs(tmp_path: Path) -> None:
    expected = {
        ODGIBuildNode: ("graph.odgi", "graph.stats.json"),
        ODGIStatsNode: ("stats.json",),
        ODGIViewNode: ("graph.gfa",),
        ODGIVizNode: ("viz_image.png",),
        ODGIVisualizeNode: ("graph_1d.png", "graph_2d.png"),
        PGGBNode: ("smooth_gfa.gfa", "smooth_odgi.og"),
        PGGBBuildNode: ("graph_gfa.gfa", "graph_odgi.odgi"),
    }
    inputs = {"gfa_graph": "graph.gfa"}

    for node_class, names in expected.items():
        outputs = node_class.PLAN_OUTPUTS(inputs, tmp_path)
        assert tuple(path.name for path in outputs) == names
        assert all(path.parent == tmp_path / node_class.NODE_ID for path in outputs)


def test_pggb_contract_and_defaults_match_version_074() -> None:
    inputs = PGGBNode.INPUT_TYPES()
    assert set(inputs["required"]) == {"input_fasta", "threads"}
    assert set(inputs["optional"]) == {
        "num_haplotypes",
        "map_pct_id",
        "segment_length",
        "min_match_length",
        "poa_length_target",
        "do_viz",
        "stats",
    }
    assert inputs["optional"]["min_match_length"][1]["default"] == 23
    assert inputs["optional"]["poa_length_target"][1]["default"] == "700,1100"
    assert PGGBNode.pggb_argv(
        {"input_fasta": "haplotypes.fa", "threads": 8, "output": "/tmp/pggb"}
    ) == [
        "pggb",
        "-i",
        "haplotypes.fa",
        "-o",
        "/tmp/pggb",
        "-t",
        "8",
        "-p",
        "90",
        "-s",
        "5000",
        "-k",
        "23",
        "-G",
        "700,1100",
    ]


def test_pggb_renders_supported_optional_flags_only() -> None:
    command = PGGBNode.pggb_argv(
        {
            "input_fasta": "haplotypes.fa",
            "threads": 16,
            "num_haplotypes": 6,
            "map_pct_id": 95.5,
            "segment_length": 10000,
            "min_match_length": 29,
            "poa_length_target": "800,1200",
            "do_viz": False,
            "stats": True,
            "output": "/tmp/pggb",
        }
    )

    assert command == [
        "pggb",
        "-i",
        "haplotypes.fa",
        "-o",
        "/tmp/pggb",
        "-n",
        "6",
        "-t",
        "16",
        "-p",
        "95.5",
        "-s",
        "10000",
        "-k",
        "29",
        "-G",
        "800,1200",
        "-v",
        "-S",
    ]
    assert "-C" not in command


def test_pggb_validation_fails_closed_for_unsupported_or_invalid_values(tmp_path: Path) -> None:
    fasta = tmp_path / "haplotypes.fa"
    fasta.write_text(">sample#1#chr1\nACGT\n", encoding="utf-8")
    valid = {"input_fasta": fasta, "threads": 4}
    assert PGGBNode.VALIDATE_INPUTS(valid) is True

    cases = (
        ({"threads": 0}, "threads must be at least 1"),
        ({"num_haplotypes": -1}, "num_haplotypes must be zero or greater"),
        ({"map_pct_id": 0}, "map_pct_id must be greater than 0 and at most 100"),
        ({"segment_length": 0}, "segment_length must be at least 1"),
        ({"min_match_length": True}, "min_match_length must be an integer"),
        (
            {"poa_length_target": "700,0"},
            "poa_length_target must be a comma-separated list of positive integers",
        ),
        (
            {"graph_poas": 2},
            "legacy graph_poas has no PGGB 0.7.4 equivalent; use poa_length_target for -G",
        ),
        (
            {"consensus_spec": "cons,100"},
            "consensus_spec is unavailable in PGGB 0.7.4; the upstream -C option is disabled",
        ),
        ({"do_layout": False}, "legacy do_layout is unavailable in PGGB 0.7.4"),
    )
    for overrides, message in cases:
        assert PGGBNode.VALIDATE_INPUTS({**valid, **overrides}) == message


def test_pggb_prepares_one_safe_fasta_path_for_sibling_index_discovery(tmp_path: Path) -> None:
    source = tmp_path / "unsafe name.fasta.gz"
    source.write_text(">sample#1#chr1\nACGT\n", encoding="utf-8")
    outputs = [
        tmp_path / "pggb" / "smooth_gfa.gfa",
        tmp_path / "pggb" / "smooth_odgi.og",
    ]
    inputs: dict[str, Any] = {"input_fasta": source}

    PGGBNode.PREPARE_EXECUTION(inputs, outputs)

    staged = tmp_path / "pggb" / "_inputs" / "input.fasta.gz"
    assert inputs["input_fasta"] == str(staged)
    assert staged.read_text(encoding="utf-8") == source.read_text(encoding="utf-8")
    assert staged.parent == outputs[0].parent / "_inputs"


@pytest.mark.asyncio
async def test_pggb_fake_execution_stages_fai_and_normalizes_final_outputs(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    bin_dir = tmp_path / "bin"
    _install_fake_pggb_tools(bin_dir)
    monkeypatch.setenv("PATH", f"{bin_dir}:{os.environ['PATH']}")
    fasta = tmp_path / "source haplotypes.fa"
    fasta.write_text(">sample#1#chr1\nACGT\n", encoding="utf-8")
    output_root = tmp_path / "run with spaces"

    result = await PGGBNode().run(input_fasta=fasta, threads=2, output_dir=output_root)

    expected_root = output_root / "pggb"
    assert result == (
        str(expected_root / "smooth_gfa.gfa"),
        str(expected_root / "smooth_odgi.og"),
    )
    assert (expected_root / "_inputs" / "input.fa.fai").is_file()
    assert (expected_root / "smooth_gfa.gfa").read_text(encoding="utf-8").startswith("H\t")
    assert (expected_root / "smooth_odgi.og").read_text(encoding="utf-8") == "fake odgi\n"
    assert (expected_root / "seen-input.txt").read_text(encoding="utf-8").strip().endswith(
        "/pggb/_inputs/input.fa"
    )


@pytest.mark.asyncio
async def test_pggb_build_executes_the_multi_fasta_contract(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    bin_dir = tmp_path / "bin"
    _install_fake_pggb_tools(bin_dir)
    monkeypatch.setenv("PATH", f"{bin_dir}:{os.environ['PATH']}")
    first = tmp_path / "haplotype-a.fa"
    second = tmp_path / "haplotype-b.fa"
    first.write_text(">a\nACGT\n", encoding="utf-8")
    second.write_text(">b\nTGCA\n", encoding="utf-8")

    result = await PGGBBuildNode().run(
        input_fasta=[first, second],
        threads=2,
        output_dir=tmp_path / "run",
    )

    output = tmp_path / "run" / "pggb_build"
    assert result == (str(output / "graph_gfa.gfa"), str(output / "graph_odgi.odgi"))
    assert (output / "_inputs" / "input.fa.fai").is_file()
    assert (output / "seen-input.txt").read_text(encoding="utf-8").strip().endswith(
        "/pggb_build/_inputs/input.fa"
    )


@pytest.mark.asyncio
async def test_pggb_fake_execution_rejects_missing_and_ambiguous_native_outputs(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    bin_dir = tmp_path / "bin"
    _install_fake_pggb_tools(bin_dir)
    monkeypatch.setenv("PATH", f"{bin_dir}:{os.environ['PATH']}")
    fasta = tmp_path / "haplotypes.fa"
    fasta.write_text(">sample#1#chr1\nACGT\n", encoding="utf-8")

    for mode, expected_message in (
        ("missing", "expected exactly one *.final.og, found 0"),
        ("ambiguous", "expected exactly one *.final.gfa, found 2"),
    ):
        monkeypatch.setenv("FAKE_PGGB_MODE", mode)
        with pytest.raises(CommandExecutionError) as exc_info:
            await PGGBNode().run(
                input_fasta=fasta,
                threads=2,
                output_dir=tmp_path / f"run-{mode}",
            )
        assert expected_message in exc_info.value.stderr_path.read_text(encoding="utf-8")


def test_pggb_build_preserves_the_distinct_multi_fasta_contract(tmp_path: Path) -> None:
    assert issubclass(PGGBBuildNode, PGGBNode)
    assert PGGBBuildNode.LEGACY_MULTI_FASTA_CONTRACT is True
    assert PGGBBuildNode.RETURN_NAMES == ("graph_gfa", "graph_odgi")
    assert PGGBBuildNode.INPUT_TYPES()["required"]["input_fasta"][1]["multiple"] is True

    first = tmp_path / "haplotype-a.fa"
    second = tmp_path / "haplotype-b.fa"
    first.write_text(">a\nACGT\n", encoding="utf-8")
    second.write_text(">b\nTGCA\n", encoding="utf-8")
    inputs: dict[str, Any] = {"input_fasta": [first, second], "threads": 2}
    outputs = PGGBBuildNode.PLAN_OUTPUTS(inputs, tmp_path)

    assert PGGBBuildNode.VALIDATE_INPUTS(inputs) is True
    PGGBBuildNode.PREPARE_EXECUTION(inputs, outputs)
    staged = Path(inputs["input_fasta"])
    assert staged.read_text(encoding="utf-8") == ">a\nACGT\n\n>b\nTGCA\n"
    assert inputs["num_haplotypes"] == 2
    assert PGGBBuildNode.pggb_argv({**inputs, "output": str(tmp_path / "pggb_build")})[:7] == [
        "pggb",
        "-i",
        str(staged),
        "-o",
        str(tmp_path / "pggb_build"),
        "-n",
        "2",
    ]


def test_pggb_build_rejects_single_or_legacy_ambiguous_inputs(tmp_path: Path) -> None:
    fasta = tmp_path / "haplotype.fa"
    fasta.write_text(">a\nACGT\n", encoding="utf-8")

    assert PGGBBuildNode.VALIDATE_INPUTS({"input_fasta": [fasta], "threads": 1}) == (
        "pggb_build requires at least two haplotype FASTA files"
    )
    assert PGGBBuildNode.VALIDATE_INPUTS({
        "input_fasta": [fasta, fasta],
        "threads": 1,
        "graph_poas": 2,
    }) == "legacy graph_poas has no PGGB 0.7.4 equivalent; use poa_length_target for -G"


@pytest.mark.parametrize(
    ("node_class", "removed_port", "required_input", "input_value"),
    [
        (ODGIViewNode, "view", "graph", "graph.og"),
        (ODGIViewNode, "stats", "graph", "graph.og"),
        (PGGBNode, "consensus_fasta", "input_fasta", "haplotypes.fa"),
    ],
)
def test_removed_pangenomics_output_ports_fail_workflow_validation(
    node_class: type,
    removed_port: str,
    required_input: str,
    input_value: str,
) -> None:
    registry = NodeRegistry.create_isolated()
    registry.register(node_class)
    result = validate_workflow(
        {
            "nodes": [
                {
                    "id": "source",
                    "type": node_class.NODE_ID,
                    "params": {required_input: input_value},
                },
                {"id": "target", "type": node_class.NODE_ID, "params": {}},
            ],
            "edges": [
                {
                    "from": {"node": "source", "output": removed_port},
                    "to": {"node": "target", "input": required_input},
                }
            ],
        },
        registry,
    )

    assert result.valid is False
    assert f"unknown output port '{removed_port}'" in result.errors[0]


def test_environment_constraints_match_the_pinned_source_versions() -> None:
    assert EXECUTABLE_TO_CONDA_PACKAGE["odgi"] == "odgi"
    assert EXECUTABLE_TO_CONDA_PACKAGE["pggb"] == "pggb"
    assert PACKAGE_MIN_VERSIONS["odgi"] == "0.9.2"
    assert PACKAGE_MIN_VERSIONS["pggb"] == "0.7.4"
