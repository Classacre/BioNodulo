"""Krona's taxonomy database must be buildable in-workflow.

KronaTools publishes no prebuilt taxonomy.tab -- only updateTaxonomy.sh, which
fetches NCBI's taxdump and runs extractTaxonomy.pl. Without this node every
Krona workflow depends on a file the user builds by hand.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from bionodulo.nodes.builtin.metagenomics_family import KronaBuildTaxonomyNode


def test_planned_output_matches_the_directory_the_command_writes(tmp_path: Path) -> None:
    """A mismatch here makes the tool succeed while the declared output is absent."""
    inputs = {"taxdump": "/data/taxdump.tar.gz", "output": str(tmp_path / "krona_build_taxonomy")}
    outputs = KronaBuildTaxonomyNode.PLAN_OUTPUTS(inputs, tmp_path)

    assert outputs[0].name == "taxonomy.tab"
    assert outputs[0].parent.name == "taxonomy"
    assert str(outputs[0].parent) in KronaBuildTaxonomyNode.render_command(inputs)


def test_archive_and_directory_inputs_are_both_handled(tmp_path: Path) -> None:
    """NCBI ships taxdump.tar.gz; a pre-extracted directory is also valid."""
    command = KronaBuildTaxonomyNode.render_command(
        {"taxdump": "/data/taxdump.tar.gz", "output": str(tmp_path / "n")}
    )
    assert "tar -xmf" in command
    assert "*.dmp" in command  # directory branch copies the dumps instead
    assert "extractTaxonomy.pl" in command


def test_extractor_is_located_relative_to_the_installed_tool(tmp_path: Path) -> None:
    """Resolve via ktImportTaxonomy so it works wherever conda placed the env.

    Hard-coding a prefix breaks as soon as the environment path changes; this was
    verified against the real conda layout, where the script sits at
    <env>/opt/krona/scripts/extractTaxonomy.pl.
    """
    command = KronaBuildTaxonomyNode.render_command(
        {"taxdump": "/data/taxdump.tar.gz", "output": str(tmp_path / "n")}
    )
    assert "command -v ktImportTaxonomy" in command
    assert "opt/krona/scripts/extractTaxonomy.pl" in command


def test_empty_taxonomy_is_rejected(tmp_path: Path) -> None:
    """An empty taxonomy.tab yields a silently blank chart, so fail loudly."""
    outputs = [tmp_path / "taxonomy.tab"]
    outputs[0].write_text("", encoding="utf-8")
    with pytest.raises(ValueError, match="empty"):
        KronaBuildTaxonomyNode.VERIFY_OUTPUTS({}, outputs)

    outputs[0].write_text("1\troot\n", encoding="utf-8")
    KronaBuildTaxonomyNode.VERIFY_OUTPUTS({}, outputs)


def test_missing_taxdump_is_rejected() -> None:
    assert KronaBuildTaxonomyNode.VALIDATE_INPUTS({"output": "/tmp/x"}) is not True
