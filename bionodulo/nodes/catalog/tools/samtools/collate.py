"""Typed Samtools ``collate`` catalog node."""

from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path

from bionodulo.nodes.builtin.samtools_family.collate import SamtoolsCollateNode
from bionodulo.nodes.contract.artifacts import ArtifactPort, Cardinality
from bionodulo.nodes.contract.model import NodeSpec

from .common import build_argv_plan, exact_output, make_spec, threads_parameter


LEGACY_NODE = SamtoolsCollateNode
SPEC: NodeSpec = make_spec(
    operation="collate",
    display_name="Samtools Collate",
    description="Name-collate a BAM before samtools fixmate.",
    artifact_inputs=(
        ArtifactPort(port_id="bam", artifact_type="alignment.bam", cardinality=Cardinality.ONE),
    ),
    parameters=(threads_parameter(),),
    outputs=(exact_output("name_collated_bam", "alignment.bam", "name_collated_bam.bam"),),
    source_file="bamshuf.c",
    source_symbol="bamshuf",
    factory="bionodulo.nodes.catalog.tools.samtools.collate:build_plan",
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
