"""Focused source, port, argv, and output checks for twelve pangenomics owners."""

from __future__ import annotations

from pathlib import Path

import pytest

from bionodulo.environments.constants import EXECUTABLE_TO_CONDA_PACKAGE, PACKAGE_MIN_VERSIONS
import bionodulo.nodes.builtin.pangenomics_family as pangenomics_family
from bionodulo.nodes.builtin.pangenomics_family import (
    CactusExportNode,
    CactusGalaxyNode,
    MinigraphCactusNode,
    MinigraphNode,
    PangenomeGeneNode,
    PangenomeSVNode,
    PangenomeStatsNode,
    VCFDecomposeNode,
    VGCallNode,
    VGConstructNode,
    VGIndexNode,
    VGMapNode,
)
from bionodulo.nodes.builtin.pangenomics_family.evidence import (
    CACTUS_COMMIT,
    MINIGRAPH_COMMIT,
    NODE_EVIDENCE,
    PANACUS_COMMIT,
    PANAROO_COMMIT,
    TOOLS_IUC_COMMIT,
    VCFLIB_COMMIT,
    VG_COMMIT,
    VG_FASTAHACK_COMMIT,
    VG_TABIXPP_COMMIT,
    VG_VCFLIB_COMMIT,
    PangenomicsCommandContract,
)
from bionodulo.nodes.registry import NodeRegistry


CLASSES = (
    VGConstructNode,
    VGIndexNode,
    VGMapNode,
    VGCallNode,
    VCFDecomposeNode,
    PangenomeSVNode,
    PangenomeStatsNode,
    PangenomeGeneNode,
    MinigraphNode,
    MinigraphCactusNode,
    CactusGalaxyNode,
    CactusExportNode,
)


def test_registry_uses_twelve_focused_owners() -> None:
    registry = NodeRegistry.create_isolated()
    registry.load_builtin_nodes()
    for node_class in CLASSES:
        assert registry.get(node_class.NODE_ID) is node_class
        assert "pangenomics_family" in node_class.__module__
        assert node_class.__bases__ == (PangenomicsCommandContract,)
        assert node_class.__module__ == (
            f"bionodulo.nodes.builtin.pangenomics_family.{node_class.NODE_ID}"
        )
    family_dir = Path(VGConstructNode.__module__.replace(".", "/"))
    assert family_dir.name == "vg_construct"
    assert not Path(pangenomics_family.__file__).with_name("legacy.py").exists()


@pytest.mark.parametrize("node_class", CLASSES)
def test_each_owner_has_pinned_source_package_and_exit_evidence(node_class: type) -> None:
    evidence = NODE_EVIDENCE[node_class.NODE_ID]
    assert node_class.VERSION == evidence.version
    assert node_class.GIT_COMMIT == evidence.commit
    assert node_class.SOURCE_REF == evidence.source_ref
    assert node_class.SOURCE_URLS == evidence.source_urls
    assert node_class.PACKAGE_CONSTRAINTS == evidence.package_constraints
    assert node_class.PACKAGE_CONSTRAINT == "; ".join(evidence.package_constraints)
    assert node_class.AUDIT_STATUS == "contract-checked-no-external-execution"
    assert "non-zero" in node_class.EXIT_SEMANTICS


def test_exact_authority_commits_are_recorded() -> None:
    assert VG_COMMIT == "1859bc3225bc32c64ebdff2530c68857b11beae7"
    assert VG_FASTAHACK_COMMIT == "75f12d25df9416b9d49b84c70dcc58406afce11a"
    assert VG_TABIXPP_COMMIT == "ae5cdf846af85bd1d0e310c05e5c67b037f51a25"
    assert VG_VCFLIB_COMMIT == "0b01ccf90905bb664e4242967c01adcb24299111"
    assert VCFLIB_COMMIT == "fa6831e9c83059f1c2dc71218bb5b390c5fe917a"
    assert PANACUS_COMMIT == "f70f563c62029589bb79fd2c85821fcfa2ef33f9"
    assert PANAROO_COMMIT == "a79bb11f1d61f58cd367e1be52f2e0120b8934cb"
    assert MINIGRAPH_COMMIT == "7e3e65c5e55a10e2968f32cef5c04eee9330521b"
    assert CACTUS_COMMIT == "3147387e9ca6ad9710b3cdebf029c5c2574e8367"
    assert CactusGalaxyNode.GALAXY_WRAPPER_GIT_COMMIT == TOOLS_IUC_COMMIT
    assert CactusExportNode.GALAXY_WRAPPER_GIT_COMMIT == TOOLS_IUC_COMMIT
    assert "src/index_registry.cpp" in NODE_EVIDENCE["vg_index"].source_paths


