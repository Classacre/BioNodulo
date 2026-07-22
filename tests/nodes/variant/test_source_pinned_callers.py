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
    if node in {MantaNode, MantaCallNode}:
        assert node.UPSTREAM_RUN_DIRECTORY_SOURCE == "src/python/lib/mantaOptions.py:147-154"


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


def test_freebayes_accepts_documented_disabled_haplotype_clumping(
    tmp_path: Path,
) -> None:
    output = tmp_path / "freebayes"
    inputs = _indexed_inputs(output=output, haplotype_length=-1)

    assert FreeBayesNode.INPUT_TYPES()["optional"]["haplotype_length"][1]["min"] == -1
    assert FreeBayesNode.VALIDATE_INPUTS(inputs) is True
    assert FreeBayesNode.render_command(inputs)[-3:] == [
        "--haplotype-length",
        "-1",
        "/data/sample.bam",
    ]


def test_source_callers_do_not_apply_local_thread_or_ploidy_caps() -> None:
    assert FreeBayesNode.VALIDATE_INPUTS(_indexed_inputs(ploidy=64)) is True
    assert MantaNode.VALIDATE_INPUTS(_indexed_inputs(threads=128)) is True


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


def test_delly_uses_its_documented_call_default_when_mode_is_omitted(
    tmp_path: Path,
) -> None:
    output = tmp_path / "delly"
    inputs = _indexed_inputs(output=output)

    assert "mode" in DellyNode.INPUT_TYPES()["optional"]
    assert DellyNode.VALIDATE_INPUTS(inputs) is True
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


def test_delly_somatic_call_appends_matched_control_bam_after_tumor(
    tmp_path: Path,
) -> None:
    output = tmp_path / "delly"
    inputs = _indexed_inputs(
        output=output,
        normal_bam="/data/normal.bam",
        normal_bam_index="/data/normal.bam.bai",
    )

    assert DellyNode.VALIDATE_INPUTS(inputs) is True
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
        "/data/normal.bam",
    ]


def test_delly_normal_bam_index_is_an_explicit_colocated_sidecar() -> None:
    inputs = _indexed_inputs()

    assert "/data/normal.bam.bai" in str(
        DellyNode.VALIDATE_INPUTS({**inputs, "normal_bam": "/data/normal.bam"})
    )
    assert (
        DellyNode.VALIDATE_INPUTS(
            {**inputs, "normal_bam_index": "/data/normal.bam.bai"}
        )
        == "Input 'normal_bam_index' requires input 'normal_bam'"
    )
    assert "exact colocated index" in str(
        DellyNode.VALIDATE_INPUTS(
            {
                **inputs,
                "normal_bam": "/data/normal.bam",
                "normal_bam_index": "/data/not-normal.bai",
            }
        )
    )


@pytest.mark.parametrize(
    ("bam", "index"),
    [
        ("/data/sample.bam", "/data/sample.bam.csi"),
        ("/data/sample.bam", "/data/sample.csi"),
        ("/data/sample.cram", "/data/sample.cram.crai"),
        ("/data/sample.cram", "/data/sample.crai"),
    ],
)
def test_delly_accepts_htslib_alignment_index_siblings(bam: str, index: str) -> None:
    inputs = _indexed_inputs(bam=bam, bam_index=index, mode="call")

    assert DellyNode.VALIDATE_INPUTS(inputs) is True


@pytest.mark.parametrize("index_suffix", [".csi", ".crai"])
def test_manta_accepts_appended_source_supported_index_siblings(index_suffix: str) -> None:
    bam = "/data/sample.bam"
    inputs = _indexed_inputs(bam=bam, bam_index=f"{bam}{index_suffix}", threads=4)

    assert MantaNode.VALIDATE_INPUTS(inputs) is True


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


def test_delly_rejects_non_default_technology_that_call_mode_would_ignore() -> None:
    inputs = _indexed_inputs(mode="call", technology="not-a-long-read-platform")

    assert DellyNode.VALIDATE_INPUTS(inputs) == "technology must be one of: ont, pb"
    assert DellyNode.VALIDATE_INPUTS(
        {**inputs, "mode": "lr"}
    ) == "technology must be one of: ont, pb"

    assert DellyNode.VALIDATE_INPUTS(
        _indexed_inputs(mode="call", technology="pb")
    ) == "technology is only consumed when mode is 'lr'"


def test_delly_map_qual_matches_the_source_uint16_range() -> None:
    inputs = _indexed_inputs()

    assert DellyNode.VALIDATE_INPUTS({**inputs, "map_qual": 65535}) is True
    assert (
        DellyNode.VALIDATE_INPUTS({**inputs, "map_qual": 65536})
        == "map_qual must be at most 65535"
    )


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


