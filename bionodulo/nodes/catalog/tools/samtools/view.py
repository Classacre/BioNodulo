"""Typed Samtools ``view`` catalog node."""

from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path

from bionodulo.nodes.builtin.samtools_family.view import SamtoolsViewNode
from bionodulo.nodes.contract.artifacts import ArtifactPort, Cardinality
from bionodulo.nodes.contract.model import NodeSpec
from bionodulo.nodes.contract.parameters import ParameterSpec, ValueKind

from .common import build_argv_plan, exact_output, make_spec, threads_parameter


LEGACY_NODE = SamtoolsViewNode
SPEC: NodeSpec = make_spec(
    operation="view",
    display_name="Samtools View",
    description="Convert SAM or BAM alignments to BAM and filter by flags.",
    artifact_inputs=(
        ArtifactPort(port_id="alignment", artifact_type="alignment.union", cardinality=Cardinality.ONE),
    ),
    parameters=(
        threads_parameter(),
        ParameterSpec(
            parameter_id="require_all_flags",
            kind=ValueKind.INTEGER,
            minimum=0,
            maximum=65535,
            description="Require all SAM flag bits in a read.",
        ),
        ParameterSpec(
            parameter_id="exclude_any_flags",
            kind=ValueKind.INTEGER,
            minimum=0,
            maximum=65535,
            description="Exclude reads carrying any of these SAM flag bits.",
        ),
    ),
    outputs=(exact_output("bam", "alignment.bam", "bam.bam"),),
    source_file="sam_view.c",
    source_symbol="sam_view",
    factory="bionodulo.nodes.catalog.tools.samtools.view:build_plan",
)


def build_plan(inputs: Mapping[str, object], output_dir: str | Path = "."):
    """Return a validated immutable argv plan using the legacy renderer."""

    return build_argv_plan(LEGACY_NODE, inputs, output_dir)


async def run_legacy(**inputs: object):
    """Execute through the already-tested CommandNode bridge."""

    return await LEGACY_NODE().run(**inputs)


__all__ = ["LEGACY_NODE", "SPEC", "build_plan", "run_legacy"]
