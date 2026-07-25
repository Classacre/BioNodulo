"""Source-backed BayeScan 2.1 contract checks."""

from __future__ import annotations

from pathlib import Path

import pytest

from bionodulo.nodes.builtin._variant_assembly_contracts import TOOL_EVIDENCE
from bionodulo.nodes.builtin.bayescan_family import BayeScanGalaxyNode, BayeScanNode
from bionodulo.nodes.registry import NodeRegistry


@pytest.mark.parametrize("node_class", [BayeScanNode, BayeScanGalaxyNode])
def test_bayescan_aliases_share_the_verified_archive_authority(node_class: type[BayeScanNode]) -> None:
    authority = TOOL_EVIDENCE["bayescan"]
    assert authority.source_sha256 == (
        "c6bbc52a5a6a30e895951faf2bd6291ca47fdccdc708e693fce02389548d5547"
    )
    assert node_class.SOURCE_SHA256 == authority.source_sha256
    assert node_class.SOURCE_PATHS == ("source/start.cpp", "source/read_write.cpp")
    assert node_class.DOCUMENTATION_LOCATOR == "BayeScan2.1_manual.pdf pages 3-4 and 8"
    assert "without options prints usage and exits 0" in node_class.EXIT_SEMANTICS
    registry = NodeRegistry.create_isolated()
    registry.load_builtin_nodes()
    assert registry.get(node_class.NODE_ID) is node_class


def test_bayescan_uses_the_documented_snp_fstat_and_thread_options() -> None:
    command = BayeScanNode.render_command(
        {
            "input": "population.txt",
            "snp_genotypes_matrix": True,
            "fstats": True,
            "threads": 6,
            "output": "/work/bayescan",
        }
    )
    assert command[command.index("-snp") : command.index("-snp") + 2] == ["-snp", "-fstat"]
    assert command[command.index("-threads") : command.index("-threads") + 2] == [
        "-threads",
        "6",
    ]


def test_bayescan_plans_native_summary_trace_and_sparse_optional_outputs(tmp_path: Path) -> None:
    normal = BayeScanNode.PLAN_OUTPUTS(
        {"pilot_runs": True, "allele_frequency": True},
        tmp_path,
    )
    mapped = BayeScanNode.MAP_PLANNED_OUTPUTS(normal)
    assert set(mapped) == {
        "log",
        "selection",
        "mcmc_trace",
        "verification",
        "acceptance_rate",
        "pilot_runs",
        "allele_frequencies",
    }
    assert Path(mapped["selection"]).name == "bayescan_fst.txt"
    assert Path(mapped["mcmc_trace"]).name == "bayescan.sel"

    fstats = BayeScanNode.MAP_PLANNED_OUTPUTS(
        BayeScanNode.PLAN_OUTPUTS({"fstats": True}, tmp_path)
    )
    assert "selection" not in fstats
    assert Path(fstats["mcmc_trace"]).name == "bayescan.sel"


@pytest.mark.parametrize(
    ("inputs", "message"),
    [
        ({}, "input genotype data file"),
        ({"input": "population.txt", "threads": 0}, "threads must be >= 1"),
        (
            {"input": "population.txt", "lower_prior": 0.8, "higher_prior": 0.2},
            "lower_prior and higher_prior",
        ),
        ({"input": "population.txt", "prior_odds": 0}, "prior_odds must be > 0"),
    ],
)
def test_bayescan_rejects_inputs_the_pinned_source_cannot_use(
    inputs: dict[str, object],
    message: str,
) -> None:
    assert message in str(BayeScanNode.VALIDATE_INPUTS(inputs))
