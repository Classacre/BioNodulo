"""MetaPhlAn's Bowtie2 index must be buildable in-workflow.

Published MetaPhlAn database bundles ship the marker FASTA and the .pkl but no
Bowtie2 index -- it is normally built by an implicit download-and-build on first
use. BioNodulo runs offline, and MetaPhlAnNode fails closed on a missing index
("missing required index sidecar(s)"), so the build must be an explicit step.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from bionodulo.nodes.builtin.metaphlan_family import MetaPhlAnBuildIndexNode
from bionodulo.nodes.builtin.metaphlan_family.metaphlan import MetaPhlAnNode

INDEX = "mpa_vJan21_TOY_CHOCOPhlAnSGB_202103"


def test_suffixes_match_what_the_profiler_demands() -> None:
    """A divergence would let the build 'succeed' while the profiler still fails."""
    assert MetaPhlAnBuildIndexNode.INDEX_SUFFIXES == MetaPhlAnNode.DATABASE_INDEX_SUFFIXES


def test_command_expands_the_bzipped_fasta_and_forces_a_large_index(tmp_path: Path) -> None:
    """The bundle ships <index>_SGB.fna.bz2, and the profiler wants bt2l members.

    Verified against the real TOY bundle: bowtie2-build --large-index produces
    exactly the six .bt2l files MetaPhlAn requires.
    """
    command = MetaPhlAnBuildIndexNode.render_command(
        {"database": "/data/mpa", "index": INDEX, "output": str(tmp_path / "n"), "threads": 4}
    )
    assert "bunzip2 -k" in command
    # Globs the bundle's own *.fna.bz2 rather than assuming one filename, then
    # asserts the marker FASTA exists: a missing one otherwise surfaces only as
    # "Encountered internal Bowtie 2 exception (#1)", which names no cause.
    assert "*.fna.bz2" in command
    assert f'if [ ! -s "{INDEX}_SGB.fna" ]' in command
    assert "--large-index" in command
    assert command.startswith("set -e;")


def test_output_directory_is_returned_so_the_profiler_can_consume_it(tmp_path: Path) -> None:
    """MetaPhlAn discovers the index by name under the directory it is handed."""
    # The runner passes the node directory as `output`, which is the parent of
    # what PLAN_OUTPUTS returns for the run root -- pass it the same way here.
    node_root = tmp_path / MetaPhlAnBuildIndexNode.NODE_ID
    inputs = {"database": "/data/mpa", "index": INDEX, "output": str(node_root)}
    outputs = MetaPhlAnBuildIndexNode.PLAN_OUTPUTS(inputs, tmp_path)

    assert len(outputs) == 1
    assert outputs[0].is_dir()
    assert str(outputs[0]) in MetaPhlAnBuildIndexNode.render_command(inputs)
    assert MetaPhlAnBuildIndexNode.RETURN_NAMES == ("database",)


def test_a_partial_index_is_rejected(tmp_path: Path) -> None:
    """Five of six members would fail later, inside MetaPhlAn, less clearly."""
    database = tmp_path / "database"
    database.mkdir()
    for suffix in MetaPhlAnBuildIndexNode.INDEX_SUFFIXES[:-1]:
        (database / f"{INDEX}{suffix}").write_bytes(b"x")

    with pytest.raises(ValueError, match="did not produce"):
        MetaPhlAnBuildIndexNode.VERIFY_OUTPUTS({"index": INDEX}, [database])

    (database / f"{INDEX}{MetaPhlAnBuildIndexNode.INDEX_SUFFIXES[-1]}").write_bytes(b"x")
    MetaPhlAnBuildIndexNode.VERIFY_OUTPUTS({"index": INDEX}, [database])


def test_missing_inputs_are_rejected() -> None:
    assert MetaPhlAnBuildIndexNode.VALIDATE_INPUTS({"index": INDEX}) is not True
