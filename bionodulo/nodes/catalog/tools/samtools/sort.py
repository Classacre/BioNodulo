"""Typed Samtools ``sort`` catalog node."""

from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path

from bionodulo.nodes.builtin.samtools_family.sort import SamtoolsSortNode
from bionodulo.nodes.contract.artifacts import ArtifactPort, Cardinality
from bionodulo.nodes.contract.model import NodeSpec
from bionodulo.nodes.contract.parameters import ParameterSpec, ValueKind

from .common import build_argv_plan, exact_output, make_spec, threads_parameter


LEGACY_NODE = SamtoolsSortNode
SPEC: NodeSpec = make_spec(
    operation="sort",
    display_name="Samtools Sort",
    description="Sort a SAM or BAM alignment by genomic coordinate.",
    artifact_inputs=(
        ArtifactPort(port_id="alignment", artifact_type="alignment.union", cardinality=Cardinality.ONE),
    ),
    parameters=(
        threads_parameter(),
        ParameterSpec(
            parameter_id="memory_per_thread",
            kind=ValueKind.STRING,
            has_default=True,
            default="768M",
            description="Maximum memory per sorting thread (for example 768M).",
        ),
    ),
    outputs=(exact_output("sorted_bam", "alignment.bam", "sorted_bam.bam"),),
    source_file="bam_sort.c",
    source_symbol="bam_sort",
    factory="bionodulo.nodes.catalog.tools.samtools.sort:build_plan",
)


def build_plan(inputs: Mapping[str, object], output_dir: str | Path = "."):
    return build_argv_plan(LEGACY_NODE, inputs, output_dir)


async def run_legacy(**inputs: object):
    return await LEGACY_NODE().run(**inputs)


__all__ = ["LEGACY_NODE", "SPEC", "build_plan", "run_legacy"]
