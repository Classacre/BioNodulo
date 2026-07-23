"""Typed Samtools ``fixmate`` catalog node."""

from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path

from bionodulo.nodes.builtin.samtools_family.fixmate import SamtoolsFixmateNode
from bionodulo.nodes.contract.artifacts import ArtifactPort, Cardinality
from bionodulo.nodes.contract.model import NodeSpec
from bionodulo.nodes.contract.parameters import ParameterSpec, ValueKind

from .common import build_argv_plan, exact_output, make_spec, threads_parameter


LEGACY_NODE = SamtoolsFixmateNode
SPEC: NodeSpec = make_spec(
    operation="fixmate",
    display_name="Samtools Fixmate",
    description="Add mate coordinates to a name-collated BAM.",
    artifact_inputs=(
        ArtifactPort(port_id="bam", artifact_type="alignment.bam", cardinality=Cardinality.ONE),
    ),
    parameters=(
        threads_parameter(),
        ParameterSpec(
            parameter_id="add_markdup_tags",
            kind=ValueKind.BOOLEAN,
            has_default=True,
            default=False,
            description="Add duplicate-marking tags required by samtools markdup.",
        ),
        ParameterSpec(
            parameter_id="remove_secondary_unmapped",
            kind=ValueKind.BOOLEAN,
            has_default=True,
            default=False,
            description="Remove secondary and unmapped records.",
        ),
    ),
    outputs=(exact_output("fixmate_bam", "alignment.bam", "fixmate_bam.bam"),),
    source_file="bam_mate.c",
    source_symbol="bam_mating",
    factory="bionodulo.nodes.catalog.tools.samtools.fixmate:build_plan",
)


def build_plan(inputs: Mapping[str, object], output_dir: str | Path = "."):
    return build_argv_plan(LEGACY_NODE, inputs, output_dir)


async def run_legacy(**inputs: object):
    return await LEGACY_NODE().run(**inputs)


__all__ = ["LEGACY_NODE", "SPEC", "build_plan", "run_legacy"]
