from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from bionodulo.nodes.builtin.variant_family.delly import DellyNode
from bionodulo.nodes.builtin.variant_family.delly_call import DellyCallNode
from bionodulo.nodes.builtin.variant_family.freebayes import FreeBayesNode
from bionodulo.nodes.builtin.variant_family.manta import MantaNode
from bionodulo.nodes.builtin.variant_family.manta_call import MantaCallNode


FREEBAYES_COMMIT = "b0d8efd9fa7f6612c883ec5ff79e4d17a0c29993"
MANTA_COMMIT = "ab9f5502985a29ec74cfafb4963179b9cc185e55"
DELLY_COMMIT = "e6246dbb18b7f6df2b7b381d542cdeaea6be8c82"


def _indexed_inputs(**updates: Any) -> dict[str, Any]:
    inputs: dict[str, Any] = {
        "bam": "/data/sample.bam",
        "bam_index": "/data/sample.bam.bai",
        "reference": "/data/reference.fa",
        "reference_index": "/data/reference.fa.fai",
    }
    inputs.update(updates)
    return inputs


@pytest.mark.parametrize(
    ("node", "version", "commit", "source"),
    [
        (FreeBayesNode, "1.3.10", FREEBAYES_COMMIT, "src/Parameters.cpp"),
        (DellyNode, "1.2.6", DELLY_COMMIT, "src/delly.h"),
        (DellyCallNode, "1.2.6", DELLY_COMMIT, "src/delly.h"),
        (MantaNode, "1.6.0", MANTA_COMMIT, "src/python/bin/configManta.py"),
        (MantaCallNode, "1.6.0", MANTA_COMMIT, "src/python/bin/configManta.py"),
    ],
)
def test_variant_callers_are_source_pinned(
    node: type,
    version: str,
    commit: str,
    source: str,
) -> None:
    assert node.VERSION == version
    assert node.GIT_COMMIT == commit
    assert node.UPSTREAM_SOURCE == source


def test_freebayes_native_output_and_default_argv_are_exact(tmp_path: Path) -> None:
    output = tmp_path / "freebayes"
    inputs = _indexed_inputs(output=output)

    assert FreeBayesNode.SHELL is False
    assert FreeBayesNode.RETURN_TYPES == ("VCF",)
    assert FreeBayesNode.RETURN_NAMES == ("vcf",)
    assert FreeBayesNode.PLAN_OUTPUTS(inputs, tmp_path) == [output / "vcf.vcf"]
    assert FreeBayesNode.render_command(inputs) == [
        "freebayes",
        "-f",
        "/data/reference.fa",
        "-v",
        str(output / "vcf.vcf"),
        "-p",
        "2",
        "-m",
        "1",
        "-q",
        "0",
        "--haplotype-length",
        "3",
        "/data/sample.bam",
    ]


def test_freebayes_optional_argv_is_exact(tmp_path: Path) -> None:
    output = tmp_path / "freebayes"
    inputs = _indexed_inputs(
        output=output,
        pooled=True,
        ploidy=4,
        min_mapping_quality=10,
        min_base_quality=13,
        haplotype_length=50,
    )

    assert FreeBayesNode.render_command(inputs) == [
        "freebayes",
        "-f",
        "/data/reference.fa",
        "-v",
        str(output / "vcf.vcf"),
        "-K",
        "-p",
        "4",
        "-m",
        "10",
        "-q",
        "13",
        "--haplotype-length",
        "50",
        "/data/sample.bam",
    ]


def test_delly_native_bcf_and_csi_contract_is_exact(tmp_path: Path) -> None:
    output = tmp_path / "delly"
    inputs = _indexed_inputs(mode="call", output=output)

    assert DellyNode.SHELL is False
    assert DellyNode.RETURN_TYPES == ("BCF", "VCF_INDEX")
    assert DellyNode.RETURN_NAMES == ("sv_calls", "sv_calls_index")
    assert DellyNode.PLAN_OUTPUTS(inputs, tmp_path) == [
        output / "sv_calls.bcf",
        output / "sv_calls.bcf.csi",
    ]
    assert DellyNode.render_command(inputs) == [
        "delly",
        "call",
        "-g",
        "/data/reference.fa",
        "-o",
        str(output / "sv_calls.bcf"),
        "-q",
        "1",
        "/data/sample.bam",
    ]


def test_delly_long_read_argv_uses_source_native_technology_flag(tmp_path: Path) -> None:
    output = tmp_path / "delly"
    inputs = _indexed_inputs(
        mode="lr",
        output=output,
        exclude_regions="excluded.bed",
        map_qual=5,
        technology="pb",
    )

    assert DellyNode.render_command(inputs) == [
        "delly",
        "lr",
        "-g",
        "/data/reference.fa",
        "-o",
        str(output / "sv_calls.bcf"),
        "-x",
        "excluded.bed",
        "-q",
        "5",
        "-y",
        "pb",
        "/data/sample.bam",
    ]