def test_runtime_package_resolution_is_exact_for_the_wave() -> None:
    assert EXECUTABLE_TO_CONDA_PACKAGE["minigraph"] == "minigraph"
    assert EXECUTABLE_TO_CONDA_PACKAGE["vcfwave"] == "vcflib"
    assert EXECUTABLE_TO_CONDA_PACKAGE["vcfallelicprimitives"] == "vcflib"
    assert PACKAGE_MIN_VERSIONS["vg"] == "1.63.1"
    assert PACKAGE_MIN_VERSIONS["vcflib"] == "1.0.9"
    assert PACKAGE_MIN_VERSIONS["panacus"] == "0.3.3"
    assert PACKAGE_MIN_VERSIONS["panaroo"] == "1.5.0"
    assert PACKAGE_MIN_VERSIONS["minigraph"] == "0.21"
    assert PACKAGE_MIN_VERSIONS["cactus"] == "2.9.9"
    assert PACKAGE_MIN_VERSIONS["htslib"] == "1.23.1"


def test_vg_construct_uses_one_vcf_flag_and_documented_options() -> None:
    command = VGConstructNode.render_command(
        {
            "reference": "ref.fa",
            "vcf": "variants.vcf",
            "region": "chr1:1-1000",
            "max_node_size": 64,
            "threads": 3,
            "progress": True,
            "output": "/tmp/vg_construct",
        }
    )
    assert command == [
        "vg", "construct", "-r", "ref.fa", "-v", "variants.vcf", "-a", "-f", "-S",
        "-R", "chr1:1-1000", "-m", "64", "-t", "3", "-p", ">",
        "/tmp/vg_construct/vg_graph.vg",
    ]
    assert "-V" not in command
    assert VGConstructNode.INPUT_TYPES()["required"]["vcf"][0] == "FILE"
    assert VGConstructNode.VALIDATE_INPUTS({"reference": "ref.fa", "vcf": "v.vcf", "threads": 0}) == (
        "threads must be at least 1"
    )


def test_vg_construct_stages_writable_reference_and_explicit_compressed_vcf_index(tmp_path: Path) -> None:
    reference = tmp_path / "source.fa"
    reference.write_text(">chr1\nACGT\n", encoding="ascii")
    vcf = tmp_path / "variants.vcf.gz"
    vcf.write_bytes(b"bgzip-placeholder")
    vcf_index = tmp_path / "uploaded-index.tbi"
    vcf_index.write_bytes(b"tabix-placeholder")
    outputs = VGConstructNode.PLAN_OUTPUTS({}, tmp_path / "run")
    inputs = {"reference": reference, "vcf": vcf, "vcf_index": vcf_index}

    VGConstructNode.PREPARE_EXECUTION(inputs, outputs)

    staged_reference = outputs[0].parent / "inputs" / "reference.fa"
    staged_vcf = outputs[0].parent / "inputs" / "variants.vcf.gz"
    assert inputs == {
        "reference": str(staged_reference),
        "vcf": str(staged_vcf),
        "vcf_index": f"{staged_vcf}.tbi",
    }
    assert staged_reference.read_bytes() == reference.read_bytes()
    assert not Path(f"{staged_reference}.fai").exists()
    assert staged_vcf.read_bytes() == vcf.read_bytes()
    assert Path(f"{staged_vcf}.tbi").read_bytes() == vcf_index.read_bytes()
    assert "reference_index" not in VGConstructNode.INPUT_TYPES()["optional"]
    assert "fastahack" in VGConstructNode.SIDECAR_POLICY
    assert "tabixpp" in VGConstructNode.SIDECAR_POLICY


