"""Compact contracts for the focused amplicon and trimming wrapper family."""

from __future__ import annotations

import hashlib
import re
from pathlib import Path

from bionodulo.nodes.builtin import wrapped_amplicon_trimming_family as family
from bionodulo.nodes.builtin.wrapped_amplicon_trimming_family.assets import ASSET_DIR
from bionodulo.nodes.builtin.wrapped_amplicon_trimming_family.evidence import (
    ASSET_EVIDENCE,
    NODE_EVIDENCE,
    TOOLS_IUC_COMMIT,
)
from bionodulo.nodes.builtin.wrapped_amplicon_trimming_family.vsearch_adapter import (
    VSearchNodeBase,
)


EXPECTED_IDS = {
    "adapter_removal",
    "aldex2",
    "ancombc",
    "angsd",
    "angsd_contamination",
    "ampvis2_alpha_diversity",
    "ampvis2_boxplot",
    "ampvis2_core",
    "ampvis2_export_fasta",
    "ampvis2_export_otu",
    "ampvis2_frequency",
    "ampvis2_heatmap",
    "ampvis2_load",
    "ampvis2_merge_ampvis2",
    "ampvis2_mergereplicates",
    "ampvis2_octave",
    "ampvis2_ordinate",
    "ampvis2_otu_network",
    "ampvis2_rankabundance",
    "ampvis2_rarecurve",
    "ampvis2_setmetadata",
    "ampvis2_subset_samples",
    "ampvis2_subset_taxa",
    "ampvis2_timeseries",
    "ampvis2_venn",
    "megahit_contig2fastg",
    "miniasm",
    "prinseq",
    "trimn",
    "trimns",
    "vsearch_alignment",
    "vsearch_chimera_detection",
    "vsearch_cluster",
    "vsearch_dereplication",
    "vsearch_masking",
    "vsearch_search",
    "vsearch_shuffling",
    "vsearch_sorting",
}


def _nodes() -> list[type]:
    return [getattr(family, name) for name in family.__all__]


def _value_after(command: list[str], flag: str) -> str:
    return command[command.index(flag) + 1]


def test_stable_ids_survive_semantic_relocation() -> None:
    nodes = _nodes()
    assert len(nodes) == 38
    assert {node.NODE_ID for node in nodes} == EXPECTED_IDS
    assert len({node.NODE_ID for node in nodes}) == len(nodes)
    assert all(".wrapped_" not in node.__module__ for node in nodes)


def test_every_contract_has_exact_wrapper_packages_and_failure_semantics() -> None:
    for node in _nodes():
        evidence = NODE_EVIDENCE[node.NODE_ID]
        package_names = [re.split(r"[<>=!~]", spec, maxsplit=1)[0] for spec in evidence.package_constraints]

        assert node.VERSION == evidence.version
        assert node.WRAPPER_GIT_COMMIT == TOOLS_IUC_COMMIT
        assert node.WRAPPER_SOURCE == evidence.wrapper_path
        assert node.WRAPPER_TOOL_ID == (evidence.wrapper_id or node.NODE_ID)
        assert node.SOURCE_URL == evidence.source_url
        assert node.PACKAGE_CONSTRAINTS == evidence.package_constraints
        assert [name.lower() for name in node.REQUIRED_CONDA_PACKAGES] == [
            name.lower() for name in package_names
        ]
        assert node.WRAPPER_ERROR_DETECTION == evidence.error_detection
        assert node.EXIT_SEMANTICS
        assert node.AUDIT_STATUS == "contract-checked-no-external-execution"


