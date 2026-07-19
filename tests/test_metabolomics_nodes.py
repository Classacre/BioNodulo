"""Compact contracts for the four non-template metabolomics operations."""

from __future__ import annotations

from pathlib import Path

import pytest

from bionodulo.nodes.builtin.metabolomics_family import (
    MSDIALProcessingNode,
    MZmineBatchProcessingNode,
    MetaboAnalystStatsNode,
    SiriusFormulaIDNode,
)
from bionodulo.nodes.registry import NodeRegistry


NEW_NODES = (
    SiriusFormulaIDNode,
    MZmineBatchProcessingNode,
    MetaboAnalystStatsNode,
    MSDIALProcessingNode,
)


def test_metabolomics_nodes_have_focused_ownership_and_pinned_authorities() -> None:
    assert {node.NODE_ID for node in NEW_NODES} == {
        "sirius_formula_id",
        "mzmine_batch_processing",
        "metaboanalyst_stats",
        "msdial_processing",
    }
    assert all(node.__module__.startswith("bionodulo.nodes.builtin.metabolomics_family.") for node in NEW_NODES)
    assert SiriusFormulaIDNode.GIT_COMMIT == "03af898a944ada6527bbbabd8f85e2e00c6c4d5b"
    assert SiriusFormulaIDNode.REQUIRED_EXECUTABLES == []
    assert SiriusFormulaIDNode.EXTERNAL_REQUIRED_EXECUTABLES == ("sirius",)
    assert SiriusFormulaIDNode.REQUIRED_CONDA_PACKAGES == []
    assert MZmineBatchProcessingNode.VERSION == "4.7.29"
    assert MZmineBatchProcessingNode.GIT_COMMIT == "d780c98fd0689fea47839d0a7975f259a80e5634"
    assert MetaboAnalystStatsNode.VERSION == "4.2.0"
    assert MetaboAnalystStatsNode.GIT_COMMIT == "89dd939c7a5c6bb1b87a241c332e89a378048cd3"
    assert MSDIALProcessingNode.VERSION == "4.92"
    assert MSDIALProcessingNode.GIT_COMMIT == "dd3a03f6fca266978211eb96aef4332744819568"


def test_registry_exposes_native_output_contracts() -> None:
    registry = NodeRegistry.create_isolated()
    registry.load_builtin_nodes()
    info = registry.object_info()

    assert info["sirius_formula_id"]["output_name"] == ["project_space"]
    assert info["mzmine_batch_processing"]["input"]["required"]["user_file"][0] == "FILE"
    assert info["mzmine_batch_processing"]["output_name"] == ["results_dir"]
    assert info["metaboanalyst_stats"]["output_name"] == [
        "normalized_table",
        "pca_scores",
        "pca_loadings",
        "test_results",
        "metaboanalyst_object",
        "summary",
    ]
    assert info["msdial_processing"]["input"]["required"]["msdial_executable"][0] == "FILE"
    assert info["msdial_processing"]["output_name"] == ["results_dir"]


def test_sirius_cli_places_options_under_their_documented_subcommands() -> None:
    assert SiriusFormulaIDNode.render_command(
        {
            "spectra_file": "input.ms",
            "cores": 8,
            "profile": "orbitrap",
            "ppm_max": 10,
            "formula_database": "BIO",
            "ions_enforced": "[M+H]+",
            "run_zodiac": True,
            "run_structure": True,
            "structure_database": "ALL",
            "run_canopus": True,
            "output_name": "sample one",
            "output": "/work/sirius",
        }
    ) == [
        "sirius",
        "--input",
        "input.ms",
        "--output",
        "/work/sirius/sample_one",
        "--cores",
        "8",
        "formula",
        "--profile",
        "orbitrap",
        "--ppm-max",
        "10",
        "--database",
        "BIO",
        "--ions-enforced",
        "[M+H]+",
        "zodiac",
        "structure",
        "--database",
        "ALL",
        "canopus",
    ]
    with pytest.raises(ValueError, match="either 'ions_considered' or 'ions_enforced'"):
        SiriusFormulaIDNode.render_command(
            {"spectra_file": "input.ms", "ions_considered": "[M+H]+", "ions_enforced": "[M+Na]+"}
        )


def test_mzmine_and_msdial_use_explicit_staged_state(tmp_path: Path) -> None:
    mzmine_out = tmp_path / "mzmine"
    mzmine_command = MZmineBatchProcessingNode.render_command(
        {
            "batch_file": "workflow.mzbatch",
            "user_file": "analyst.mzuser",
            "input_files": ["a.mzML", "b.mzML"],
            "preferences_file": "prefs.mzconfig",
            "threads": 4,
            "memory_mode": "none",
            "output_name": "study",
            "output": str(mzmine_out),
        }
    )
    assert mzmine_command == [
        "mzmine",
        "-user",
        "analyst.mzuser",
        "-batch",
        "workflow.mzbatch",
        "-input",
        str(mzmine_out / "study.input_files.txt"),
        "-output",
        str(mzmine_out / "study" / "study"),
        "-pref",
        "prefs.mzconfig",
        "-memory",
        "none",
        "-threads",
        "4",
    ]
    assert (mzmine_out / "study.input_files.txt").read_text(encoding="utf-8") == "a.mzML\nb.mzML\n"
    with pytest.raises(ValueError, match="user_file"):
        MZmineBatchProcessingNode.render_command({"batch_file": "workflow.mzbatch", "user_file": ""})

    assert MSDIALProcessingNode.render_command(
        {
            "msdial_executable": "/tools/MsdialConsoleApp.exe",
            "input_dir": "/inputs",
            "parameter_file": "/params/method.txt",
            "analysis_type": "lcmsdia",
            "keep_project_file": True,
            "multi_collision_energy": True,
            "target_mz": 500.2,
            "output_name": "dia",
            "output": "/work/msdial",
        }
    ) == [
        "mono",
        "/tools/MsdialConsoleApp.exe",
        "lcmsdia",
        "-i",
        "/inputs",
        "-o",
        "/work/msdial/dia",
        "-m",
        "/params/method.txt",
        "-p",
        "-mCE",
        "-target",
        "500.2",
    ]


def test_metaboanalyst_script_matches_420_function_signatures(tmp_path: Path) -> None:
    output = tmp_path / "stats"
    command = MetaboAnalystStatsNode.render_command(
        {
            "data_table": "/inputs/metabolites.csv",
            "test_method": "wilcox",
            "p_threshold": 0.01,
            "run_pca": True,
            "run_ttest": True,
            "output": str(output),
        }
    )
    assert command == ["Rscript", str(output / "metaboanalyst_stats.R")]
    script = (output / "metaboanalyst_stats.R").read_text(encoding="utf-8")
    assert "Ttests.Anal(" in script
    assert "nonpar = TRUE" in script
    assert "equal.var = FALSE" in script
    assert "tt.method" not in script
    assert "mSet$analSet$tt" in script
    assert "feature = names(tt$p.value)" in script
    assert len(MetaboAnalystStatsNode.PLAN_OUTPUTS({"data_table": "metabolites.csv"}, tmp_path)) == 6