def test_vg_construct_sidecar_validation_follows_vendored_vcflib_suffix_behavior() -> None:
    assert VGConstructNode.VALIDATE_INPUTS({"reference": "ref.fa", "vcf": "v.vcf.gz"}) == (
        "vcf_index is required for a bgzip-compressed VCF"
    )
    assert VGConstructNode.VALIDATE_INPUTS(
        {"reference": "ref.fa", "vcf": "v.vcf.gz", "vcf_index": "uploaded.tbi"}
    ) is True
    assert VGConstructNode.VALIDATE_INPUTS(
        {"reference": "ref.fa", "vcf": "v.vcf", "vcf_index": "v.vcf.tbi"}
    ) == "vcf_index is only valid when vcf is bgzip-compressed"
    assert VGConstructNode.VALIDATE_INPUTS({"reference": "ref.fa.gz", "vcf": "v.vcf"}) == (
        "reference must be an uncompressed FASTA because vg fastahack opens it as plain text"
    )


def test_vg_autoindex_pins_the_1631_zipcode_artifacts_and_xg_adapter() -> None:
    inputs = {
        "graph_gfa": "pan.gfa",
        "threads": 12,
        "output_prefix": "study graph",
        "tmp_dir": "/scratch/vg",
        "target_mem": "64G",
        "output": "/tmp/vg_index",
    }
    command = VGIndexNode.render_command(inputs)
    assert command[:12] == [
        "vg", "autoindex", "--workflow", "giraffe", "--gfa", "pan.gfa", "--prefix",
        "/tmp/vg_index/study_graph", "--threads", "12", "--tmp-dir", "/scratch/vg",
    ]
    assert "--ref-fasta" not in command
    assert "/tmp/vg_index/study_graph.shortread.withzip.min" in command
    assert "/tmp/vg_index/study_graph.shortread.zipcodes" in command
    assert [path.name for path in VGIndexNode.PLAN_OUTPUTS(inputs, "/tmp/run")] == [
        "study_graph.giraffe.gbz",
        "study_graph.shortread.withzip.min",
        "study_graph.shortread.zipcodes",
        "study_graph.dist",
        "study_graph.xg",
    ]
    assert "reference" not in VGIndexNode.INPUT_TYPES()["optional"]
    assert VGIndexNode.VALIDATE_INPUTS({"graph_gfa": "g.gfa", "target_mem": "64Gi"}) == (
        "target_mem must use vg's INT[kMG] format"
    )


def test_vg_map_has_mode_specific_indexes_and_optional_zipcodes() -> None:
    giraffe = VGMapNode.render_command(
        {
            "reads": "r1.fq",
            "reads2": "r2.fq",
            "mapper": "giraffe",
            "threads": 8,
            "gbz_index": "graph.gbz",
            "minimizer_index": "graph.min",
            "zipcode_index": "graph.zipcodes",
            "distance_index": "graph.dist",
            "output": "/tmp/vg_map",
        }
    )
    assert giraffe[:12] == [
        "vg", "giraffe", "-Z", "graph.gbz", "-m", "graph.min", "-z", "graph.zipcodes",
        "-d", "graph.dist", "-f", "r1.fq",
    ]
    assert giraffe.count("-f") == 2
    classic = VGMapNode.render_command(
        {
            "reads": "reads.fq",
            "mapper": "map",
            "threads": 4,
            "xg_index": "graph.xg",
            "gcsa_index": "graph.gcsa",
            "gcsa_lcp": "graph.gcsa.lcp",
            "min_identity": 0.8,
            "output": "/tmp/vg_map",
        }
    )
    assert classic[:10] == [
        "vg", "map", "-x", "graph.xg", "-g", "graph.gcsa", "-f", "reads.fq", "-t", "4",
    ]
    assert ["--min-ident", "0.8"] == classic[10:12]
    assert VGMapNode.VALIDATE_INPUTS({"reads": "r.fq", "mapper": "giraffe", "threads": 1}) == (
        "gbz_index is required for mapper=giraffe"
    )
    assert VGMapNode.VALIDATE_INPUTS(
        {
            "reads": "r.fq",
            "mapper": "map",
            "threads": 1,
            "xg_index": "graph.xg",
            "gcsa_index": "graph.gcsa",
        }
    ) == "gcsa_lcp is required for mapper=map"


