"""HUMAnN must never share a Pixi environment with bowtie2.

The bioconda `humann` package vendors bowtie2 2.2.3 binaries at the same file
paths the real `bowtie2` package owns. In a merged environment the last package
unpacked wins, so a lock pinning bowtie2 2.5.5 can still put 2.2.3 on PATH. The
only symptom is "Encountered internal Bowtie 2 exception (#1)", which names
neither package nor version -- so this needs a test, not a comment.
"""

from __future__ import annotations

from bionodulo.environments.manifest import workflow_to_environment_plan
from bionodulo.nodes.builtin.humann_family.humann import HUMAnNNode


def _plan(node_types: list[str]):
    workflow = {
        "nodes": [
            {"id": f"{node_type}_001", "type": node_type} for node_type in node_types
        ]
    }
    from bionodulo.nodes.registry import NodeRegistry

    registry = NodeRegistry()
    registry.load_builtin_nodes()
    return workflow_to_environment_plan(workflow, registry)


def test_humann_declares_an_isolated_pixi_environment() -> None:
    assert HUMAnNNode.ENVIRONMENT == {"type": "pixi", "name": "humann"}


def test_humann_never_lands_in_the_same_environment_as_bowtie2() -> None:
    plan = _plan(["humann", "metaphlan", "metaphlan_build_index"])

    default = set(plan.default_packages)
    named = dict(plan.named_environments)

    assert "bowtie2" in default, "the build node still needs a real bowtie2"
    assert "humann" not in default, "humann would clobber bowtie2 in a shared env"
    assert named["humann"] == ("humann", "python")


def test_humann_alone_still_gets_its_environment() -> None:
    """A workflow with no bowtie2 consumer must not silently merge it back."""
    plan = _plan(["humann"])

    assert plan.default_packages == ()
    assert dict(plan.named_environments)["humann"] == ("humann", "python")


def test_python_is_pinned_so_the_humann_build_matches_its_interpreter() -> None:
    """bioconda humann 3.9 is a py312 build declaring only `python >=3`.

    Left unpinned the solver picks 3.13, humann's modules land in
    lib/python3.12/site-packages, and `humann` dies with ModuleNotFoundError.
    """
    from bionodulo.environments.constants import PACKAGE_MIN_VERSIONS

    assert PACKAGE_MIN_VERSIONS["python"] == "3.12.*"
