"""Typed Samtools ``index`` catalog node."""

from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path

from bionodulo.nodes.builtin.samtools_family.index import SamtoolsIndexNode
from bionodulo.nodes.contract.artifacts import ArtifactPort, Cardinality
from bionodulo.nodes.contract.model import NodeSpec

from .common import build_argv_plan, exact_output, make_spec, threads_parameter


LEGACY_NODE = SamtoolsIndexNode
SPEC: NodeSpec = make_spec(
    operation="index",
    display_name="Samtools Index",
    description="Create a BAI index for a coordinate-sorted BAM.",
    artifact_inputs=(
        ArtifactPort(port_id="bam", artifact_type="alignment.bam", cardinality=Cardinality.ONE),
    ),
    parameters=(threads_parameter(default=2),),
    outputs=(
        exact_output("indexed_bam", "alignment.bam", "indexed_bam.bam"),
        exact_output("bai", "alignment.bai", "indexed_bam.bam.bai"),
    ),
    source_file="bam_index.c",
    source_symbol="sam_index",
    factory="bionodulo.nodes.catalog.tools.samtools.index:build_plan",
)


def build_plan(
    inputs: Mapping[str, object] | None = None,
    output_dir: str | Path = ".",
    **kwargs: object,
):
    values = dict(inputs or {})
    values.update(kwargs)
    return build_argv_plan(LEGACY_NODE, values, output_dir)


async def run_legacy(**inputs: object):
    return await LEGACY_NODE().run(**inputs)


__all__ = ["LEGACY_NODE", "SPEC", "build_plan", "run_legacy"]