def test_vg_map_stages_gcsa_and_lcp_under_the_required_sibling_names(tmp_path: Path) -> None:
    gcsa = tmp_path / "uploaded.gcsa"
    lcp = tmp_path / "uploaded.lcp"
    gcsa.write_bytes(b"gcsa")
    lcp.write_bytes(b"lcp")
    inputs = {
        "reads": "reads.fq",
        "mapper": "map",
        "xg_index": "graph.xg",
        "gcsa_index": gcsa,
        "gcsa_lcp": lcp,
    }
    outputs = VGMapNode.PLAN_OUTPUTS(inputs, tmp_path / "run")

    VGMapNode.PREPARE_EXECUTION(inputs, outputs)

    staged_gcsa = outputs[0].parent / "inputs" / "graph.gcsa"
    assert inputs["gcsa_index"] == str(staged_gcsa)
    assert inputs["gcsa_lcp"] == f"{staged_gcsa}.lcp"
    assert staged_gcsa.read_bytes() == b"gcsa"
    assert Path(f"{staged_gcsa}.lcp").read_bytes() == b"lcp"
    assert "<gcsa_index>.lcp" in VGMapNode.SIDECAR_POLICY


def test_vg_call_never_renders_a_dangling_vcf_argument() -> None:
    command = VGCallNode.render_command(
        {
            "xg_graph": "graph.xg",
            "gam": "reads.gam",
            "threads": 4,
            "ref_path": "chr1",
            "sample": "sample-a",
            "min_support": "3,5",
            "output": "/tmp/vg_call",
        }
    )
    assert command[:10] == [
        "vg", "pack", "-x", "graph.xg", "-g", "reads.gam", "-o", "/tmp/vg_call/aln.pack", "-t", "4",
    ]
    call_index = command.index("call")
    assert command[call_index - 1] == "vg"
    assert command[call_index + 1 : call_index + 9] == [
        "graph.xg", "-k", "/tmp/vg_call/aln.pack", "-t", "4", "-m", "3,5", "-p",
    ]
    assert "-v" not in command[call_index:]
    assert VGCallNode.VALIDATE_INPUTS(
        {"xg_graph": "g.xg", "gam": "a.gam", "threads": 4, "min_support": "3"}
    ) == (
        "min_support must use vg's M,N format"
    )


def test_vcf_decompose_uses_vcfwave_or_the_named_legacy_operation() -> None:
    normalized = VCFDecomposeNode.render_command(
        {"vcf": "graph.vcf.gz", "mode": "normalize", "threads": 4, "max_length": 10000, "output": "/tmp/vcf"}
    )
    assert normalized[:7] == [
        "vcfwave", "--threads", "4", "--max-length", "10000", "graph.vcf.gz", "|",
    ]
    legacy = VCFDecomposeNode.render_command(
        {"vcf": "graph.vcf", "mode": "decompose", "threads": 1, "keep_info": True, "output": "/tmp/vcf"}
    )
    assert legacy[:3] == ["vcfallelicprimitives", "--keep-info", "graph.vcf"]
    assert [path.name for path in VCFDecomposeNode.PLAN_OUTPUTS({}, "/tmp/run")] == [
        "decomposed_vcf.vcf.gz", "decomposed_vcf.vcf.gz.tbi",
    ]
    assert set(VCFDecomposeNode.INPUT_TYPES()["required"]) == {"vcf"}
    assert VCFDecomposeNode.VALIDATE_INPUTS({"vcf": "v.vcf", "mode": "bad"}) == (
        "Unsupported VCF decompose mode: bad"
    )


