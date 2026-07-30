"""A node's declared package constraint must reach the environment solver.

`CONDA_PACKAGE_CONSTRAINTS` on a node is documentation; the solver reads
`PACKAGE_MIN_VERSIONS`. When a package appears only in the former it is
effectively unconstrained, and the solver is free to install a version the node
cannot use. That is how NanoPlot ended up with kaleido 1.3 -- it declared
`python-kaleido: 0.2.1` and got `*`, so the run died at import with
ModuleNotFoundError before reading a single read.

This does not require the two to be identical: several packages legitimately
differ in form (`1.23.1` vs `==1.23.1`) or deliberately (a node's ceiling vs a
workflow-wide floor). It requires only that the solver has *some* pin, so a
declared constraint can never be silently ignored.
"""

from __future__ import annotations

from bionodulo.environments.constants import PACKAGE_MIN_VERSIONS
from bionodulo.nodes.registry import NodeRegistry


def test_every_node_constrained_package_is_pinned_for_the_solver() -> None:
    registry = NodeRegistry()
    registry.load_builtin_nodes()

    unpinned: dict[str, list[str]] = {}
    for node_id, node_class in registry._nodes.items():
        constraints = getattr(node_class, "CONDA_PACKAGE_CONSTRAINTS", None)
        if not isinstance(constraints, dict):
            continue
        for package, declared in constraints.items():
            # A node declaring "*" is asking for no pin, so the solver agreeing
            # is correct, not drift (odgi_build does this for bash).
            if str(declared).strip() == "*":
                continue
            if PACKAGE_MIN_VERSIONS.get(package, "*") == "*":
                unpinned.setdefault(package, []).append(node_id)

    assert not unpinned, (
        "these packages are constrained by a node but left unpinned for the "
        "solver, so the constraint has no effect: "
        + "; ".join(f"{pkg} (e.g. {nodes[0]})" for pkg, nodes in sorted(unpinned.items()))
    )


def test_nanoplot_pins_kaleido_below_the_breaking_release() -> None:
    """The concrete regression: kaleido 1.x removed `kaleido.scopes.plotly`."""
    from bionodulo.nodes.builtin.long_read_family.nanoplot import NanoPlotQCNode

    assert "python-kaleido" in NanoPlotQCNode.REQUIRED_CONDA_PACKAGES
    assert PACKAGE_MIN_VERSIONS["python-kaleido"].startswith("0.")
