"""Typed Samtools ``markdup`` catalog node."""

from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path

from bionodulo.nodes.builtin.samtools_family.markdup import SamtoolsMarkdupNode
from bionodulo.nodes.contract.artifacts import ArtifactPort, Cardinality
from bionodulo.nodes.contract.model import NodeSpec
from bionodulo.nodes.contract.parameters import ParameterSpec, ValueKind

from .common import build_argv_plan, exact_output, make_spec, threads_parameter


LEGACY_NODE = SamtoolsMarkdupNode
SPEC: NodeSpec = make_spec(
    operation="markdup",
    display_name="Samtools Markdup",
    description="Mark or remove duplicate alignments.",
    artifact_inputs=(
        ArtifactPort(port_id="bam", artifact_type="alignment.bam", cardinality=Cardinality.ONE),
    ),
    parameters=(
        threads_parameter(),
        ParameterSpec(
            parameter_id="remove_duplicates",
            kind=ValueKind.BOOLEAN,
            has_default=True,
            default=False,
            description="Remove duplicates instead of only marking them.",
        ),
        ParameterSpec(
            parameter_id="mark_supplementary",
            kind=ValueKind.BOOLEAN,
            has_default=True,
            default=False,
            description="Mark duplicate supplementary alignments.",
        ),
        ParameterSpec(
            parameter_id="optical_distance",
            kind=ValueKind.INTEGER,
            has_default=True,
            default=0,
            minimum=0,
            description="Optical duplicate distance; zero disables optical detection.",
        ),
        ParameterSpec(
            parameter_id="read_coords",
            kind=ValueKind.STRING,
            has_default=True,
            default="",
            description="Read-name coordinate extraction pattern.",
        ),
        ParameterSpec(
            parameter_id="clear_existing",
            kind=ValueKind.BOOLEAN,
            has_default=True,
            default=False,
            description="Clear existing duplicate tags before processing.",
        ),
    ),
    outputs=(
        exact_output("marked_bam", "alignment.bam", "marked_bam.bam"),
        exact_output("duplicate_stats", "statistics.text", "duplicate_stats.stats.txt"),
    ),
    source_file="bam_markdup.c",
    source_symbol="mark_duplicates",
    factory="bionodulo.nodes.catalog.tools.samtools.markdup:build_plan",
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