def test_pangenome_sv_deconstructs_a_real_xg_and_returns_the_tbi() -> None:
    command = PangenomeSVNode.render_command(
        {"graph_gfa": "pan.gfa", "ref_path": "GRCh38", "threads": 8, "min_sv_length": 50, "output": "/tmp/sv"}
    )
    assert command[:9] == [
        "vg", "convert", "-x", "pan.gfa", ">", "/tmp/sv/graph.xg", "&&", "vg", "deconstruct",
    ]
    assert command[9:16] == ["-P", "GRCh38", "-a", "-t", "8", "/tmp/sv/graph.xg", "|"]
    assert "-e" not in command
    assert [path.name for path in PangenomeSVNode.PLAN_OUTPUTS({}, "/tmp/run")] == [
        "sv_vcf.vcf.gz", "sv_vcf.vcf.gz.tbi",
    ]
    assert set(PangenomeSVNode.INPUT_TYPES()["required"]) == {"graph_gfa", "ref_path"}
    assert PangenomeSVNode.VALIDATE_INPUTS({"graph_gfa": "g.gfa", "ref_path": "ref", "min_sv_length": -1}) == (
        "min_sv_length must be non-negative"
    )


def test_panacus_contract_contains_only_033_histgrowth_options() -> None:
    command = PangenomeStatsNode.render_command(
        {
            "graph": "pan.gfa",
            "count": "bp",
            "coverage": "1,2",
            "quorum": "0.1,0.9",
            "groupby_sample": True,
            "threads": 6,
            "include_hist": True,
            "core_threshold": 0.9,
            "shell_threshold": 0.1,
            "output": "/tmp/stats",
        }
    )
    assert command[:15] == [
        "panacus", "histgrowth", "pan.gfa", "--count", "bp", "--coverage", "1,2", "--quorum",
        "0.1,0.9", "--groupby-sample", "--hist", "-t", "6", ">", "/tmp/stats/rarefaction.tsv",
    ]
    assert "--gff" not in command
    assert "--html" not in command
    assert set(PangenomeStatsNode.INPUT_TYPES()["required"]) == {"graph"}
    assert PangenomeStatsNode.INPUT_TYPES()["optional"]["threads"][1]["default"] == 0
    assert "not a Panacus artifact" in PangenomeStatsNode.ADAPTER_OUTPUT_POLICY
    assert PangenomeStatsNode.VALIDATE_INPUTS(
        {"graph": "g.gfa", "groupby": "groups.tsv", "groupby_sample": True}
    ) == "groupby, groupby_sample, and groupby_haplotype are mutually exclusive"


def test_panaroo_contract_uses_only_documented_inputs_and_outputs() -> None:
    command = PangenomeGeneNode.render_command(
        {
            "annotations": ["sample one.gff", "sample-two.gff"],
            "clean_mode": "strict",
            "threads": 4,
            "core_threshold": 0.95,
            "remove_invalid_genes": True,
            "merge_paralogs": True,
            "output": "/tmp/panaroo",
        }
    )
    assert command[:12] == [
        "panaroo", "-i", "sample one.gff", "sample-two.gff", "-o", "/tmp/panaroo",
        "--clean-mode", "strict", "-t", "4", "--core_threshold", "0.95",
    ]
    assert "--remove-invalid-genes" in command
    assert "--merge_paralogs" in command
    assert "orthologs" not in PangenomeGeneNode.INPUT_TYPES()["required"]
    assert PangenomeGeneNode.INPUT_TYPES()["optional"]["remove_invalid_genes"][1]["default"] is False
    assert "not a Panaroo artifact" in PangenomeGeneNode.ADAPTER_OUTPUT_POLICY
    assert [path.name for path in PangenomeGeneNode.PLAN_OUTPUTS({}, "/tmp/run")] == [
        "presence_matrix.tsv", "pan_genome_plot.svg",
    ]