def test_vendored_assets_match_pinned_hashes_and_resolve_at_runtime() -> None:
    for name, evidence in ASSET_EVIDENCE.items():
        path = ASSET_DIR / name
        assert path.is_absolute()
        assert path.is_file()
        assert hashlib.sha256(path.read_bytes()).hexdigest() == evidence.sha256
        assert f"/{TOOLS_IUC_COMMIT}/" in evidence.source_url

    defaults = {
        family.ALDEx2Node: "aldex2.R",
        family.ANCOMBCNode: "ancombc.R",
        family.ANGSDContaminationNode: "print_x_contamination.py",
    }
    for node, filename in defaults.items():
        # The widget default must stay blank. A non-empty absolute path is
        # frozen into node_metadata.json at generation time and would ship the
        # build host's directory layout to every client and cloud worker.
        assert node.INPUT_TYPES()["optional"]["script_path"][1]["default"] == ""
        # The vendored asset is resolved at render time instead.
        command = node.render_command({"output": "/work/out"})
        rendered = command if isinstance(command, str) else " ".join(command)
        assert str(ASSET_DIR / filename) in rendered


def test_ampvis2_variable_plots_use_image_ports_and_valid_ggsave_calls() -> None:
    plot_nodes = [
        node
        for node in _nodes()
        if node.NODE_ID.startswith("ampvis2_") and hasattr(node, "OUT_FORMATS")
    ]
    assert len(plot_nodes) == 12
    for node in plot_nodes:
        assert "PDF" not in node.RETURN_TYPES
        command = node.render_command(
            {"data": "ampvis.rds", "output": f"/work/{node.NODE_ID}"}
        )
        assert "ggsave(" in command
        assert re.search(r",\s*,", command) is None


def test_named_conditional_outputs_are_mapped_without_position_guessing(tmp_path: Path) -> None:
    heatmap_paths = family.Ampvis2HeatmapNode.PLAN_OUTPUTS({"out_format": "tabular"}, tmp_path)
    assert family.Ampvis2HeatmapNode.MAP_PLANNED_OUTPUTS(heatmap_paths) == {
        "plot_raw": heatmap_paths[0]
    }

    export_paths = family.Ampvis2ExportOtuNode.PLAN_OUTPUTS(
        {"output_selection": ["tax", "phyloseq"]},
        tmp_path,
    )
    assert family.Ampvis2ExportOtuNode.MAP_PLANNED_OUTPUTS(export_paths) == {
        "tax": export_paths[0],
        "phyloseq": export_paths[1],
    }

    load_paths = family.Ampvis2LoadNode.PLAN_OUTPUTS(
        {"write_lists": ["metadata", "tax"]},
        tmp_path,
    )
    assert tuple(family.Ampvis2LoadNode.MAP_PLANNED_OUTPUTS(load_paths)) == (
        "ampvis",
        "metadata_list_out",
        "taxonomy_list_out",
    )


def test_differential_abundance_outputs_follow_selected_analysis(tmp_path: Path) -> None:
    aldex_paths = family.ALDEx2Node.PLAN_OUTPUTS(
        {"analysis_type": "aldex_ttest", "hist_plot": True},
        tmp_path,
    )
    assert family.ALDEx2Node.MAP_PLANNED_OUTPUTS(aldex_paths) == {
        "aldex_ttest": aldex_paths[0],
        "aldex_ttest_plot": aldex_paths[1],
    }

    ancom_paths = family.ANCOMBCNode.PLAN_OUTPUTS({}, tmp_path)
    assert len(ancom_paths) == 13
    assert [path.name for path in ancom_paths] == family.ANCOMBCNode.expected_output_files()
    assert family.ANCOMBCNode.MAP_PLANNED_OUTPUTS(ancom_paths) == {
        "output_collection": ancom_paths
    }
    assert family.ANCOMBCNode.VALIDATE_INPUTS(
        {"phyloseq": "data.rds", "formula": "group", "struc_zero": True}
    ) == "group is required for structural-zero detection or the global test"


def test_miniasm_accepts_fasta_or_fastq_and_bounds_ratio_parameters() -> None:
    read_types = family.MiniasmNode.INPUT_TYPES()["required"]["read_file"][0]
    assert read_types == ("FASTA", "FASTQ")
    valid = {"read_file": "reads.fa.gz", "paf": "overlaps.paf.gz"}
    assert family.MiniasmNode.VALIDATE_INPUTS(valid) is True
    for name in ("min_iden", "int_thres", "final_drop_ratio"):
        assert family.MiniasmNode.VALIDATE_INPUTS({**valid, name: 1.01}) == (
            f"{name} must be between 0 and 1"
        )