def test_delly_call_is_the_only_explicit_conversion_pipeline(tmp_path: Path) -> None:
    output = tmp_path / "delly_call"
    inputs = _indexed_inputs(mode="call", output=output)
    converted = output / "sv_vcf.vcf.gz"

    assert DellyCallNode.SHELL is True
    assert DellyCallNode.RETURN_TYPES == ("VCF_GZ", "VCF_INDEX")
    assert DellyCallNode.RETURN_NAMES == ("sv_vcf", "sv_vcf_index")
    assert DellyCallNode.PLAN_OUTPUTS(inputs, tmp_path) == [
        converted,
        Path(f"{converted}.tbi"),
    ]
    assert DellyCallNode.render_command(inputs) == [
        "delly",
        "call",
        "-g",
        "/data/reference.fa",
        "-o",
        str(output / "sv_calls.bcf"),
        "-q",
        "1",
        "/data/sample.bam",
        "&&",
        "bcftools",
        "view",
        "-Oz",
        "-o",
        str(converted),
        str(output / "sv_calls.bcf"),
        "&&",
        "tabix",
        "-f",
        "-p",
        "vcf",
        str(converted),
    ]


@pytest.mark.parametrize(
    ("updates", "primary_name"),
    [
        ({}, "diploidSV.vcf.gz"),
        (
            {
                "normal_bam": "/data/normal.bam",
                "normal_bam_index": "/data/normal.bam.bai",
            },
            "somaticSV.vcf.gz",
        ),
        ({"rna": True}, "rnaSV.vcf.gz"),
    ],
)
def test_manta_preserves_mode_specific_native_vcfs_and_tbis(
    tmp_path: Path,
    updates: dict[str, Any],
    primary_name: str,
) -> None:
    inputs = _indexed_inputs(threads=4, **updates)
    variants = tmp_path / "manta" / "results" / "variants"
    candidate = variants / "candidateSV.vcf.gz"
    primary = variants / primary_name

    assert MantaNode.PLAN_OUTPUTS(inputs, tmp_path) == [
        candidate,
        Path(f"{candidate}.tbi"),
        primary,
        Path(f"{primary}.tbi"),
    ]


def test_manta_germline_commands_and_shell_plan_are_exact(tmp_path: Path) -> None:
    output = tmp_path / "manta"
    inputs = _indexed_inputs(threads=6, output=output, exome=True)
    config = [
        "configManta.py",
        "--bam",
        "/data/sample.bam",
        "--referenceFasta",
        "/data/reference.fa",
        "--runDir",
        str(output),
        "--exome",
    ]
    workflow = [str(output / "runWorkflow.py"), "-m", "local", "-j", "6"]

    assert MantaNode.SHELL is True
    assert MantaNode.REQUIRED_EXECUTABLES == ["configManta.py"]
    assert MantaNode.render_config_command(inputs) == config
    assert MantaNode.render_workflow_command(inputs) == workflow
    assert MantaNode.render_command(inputs) == [*config, "&&", *workflow]


def test_manta_tumor_normal_and_rna_configuration_argv_are_exact(tmp_path: Path) -> None:
    output = tmp_path / "manta"
    tumor_normal = _indexed_inputs(
        threads=4,
        output=output,
        normal_bam="/data/normal.bam",
        normal_bam_index="/data/normal.bam.bai",
    )
    rna = _indexed_inputs(threads=4, output=output, rna=True)

    assert MantaNode.render_config_command(tumor_normal) == [
        "configManta.py",
        "--normalBam",
        "/data/normal.bam",
        "--tumorBam",
        "/data/sample.bam",
        "--referenceFasta",
        "/data/reference.fa",
        "--runDir",
        str(output),
    ]
    assert MantaNode.render_config_command(rna) == [
        "configManta.py",
        "--bam",
        "/data/sample.bam",
        "--referenceFasta",
        "/data/reference.fa",
        "--runDir",
        str(output),
        "--rna",
    ]


def test_manta_call_returns_only_primary_vcf_and_tbi(tmp_path: Path) -> None:
    inputs = _indexed_inputs(threads=4, rna=True)
    primary = tmp_path / "manta_call" / "results" / "variants" / "rnaSV.vcf.gz"

    assert MantaCallNode.RETURN_TYPES == ("VCF_GZ", "VCF_INDEX")
    assert MantaCallNode.RETURN_NAMES == ("sv_vcf", "sv_vcf_index")
    assert MantaCallNode.PLAN_OUTPUTS(inputs, tmp_path) == [
        primary,
        Path(f"{primary}.tbi"),
    ]


@pytest.mark.parametrize("node", [FreeBayesNode, DellyNode, MantaNode])
def test_indexed_callers_reject_non_exact_primary_sidecars(node: type) -> None:
    inputs = _indexed_inputs()
    if issubclass(node, DellyNode):
        inputs["mode"] = "call"
    if issubclass(node, MantaNode):
        inputs["threads"] = 4

    assert "exact colocated index" in str(
        node.VALIDATE_INPUTS({**inputs, "bam_index": "/data/other.bai"})
    )
    assert "exact colocated index" in str(
        node.VALIDATE_INPUTS(
            {**inputs, "reference_index": "/data/other-reference.fa.fai"}
        )
    )