def test_minigraph_modes_emit_gfa_or_gaf_with_named_sparse_outputs() -> None:
    construct_inputs = {
        "mode": "construct", "assemblies": ["ref.fa", "sample.fa"], "preset": "ggs", "threads": 8, "output": "/tmp/mg"
    }
    assert MinigraphNode.render_command(construct_inputs)[:9] == [
        "minigraph", "-c", "-x", "ggs", "-t", "8", "ref.fa", "sample.fa", ">",
    ]
    align_inputs = {
        "mode": "align", "graph_gfa": "graph.gfa", "query_fasta": "query.fa", "preset": "asm", "threads": 4,
        "output": "/tmp/mg",
    }
    assert MinigraphNode.render_command(align_inputs)[:10] == [
        "minigraph", "-c", "-x", "asm", "-t", "4", "graph.gfa", "query.fa", ">", "/tmp/mg/alignment_gaf.gaf",
    ]
    assert MinigraphNode.MAP_PLANNED_OUTPUTS(MinigraphNode.PLAN_OUTPUTS(construct_inputs, "/tmp/run")) == {
        "output_gfa": Path("/tmp/run/minigraph/output_gfa.gfa")
    }
    assert MinigraphNode.MAP_PLANNED_OUTPUTS(MinigraphNode.PLAN_OUTPUTS(align_inputs, "/tmp/run")) == {
        "alignment_gaf": Path("/tmp/run/minigraph/alignment_gaf.gaf")
    }
    assert MinigraphNode.VALIDATE_INPUTS(
        {"mode": "construct", "assemblies": ["ref.fa"], "threads": 8}
    ) == (
        "construct mode requires a reference plus at least one assembly"
    )
    assert MinigraphNode.VALIDATE_INPUTS(
        {
            "mode": "align",
            "preset": "ggs",
            "graph_gfa": "graph.gfa",
            "query_fasta": "query.fa",
            "threads": 8,
        }
    ) == "align mode preset must be one of: asm, lr"
    assert "no single preset" in MinigraphNode.MODE_PRESET_POLICY


def test_minigraph_cactus_tracks_only_requested_primary_artifacts() -> None:
    inputs = {
        "seq_file": "seqfile.txt",
        "assemblies": ["ref.fa", "sample.fa"],
        "reference": "GRCh38",
        "out_name": "hprc",
        "threads": 48,
        "max_cores": 12,
        "cons_cores": 4,
        "gbz": True,
        "vcf": True,
        "gfa": True,
        "odgi": True,
        "output": "/tmp/cactus",
    }
    command = MinigraphCactusNode.render_command(inputs)
    assert command == [
        "cactus-pangenome", "/tmp/cactus/work", "seqfile.txt", "--outDir", "/tmp/cactus",
        "--outName", "hprc", "--reference", "GRCh38", "--binariesMode", "local", "--maxCores",
        "12", "--consCores", "4", "--gbz", "--vcf", "--gfa", "--odgi",
    ]
    outputs = MinigraphCactusNode.PLAN_OUTPUTS(inputs, "/tmp/run")
    assert [path.name for path in outputs] == [
        "hprc.gbz", "hprc.vcf.gz", "hprc.vcf.gz.tbi", "hprc.gfa.gz", "hprc.full.og",
    ]
    assert set(MinigraphCactusNode.MAP_PLANNED_OUTPUTS(outputs)) == {
        "graph_gbz", "variants_vcf", "variants_vcf_index", "graph_gfa", "graph_odgi",
    }
    assert "giraffe" not in MinigraphCactusNode.INPUT_TYPES()["optional"]
    assert "viz" not in MinigraphCactusNode.INPUT_TYPES()["optional"]
    assert MinigraphCactusNode.VALIDATE_INPUTS(
        {
            "seq_file": "s",
            "assemblies": ["ref.fa", "sample.fa"],
            "reference": "r",
            "max_cores": 4,
            "cons_cores": 5,
        }
    ) == (
        "cons_cores must not exceed max_cores or threads"
    )


def test_minigraph_cactus_rewrites_seqfile_to_explicit_staged_assemblies(tmp_path: Path) -> None:
    reference = tmp_path / "uploaded-reference.fa"
    sample = tmp_path / "uploaded-sample.fa.gz"
    reference.write_text(">chr1\nACGT\n", encoding="ascii")
    sample.write_bytes(b"gzip-placeholder")
    seq_file = tmp_path / "assemblies.seqfile"
    seq_file.write_text("GRCh38 /old/ref.fa\nHG002 /old/sample.fa.gz\n", encoding="utf-8")
    inputs = {
        "seq_file": seq_file,
        "assemblies": [reference, sample],
        "reference": "GRCh38",
    }
    outputs = MinigraphCactusNode.PLAN_OUTPUTS(inputs, tmp_path / "run")

    MinigraphCactusNode.PREPARE_EXECUTION(inputs, outputs)

    prepared = Path(inputs["seq_file"])
    rows = prepared.read_text(encoding="utf-8").splitlines()
    assert rows[0].startswith("GRCh38 ")
    assert rows[1].startswith("HG002 ")
    staged_paths = [Path(row.split(maxsplit=1)[1]) for row in rows]
    assert all(path.parent == outputs[0].parent / "inputs" for path in staged_paths)
    assert staged_paths[0].read_bytes() == reference.read_bytes()
    assert staged_paths[1].read_bytes() == sample.read_bytes()
    assert inputs["assemblies"] == [str(path) for path in staged_paths]
    assert "explicit assemblies input" in MinigraphCactusNode.SIDECAR_POLICY