def test_vsearch_nodes_share_wrapper_defaults_and_expose_advanced_search_ports() -> None:
    vsearch_nodes = [node for node in _nodes() if node.NODE_ID.startswith("vsearch_")]
    assert len(vsearch_nodes) == 8
    assert all(issubclass(node, VSearchNodeBase) for node in vsearch_nodes)

    optional = family.VSearchSearchNode.INPUT_TYPES()["optional"]
    assert set(family.VSearchSearchNode.ADVANCED_VALUE_FLAGS) <= set(optional)
    search = family.VSearchSearchNode.render_command(
        {
            "query": "query.fa",
            "database": "db.fa",
            "advanced": True,
            "userfields_output_select": "yes",
            "output": "/work/vsearch_search",
        }
    )
    for flag, value in {
        "--maxaccepts": "1",
        "--maxrejects": "32",
        "--match": "2",
        "--mismatch": "-4",
        "--wordlength": "8",
        "--userfields": "evalue+query+target",
    }.items():
        assert _value_after(search, flag) == value

    cluster = family.VSearchClusterNode.render_command(
        {"sequences": "amplicons.fa", "qmask": "none", "output": "/work/vsearch_cluster"}
    )
    assert _value_after(cluster, "--maxaccepts") == "1"
    assert _value_after(cluster, "--maxrejects") == "32"
    assert _value_after(cluster, "--qmask") == "none"

    masking = family.VSearchMaskingNode.render_command(
        {"infile": "amplicons.fa", "qmask": "none", "output": "/work/vsearch_masking"}
    )
    assert _value_after(masking, "--qmask") == "none"

    alignment = family.VSearchAlignmentNode.render_command(
        {
            "infile": "amplicons.fa",
            "userfields_output_select": "yes",
            "output": "/work/vsearch_alignment",
        }
    )
    assert _value_after(alignment, "--userfields") == "evalue+query+target"


def test_vsearch_chimera_inputs_and_outputs_are_mode_conditional(tmp_path: Path) -> None:
    inputs = family.VSearchChimeraDetectionNode.INPUT_TYPES()
    assert set(inputs["required"]) == {"detection_mode"}
    assert {"infile_denovo", "infile_reference", "db"} <= set(inputs["optional"])

    assert family.VSearchChimeraDetectionNode.VALIDATE_INPUTS(
        {"detection_mode": "denovo", "infile_denovo": "reads.fa"}
    ) is True
    assert family.VSearchChimeraDetectionNode.VALIDATE_INPUTS(
        {"detection_mode": "reference", "infile_reference": "reads.fa"}
    ) == "db is required for reference mode"
    assert family.VSearchChimeraDetectionNode.VALIDATE_INPUTS(
        {"detection_mode": "reference", "infile_reference": "reads.fa", "db": "gold.fa"}
    ) is True

    command = family.VSearchChimeraDetectionNode.render_command(
        {
            "detection_mode": "denovo",
            "infile_denovo": "reads.fa",
            "outputs": ["nonchimeras", "uchimeout"],
            "output": "/work/vsearch_chimera_detection",
        }
    )
    assert "--uchime_denovo" in command
    assert "--uchime_ref" not in command
    planned = family.VSearchChimeraDetectionNode.PLAN_OUTPUTS(
        {"outputs": ["nonchimeras", "uchimeout"]},
        tmp_path,
    )
    assert tuple(family.VSearchChimeraDetectionNode.MAP_PLANNED_OUTPUTS(planned)) == (
        "chimeras",
        "nonchimeras",
        "uchimeout",
    )