def test_manta_normal_index_and_rna_mode_fail_closed() -> None:
    inputs = _indexed_inputs(threads=4)

    assert "expected '/data/normal.bam.bai'" in str(
        MantaNode.VALIDATE_INPUTS({**inputs, "normal_bam": "/data/normal.bam"})
    )
    assert (
        MantaNode.VALIDATE_INPUTS(
            {**inputs, "normal_bam_index": "/data/normal.bam.bai"}
        )
        == "Input 'normal_bam_index' requires input 'normal_bam'"
    )
    assert (
        MantaNode.VALIDATE_INPUTS(
            {
                **inputs,
                "rna": True,
                "normal_bam": "/data/normal.bam",
                "normal_bam_index": "/data/normal.bam.bai",
            }
        )
        == "rna mode requires exactly one normal sample and no tumor BAM"
    )


@pytest.mark.parametrize(
    ("node", "inputs", "message"),
    [
        (FreeBayesNode, _indexed_inputs(ploidy=0), "ploidy must be at least 1"),
        (
            DellyNode,
            _indexed_inputs(mode="invalid"),
            "mode must be one of: call, lr",
        ),
        (
            DellyNode,
            _indexed_inputs(mode="lr", technology="pacbio"),
            "technology must be one of: ont, pb",
        ),
        (
            MantaNode,
            _indexed_inputs(threads=0),
            "threads must be at least 1",
        ),
    ],
)
def test_invalid_parameters_and_rendering_fail_closed(
    node: type,
    inputs: dict[str, Any],
    message: str,
) -> None:
    assert node.VALIDATE_INPUTS(inputs) == message
    with pytest.raises(ValueError, match=message):
        node.render_command(inputs)


@pytest.mark.asyncio
async def test_manta_runtime_executes_two_direct_argv_and_returns_native_outputs(
    tmp_path: Path,
) -> None:
    inputs = _indexed_inputs(threads=3)

    class Context:
        node_dir = tmp_path / "run"

        def __init__(self) -> None:
            self.commands: list[tuple[list[str], dict[str, Any]]] = []

        async def run_command(
            self,
            command: list[str],
            **kwargs: Any,
        ) -> dict[str, Any]:
            self.commands.append((command, kwargs))
            if command[0].endswith("runWorkflow.py"):
                for output in MantaNode.PLAN_OUTPUTS(inputs, self.node_dir):
                    output.parent.mkdir(parents=True, exist_ok=True)
                    output.write_bytes(b"native Manta artifact")
            return {"returncode": 0, "stdout": "", "stderr": ""}

    context = Context()
    result = await MantaNode().run(**inputs, context=context)
    expected = MantaNode.PLAN_OUTPUTS(inputs, context.node_dir)

    assert result == tuple(str(path) for path in expected)
    assert [command for command, _kwargs in context.commands] == [
        [
            "configManta.py",
            "--bam",
            "/data/sample.bam",
            "--referenceFasta",
            "/data/reference.fa",
            "--runDir",
            str(context.node_dir / "manta"),
        ],
        [
            str(context.node_dir / "manta" / "runWorkflow.py"),
            "-m",
            "local",
            "-j",
            "3",
        ],
    ]
    assert all(isinstance(command, list) for command, _kwargs in context.commands)


@pytest.mark.asyncio
@pytest.mark.parametrize(("failed_call", "expected_calls"), [(1, 1), (2, 2)])
async def test_manta_runtime_stops_immediately_on_nonzero_step(
    tmp_path: Path,
    failed_call: int,
    expected_calls: int,
) -> None:
    inputs = _indexed_inputs(threads=4)

    class Context:
        node_dir = tmp_path / "run"

        def __init__(self) -> None:
            self.calls = 0

        async def run_command(
            self,
            _command: list[str],
            **_kwargs: Any,
        ) -> dict[str, Any]:
            self.calls += 1
            return {
                "returncode": 9 if self.calls == failed_call else 0,
                "stdout": "",
                "stderr": "source step failed",
            }

    context = Context()
    label = "configuration" if failed_call == 1 else "workflow"

    with pytest.raises(RuntimeError, match=rf"Manta {label} failed \(exit 9\)"):
        await MantaNode().run(**inputs, context=context)
    assert context.calls == expected_calls


@pytest.mark.asyncio
async def test_manta_runtime_fails_closed_when_native_outputs_are_missing(
    tmp_path: Path,
) -> None:
    inputs = _indexed_inputs(threads=4)

    class Context:
        node_dir = tmp_path / "run"

        async def run_command(
            self,
            _command: list[str],
            **_kwargs: Any,
        ) -> dict[str, Any]:
            return {"returncode": 0, "stdout": "", "stderr": ""}

    with pytest.raises(RuntimeError, match="did not create expected output"):
        await MantaNode().run(**inputs, context=Context())