def test_delly_call_keeps_the_matched_control_before_conversion(tmp_path: Path) -> None:
    output = tmp_path / "delly_call"
    inputs = _indexed_inputs(
        output=output,
        normal_bam="/data/normal.bam",
        normal_bam_index="/data/normal.bam.bai",
    )

    command = DellyCallNode.render_command(inputs)

    assert command[:11] == [
        "delly",
        "call",
        "-g",
        "/data/reference.fa",
        "-o",
        str(output / "sv_calls.bcf"),
        "-q",
        "1",
        "/data/sample.bam",
        "/data/normal.bam",
        "&&",
    ]
    assert command[11:] == [
        "bcftools",
        "view",
        "-Oz",
        "-o",
        str(output / "sv_vcf.vcf.gz"),
        str(output / "sv_calls.bcf"),
        "&&",
        "tabix",
        "-f",
        "-p",
        "vcf",
        str(output / "sv_vcf.vcf.gz"),
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


@pytest.mark.parametrize("empty_bam", ["", "   ", b""])
def test_manta_rejects_empty_primary_bam_path(empty_bam: Any) -> None:
    result = MantaNode.VALIDATE_INPUTS(
        _indexed_inputs(bam=empty_bam, bam_index="/data/sample.bam.bai", threads=4)
    )

    assert result is not True
    assert "bam" in str(result)


def test_manta_accepts_the_short_bai_sibling_spelling_from_configure_util() -> None:
    inputs = _indexed_inputs(
        bam_index="/data/sample.bai",
        normal_bam="/data/normal.bam",
        normal_bam_index="/data/normal.bai",
        threads=4,
    )

    assert MantaNode.VALIDATE_INPUTS(inputs) is True


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
async def test_manta_runtime_retry_clears_only_generated_state(
    tmp_path: Path,
) -> None:
    inputs = _indexed_inputs(threads=4)

    class Context:
        node_dir = tmp_path / "run"

        def __init__(self) -> None:
            self.attempt = 0
            self.commands: list[list[str]] = []

        async def run_command(
            self,
            command: list[str],
            **_kwargs: Any,
        ) -> dict[str, Any]:
            self.commands.append(command)
            run_dir = self.node_dir / "manta"
            unrelated = run_dir / "unrelated-user-file.txt"
            if command[0] == "configManta.py":
                if self.attempt:
                    assert not (run_dir / "runWorkflow.py").exists()
                    assert not (run_dir / "runWorkflow.py.config.pickle").exists()
                    assert not (run_dir / "workspace").exists()
                    assert not (run_dir / "results" / "variants" / "partial.vcf.gz").exists()
                    assert unrelated.read_text(encoding="utf-8") == "keep"
                else:
                    unrelated.write_text("keep", encoding="utf-8")
                (run_dir / "runWorkflow.py").write_text("generated", encoding="utf-8")
                (run_dir / "runWorkflow.py.config.pickle").write_bytes(b"generated")
                (run_dir / "workspace").mkdir()
                (run_dir / "workspace" / "partial-state").write_text(
                    "stale",
                    encoding="utf-8",
                )
                return {"returncode": 0, "stdout": "", "stderr": ""}

            self.attempt += 1
            if self.attempt == 1:
                (run_dir / "results" / "variants").mkdir(parents=True, exist_ok=True)
                (run_dir / "results" / "variants" / "partial.vcf.gz").write_bytes(
                    b"stale"
                )
                return {"returncode": 9, "stdout": "", "stderr": "workflow failed"}

            for output in MantaNode.PLAN_OUTPUTS(inputs, self.node_dir):
                output.parent.mkdir(parents=True, exist_ok=True)
                output.write_bytes(b"native Manta artifact")
            return {"returncode": 0, "stdout": "", "stderr": ""}

    context = Context()
    with pytest.raises(RuntimeError, match=r"Manta workflow failed \(exit 9\)"):
        await MantaNode().run(**inputs, context=context)

    result = await MantaNode().run(**inputs, context=context)
    expected = MantaNode.PLAN_OUTPUTS(inputs, context.node_dir)

    assert result == tuple(str(path) for path in expected)
    assert (context.node_dir / "manta" / "unrelated-user-file.txt").exists()
    assert len(context.commands) == 4


@pytest.mark.asyncio
async def test_manta_runtime_refuses_generated_state_symlinks(tmp_path: Path) -> None:
    inputs = _indexed_inputs(threads=4)
    run_dir = tmp_path / "run" / "manta"
    outside = tmp_path / "outside"
    outside.mkdir()
    sentinel = outside / "user-input.bam"
    sentinel.write_bytes(b"keep")
    run_dir.mkdir(parents=True)
    (run_dir / "workspace").symlink_to(outside, target_is_directory=True)

    class Context:
        node_dir = tmp_path / "run"

        async def run_command(
            self,
            _command: list[str],
            **_kwargs: Any,
        ) -> dict[str, Any]:
            raise AssertionError("Manta must fail before executing a command")

    with pytest.raises(RuntimeError, match="Refusing to clear unexpected Manta"):
        await MantaNode().run(**inputs, context=Context())

    assert sentinel.read_bytes() == b"keep"


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
