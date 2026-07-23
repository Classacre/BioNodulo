"""Typed Samtools ``flagstat`` catalog node."""

from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path

from bionodulo.nodes.builtin.samtools_family.flagstat import SamtoolsFlagstatNode
from bionodulo.nodes.contract.artifacts import ArtifactPort, Cardinality
from bionodulo.nodes.contract.model import NodeSpec

from .common import build_argv_plan, make_spec, stdout_output, threads_parameter


LEGACY_NODE = SamtoolsFlagstatNode
SPEC: NodeSpec = make_spec(
    operation="flagstat",
    display_name="Samtools Flagstat",
    description="Generate alignment statistics with samtools flagstat.",
    artifact_inputs=(
        ArtifactPort(port_id="bam", artifact_type="alignment.bam", cardinality=Cardinality.ONE),
    ),
    parameters=(threads_parameter(default=2),),
    outputs=(stdout_output("stats", "statistics.text", "stats.stats.txt"),),
    source_file="bam_stat.c",
    source_symbol="bam_flagstat",
    factory="bionodulo.nodes.catalog.tools.samtools.flagstat:build_plan",
)


def build_plan(inputs: Mapping[str, object], output_dir: str | Path = "."):
    return build_argv_plan(LEGACY_NODE, inputs, output_dir)


async def run_legacy(**inputs: object):
    return await LEGACY_NODE().run(**inputs)


__all__ = ["LEGACY_NODE", "SPEC", "build_plan", "run_legacy"]