def test_minigraph_cactus_rejects_staging_name_collisions(tmp_path: Path) -> None:
    first = tmp_path / "first.fa"
    second = tmp_path / "second.fa"
    first.write_text(">a\nA\n", encoding="ascii")
    second.write_text(">b\nC\n", encoding="ascii")
    seq_file = tmp_path / "assemblies.seqfile"
    seq_file.write_text("A?B /old/a.fa\nA_B /old/b.fa\n", encoding="utf-8")
    inputs = {
        "seq_file": seq_file,
        "assemblies": [first, second],
        "reference": "A?B",
    }
    outputs = MinigraphCactusNode.PLAN_OUTPUTS(inputs, tmp_path / "run")

    with pytest.raises(ValueError, match="collide after safe staging"):
        MinigraphCactusNode.PREPARE_EXECUTION(inputs, outputs)


def test_tools_iuc_cactus_contracts_keep_mode_specific_outputs_named() -> None:
    assert CactusGalaxyNode.RETURN_TYPES == ("HAL", "GFA")
    assert CactusGalaxyNode.PACKAGE_CONSTRAINTS == ("cactus==2.9.9",)
    intra = {
        "in_seqs": ["ref.fa", "sample.fa"],
        "labels": ["ref", "sample"],
        "aln_mode_select": "intraspecies",
        "ref_level": "ref",
        "output": "/tmp/cactus_cactus",
    }
    command = CactusGalaxyNode.render_command(intra)
    assert "cactus-pangenome" in command
    assert [path.name for path in CactusGalaxyNode.PLAN_OUTPUTS(intra, "/tmp/run")] == [
        "alignment.full.hal", "alignment.gfa.gz",
    ]
    assert CactusGalaxyNode.VALIDATE_INPUTS({"in_seqs": ["a.fa"], "labels": ["bad label"]}) == (
        "labels may contain only letters, digits, and underscores"
    )


@pytest.mark.parametrize(
    ("export_format", "expected_command", "expected_name", "expected_port"),
    [
        ("maf_selector", "hal2maf", "alignment.maf", "out_maf"),
        ("vg_selector", "hal2vg", "alignment.pg", "out_vg"),
        ("ah_selector", "hal2assemblyHub.py", "assemblyhub.tar", "out_ah"),
    ],
)
def test_cactus_export_modes_match_the_pinned_wrapper(
    export_format: str,
    expected_command: str,
    expected_name: str,
    expected_port: str,
) -> None:
    inputs = {
        "hal_file": "alignment.hal",
        "format": export_format,
        "ref_level": "GRCh38" if export_format != "ah_selector" else "",
        "output": "/tmp/cactus_export",
    }
    command = CactusExportNode.render_command(inputs)
    assert expected_command in command
    outputs = CactusExportNode.PLAN_OUTPUTS(inputs, "/tmp/run")
    assert [path.name for path in outputs] == [expected_name]
    assert CactusExportNode.MAP_PLANNED_OUTPUTS(outputs) == {
        expected_port: Path(f"/tmp/run/cactus_export/{expected_name}")
    }


def test_cactus_export_validation_fails_closed() -> None:
    assert CactusExportNode.VALIDATE_INPUTS({}) == "hal_file is required"
    assert CactusExportNode.VALIDATE_INPUTS({"hal_file": "a.hal", "format": "maf_selector"}) == (
        "ref_level is required for MAF and VG export"
    )
    assert CactusExportNode.PACKAGE_CONSTRAINTS == ("cactus==2.9.9", "tar>=1.34")