def test_vsearch_operation_validation_rejects_invalid_wrapper_values() -> None:
    assert family.VSearchSearchNode.VALIDATE_INPUTS(
        {"query": "q.fa", "database": "db.fa", "wordlength": 16, "advanced": True}
    ) == "wordlength must be between 3 and 15"
    assert family.VSearchClusterNode.VALIDATE_INPUTS(
        {"sequences": "reads.fa", "qmask": "invalid"}
    ) == "qmask must be one of: none, dust, soft"
    assert family.VSearchDereplicationNode.VALIDATE_INPUTS(
        {"infile": "reads.fa", "minuniquesize": 5, "maxuniquesize": 2}
    ) == "minuniquesize must be <= maxuniquesize"
    assert family.VSearchSortingNode.VALIDATE_INPUTS(
        {"infile": "reads.fa", "sorting_mode": "sortbyabundance", "minsize": 3, "maxsize": 2}
    ) == "minsize must be <= maxsize"
    assert family.VSearchShufflingNode.VALIDATE_INPUTS(
        {"infile": "reads.fa", "topn": 0}
    ) == "topn must be at least 1"


def test_adapter_removal_modes_publish_only_the_outputs_the_command_writes(tmp_path: Path) -> None:
    cases = [
        (
            {"input_type": "single", "read1": "reads.fq"},
            ("output_settings", "output_truncated"),
        ),
        (
            {"input_type": "pair", "read1": "r1.fq", "read2": "r2.fq"},
            ("output_settings", "output_forward_truncated", "output_reverse_truncated"),
        ),
        (
            {
                "input_type": "paired",
                "reads_collection": {"forward": "r1.fq", "reverse": "r2.fq"},
                "interleaved_output": "yes",
            },
            ("output_settings", "output_interleaved_truncated"),
        ),
        (
            {"input_type": "interleaved", "read1": "reads.fq", "interleaved_output": True},
            ("output_settings", "output_interleaved_truncated"),
        ),
    ]
    for inputs, expected in cases:
        assert family.AdapterRemovalNode.VALIDATE_INPUTS(inputs) is True
        planned = family.AdapterRemovalNode.PLAN_OUTPUTS(inputs, tmp_path)
        assert tuple(family.AdapterRemovalNode.MAP_PLANNED_OUTPUTS(planned)) == expected

    assert family.AdapterRemovalNode.VALIDATE_INPUTS(
        {"input_type": "unknown", "read1": "reads.fq"}
    ) == "input_type must be one of: single, pair, paired, interleaved"


def test_prinseq_modes_preserve_compression_and_collection_pairing(tmp_path: Path) -> None:
    assert family.PrinseqNode.RUN_IN_NODE_OUTPUT_DIR is True

    single = {"input_mode": "single", "input_singles": "reads.fq.gz"}
    single_paths = family.PrinseqNode.PLAN_OUTPUTS(single, tmp_path)
    assert [path.name for path in single_paths] == [
        "good_sequences.fastq.gz",
        "rejected_sequences.fastq.gz",
    ]
    assert tuple(family.PrinseqNode.MAP_PLANNED_OUTPUTS(single_paths)) == (
        "good_sequences",
        "rejected_sequences",
    )

    collection = {
        "input_mode": "paired_collection",
        "input_collection": {"forward": "r1.fq.gz", "reverse": "r2.fq.gz"},
    }
    collection_paths = family.PrinseqNode.PLAN_OUTPUTS(collection, tmp_path)
    mapped = family.PrinseqNode.MAP_PLANNED_OUTPUTS(collection_paths)
    assert tuple(mapped) == (
        "good_sequences_collection",
        "singletons_collection",
        "rejected_sequences_collection",
    )
    assert all(len(pair) == 2 for pair in mapped.values())
    assert all(path.name.endswith(".fastq.gz") for path in collection_paths)

    command = family.PrinseqNode.render_command(
        {
            "input_mode": "single",
            "input_singles": "reads.fq",
            "noniupac": True,
            "output": "/work/prinseq",
        }
    )
    assert " -noniupac" in command
    assert "mkdir -p /work/prinseq/tmp" in command
