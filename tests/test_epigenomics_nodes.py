from __future__ import annotations

from pathlib import Path

import pytest

from bionodulo.nodes.builtin import epigenomics
from bionodulo.nodes.builtin.alignment_family.adapter import BWA_INDEX_SUFFIXES
from bionodulo.nodes.builtin.alignment_family.bowtie2_adapter import BOWTIE2_SMALL_SUFFIXES
from bionodulo.nodes.builtin.epigenomics_family.evidence import NODE_EVIDENCE
from bionodulo.nodes.registry import NodeRegistry


OWNER_MODULES = {
    "cooler": "cooler",
    "cooltools_compartments": "cooltools_compartments",
    "cooltools_insulation": "cooltools_insulation",
    "dss_dmr": "dss_dmr",
    "hic_pro": "hic_pro",
    "juicer": "juicer",
    "methyldackel": "methyldackel",
    "modkit_dmr": "modkit_dmr",
}


def _node_class(node_id: str) -> type:
    registry = NodeRegistry.create_isolated()
    registry.load_builtin_nodes()
    node_class = registry.get(node_id)
    assert node_class is not None
    return node_class


@pytest.mark.parametrize(("node_id", "module_name"), OWNER_MODULES.items())
def test_epigenomics_nodes_have_focused_evidence_pinned_owners(node_id: str, module_name: str) -> None:
    node_class = _node_class(node_id)
    evidence = NODE_EVIDENCE[node_id]

    assert node_class.__module__ == f"bionodulo.nodes.builtin.epigenomics_family.{module_name}"
    assert node_class.CATEGORY == "epigenomics"
    assert node_class.AUDIT_STATUS == "contract-checked-no-external-execution"
    assert node_class.VERSION == evidence.version
    assert node_class.GIT_COMMIT == evidence.git_commit
    assert node_class.SOURCE_REF == evidence.source_ref
    assert node_class.PACKAGE_CONSTRAINTS == evidence.package_constraints
    assert len(node_class.RETURN_TYPES) == len(node_class.RETURN_NAMES)


def test_epigenomics_facade_preserves_class_exports() -> None:
    assert epigenomics.CoolerNode is _node_class("cooler")
    assert epigenomics.CooltoolsCompartmentsNode is _node_class("cooltools_compartments")
    assert epigenomics.CooltoolsInsulationNode is _node_class("cooltools_insulation")
    assert epigenomics.DSSDMRNode is _node_class("dss_dmr")
    assert epigenomics.HICProNode is _node_class("hic_pro")
    assert epigenomics.JuicerNode is _node_class("juicer")
    assert epigenomics.MethylDackelNode is _node_class("methyldackel")
    assert epigenomics.ModkitDMRNode is _node_class("modkit_dmr")


def test_methyldackel_uses_real_text_mbias_and_bedgraph_outputs() -> None:
    node_class = _node_class("methyldackel")
    inputs = {
        "bam": "sample.bam",
        "bam_index": "sample.bam.bai",
        "reference": "ref.fa",
        "reference_index": "ref.fa.fai",
        "output_prefix": "case sample",
        "threads": 3,
        "merge_context": True,
        "min_depth": 5,
        "output": "/tmp/run/methyldackel",
    }

    assert node_class.render_command(inputs) == [
        "MethylDackel",
        "mbias",
        "--noSVG",
        "-@",
        "3",
        "ref.fa",
        "sample.bam",
        ">",
        "/tmp/run/methyldackel/case_sample_mbias.tsv",
        "&&",
        "MethylDackel",
        "extract",
        "-@",
        "3",
        "-o",
        "/tmp/run/methyldackel/case_sample",
        "--mergeContext",
        "--minDepth",
        "5",
        "ref.fa",
        "sample.bam",
    ]
    assert "--bedGraph" not in node_class.render_command(inputs)
    assert [str(path) for path in node_class.PLAN_OUTPUTS(inputs, "/tmp/run")] == [
        "/tmp/run/methyldackel/case_sample_CpG.bedGraph",
        "/tmp/run/methyldackel/case_sample_mbias.tsv",
    ]


def test_methyldackel_stages_explicit_indexes_as_siblings(tmp_path: Path) -> None:
    node_class = _node_class("methyldackel")
    source = tmp_path / "source"
    source.mkdir()
    for name in ("sample.bam", "sample.bai", "ref.fa", "ref.fai"):
        (source / name).write_text(name)
    inputs = {
        "bam": source / "sample.bam",
        "bam_index": source / "sample.bai",
        "reference": source / "ref.fa",
        "reference_index": source / "ref.fai",
    }
    outputs = node_class.PLAN_OUTPUTS(inputs, tmp_path / "out")

    node_class.PREPARE_EXECUTION(inputs, outputs)

    assert Path(inputs["bam"]).name == "alignment.bam"
    assert Path(f"{inputs['bam']}.bai").read_text() == "sample.bai"
    assert Path(inputs["reference"]).name == "reference.fa"
    assert Path(f"{inputs['reference']}.fai").read_text() == "ref.fai"


def test_dss_command_and_adapter_match_dss_258_contract() -> None:
    node_class = _node_class("dss_dmr")
    cmd = node_class.render_command({
        "methylation_files": ["tumor.tsv", "normal.tsv"],
        "sample_info": "samples.tsv",
        "condition_column": "condition",
        "sample_column": "sample",
        "threads": 2,
        "smoothing": True,
        "delta": 0.2,
        "pvalue": 0.001,
        "minlen": 75,
        "mincg": 4,
        "output_prefix": "case control",
        "output": "/tmp/run/dss_dmr",
    })

    assert cmd[:12] == [
        "Rscript",
        str(epigenomics.DSS_DMR_SCRIPT),
        "--methylation-files",
        "tumor.tsv,normal.tsv",
        "--sample-info",
        "samples.tsv",
        "--condition-column",
        "condition",
        "--sample-column",
        "sample",
        "--threads",
        "2",
    ]
    assert cmd[-1] == "--smoothing"
    script = epigenomics.DSS_DMR_SCRIPT.read_text()
    assert "ncores = threads" in script
    assert "is.null(dmrs) || nrow(dmrs) == 0" in script
    assert "abs(stats$diff.Methy)" in script
    assert "stats$pval" not in script
    assert "sample = sample_id" not in script


def test_modkit_stages_indexes_without_flags_absent_from_pinned_parser(tmp_path: Path) -> None:
    node_class = _node_class("modkit_dmr")
    source = tmp_path / "source"
    source.mkdir()
    for name in ("a.bed.gz", "a.tbi", "b.bed.gz", "b.tbi"):
        (source / name).write_text(name)
    inputs = {
        "sample_a": source / "a.bed.gz",
        "index_a": source / "a.tbi",
        "sample_b": source / "b.bed.gz",
        "index_b": source / "b.tbi",
        "reference": "ref.fa",
        "base": "C A",
        "threads": 6,
        "segment": True,
        "fine_grained": True,
        "output_prefix": "tumor normal",
        "output": str(tmp_path / "out" / "modkit_dmr"),
    }
    outputs = node_class.PLAN_OUTPUTS(inputs, tmp_path / "out")
    node_class.PREPARE_EXECUTION(inputs, outputs)
    cmd = node_class.render_command(inputs)

    assert "--index-a" not in cmd and "--index-b" not in cmd
    assert Path(f"{inputs['sample_a']}.tbi").read_text() == "a.tbi"
    assert Path(f"{inputs['sample_b']}.tbi").read_text() == "b.tbi"
    assert cmd[-3:] == ["--segment", str(outputs[1]), "--fine-grained"]
    assert node_class.MAP_PLANNED_OUTPUTS(inputs, outputs) == {
        "dmr": outputs[0],
        "segments": outputs[1],
        "log": outputs[2],
    }
    assert (
        node_class.VALIDATE_INPUTS({**inputs, "regions": "regions.bed"})
        == "segment is only available when regions is omitted"
    )


def test_hic_pro_writes_complete_pinned_config_without_precreating_run(tmp_path: Path) -> None:
    node_class = _node_class("hic_pro")
    output = tmp_path / "hic_pro"
    inputs = {
        "input_dir": "fastqs",
        "genome_id": "hg38",
        "bowtie2_index_dir": "bt2",
        "chrom_sizes": "hg38.chrom.sizes",
        "threads": 12,
        "restriction_fragments": "MboI.fragments.bed",
        "ligation_site": "GATCGATC",
        "bin_sizes": "10000,40000",
        "output": str(output),
    }

    assert node_class.render_command(inputs) == [
        "HiC-Pro",
        "-i",
        "fastqs",
        "-o",
        str(output / "run"),
        "-c",
        str(output / "hicpro_config.txt"),
    ]
    config = (output / "hicpro_config.txt").read_text()
    assert "REFERENCE_GENOME = hg38\n" in config
    assert "BOWTIE2_IDX_PATH = bt2\n" in config
    assert "GENOME_SIZE = hg38.chrom.sizes\n" in config
    assert "GENOME_FRAGMENT = MboI.fragments.bed\n" in config
    assert "LIGATION_SITE = GATCGATC\n" in config
    assert "BIN_SIZE = 10000 40000\n" in config
    assert not (output / "run").exists()
    assert node_class.PLAN_OUTPUTS({}, tmp_path) == [tmp_path / "hic_pro" / "run" / "hic_results"]


def test_hic_pro_requires_one_complete_matching_bowtie2_prefix(tmp_path: Path) -> None:
    node_class = _node_class("hic_pro")
    index_dir = tmp_path / "bt2"
    index_dir.mkdir()
    prefix = index_dir / "hg38"
    inputs = {"bowtie2_index_dir": index_dir, "genome_id": "hg38"}

    for suffix in BOWTIE2_SMALL_SUFFIXES[:-1]:
        Path(f"{prefix}{suffix}").write_bytes(b"index")
    with pytest.raises(FileNotFoundError, match="no complete sibling prefix"):
        node_class.PREPARE_EXECUTION(inputs, [])

    Path(f"{prefix}{BOWTIE2_SMALL_SUFFIXES[-1]}").write_bytes(b"index")
    node_class.PREPARE_EXECUTION(inputs, [])

    with pytest.raises(ValueError, match="genome_id must match.*'hg38'"):
        node_class.PREPARE_EXECUTION({**inputs, "genome_id": "GRCh38"}, [])


def test_juicer_uses_documented_work_and_installation_flags() -> None:
    node_class = _node_class("juicer")
    cmd = node_class.render_command({
        "fastq_dir": "fastqs",
        "bwa_index": "bwa-index",
        "genome_id": "hg38",
        "chrom_sizes": "hg38.chrom.sizes",
        "installation_dir": "/opt/juicer",
        "restriction_site": "MboI",
        "restriction_sites_bed": "hg38_MboI.txt",
        "threads": 16,
        "hic_threads": 4,
        "output": "/tmp/run/juicer",
    })

    assert cmd == [
        "juicer.sh",
        "-g",
        "hg38",
        "-d",
        "/tmp/run/juicer/run",
        "-s",
        "MboI",
        "-p",
        "hg38.chrom.sizes",
        "-D",
        "/opt/juicer",
        "-z",
        "bwa-index/reference.fa",
        "-t",
        "16",
        "-T",
        "4",
        "-y",
        "hg38_MboI.txt",
    ]
    assert [path.name for path in node_class.PLAN_OUTPUTS({}, "/tmp/run")] == [
        "inter_30.hic",
        "inter.hic",
        "merged_dedup.bam",
        "inter_30.txt",
    ]

    serial_cmd = node_class.render_command({
        "fastq_dir": "fastqs",
        "bwa_index": "bwa-index",
        "genome_id": "hg38",
        "chrom_sizes": "hg38.chrom.sizes",
        "installation_dir": "/opt/juicer",
        "restriction_site": "none",
        "output": "/tmp/run/juicer",
    })
    assert "-T" not in serial_cmd


def test_juicer_prepares_fastqs_and_resolves_complete_bwa_bundle(tmp_path: Path) -> None:
    node_class = _node_class("juicer")
    installation = tmp_path / "juicer"
    for relative in node_class.REQUIRED_INSTALLATION_FILES:
        path = installation / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(relative)
    for relative in node_class.EXECUTABLE_INSTALLATION_FILES:
        (installation / relative).chmod(0o755)
    parallel_helper = installation / node_class.PARALLEL_HIC_INSTALLATION_FILES[0]
    parallel_helper.parent.mkdir(parents=True, exist_ok=True)
    parallel_helper.write_text("helper")
    parallel_helper.chmod(0o755)
    fastqs = tmp_path / "fastqs"
    fastqs.mkdir()
    (fastqs / "sample_R1.fastq.gz").write_text("r1")
    (fastqs / "sample_R2.fastq.gz").write_text("r2")
    index = tmp_path / "index"
    index.mkdir()
    reference = index / "reference.fa"
    reference.write_text(">chr1\nA\n")
    for suffix in BWA_INDEX_SUFFIXES:
        Path(f"{reference}{suffix}").write_text(suffix)
    inputs = {
        "fastq_dir": fastqs,
        "bwa_index": index,
        "installation_dir": installation,
        "hic_threads": 2,
    }
    outputs = node_class.PLAN_OUTPUTS(inputs, tmp_path / "out")

    node_class.PREPARE_EXECUTION(inputs, outputs)

    assert (Path(inputs["_run_dir"]) / "fastq" / "sample_R1.fastq.gz").read_text() == "r1"
    assert (Path(inputs["_run_dir"]) / "fastq" / "sample_R2.fastq.gz").read_text() == "r2"
    assert inputs["_reference_prefix"] == str(reference)


def test_juicer_fails_closed_on_installation_layout_and_fastq_pairs(tmp_path: Path) -> None:
    node_class = _node_class("juicer")
    installation = tmp_path / "juicer"
    installation.mkdir()
    fastqs = tmp_path / "fastqs"
    fastqs.mkdir()
    (fastqs / "sample_R1.fastq.gz").write_text("r1")
    index = tmp_path / "index"
    index.mkdir()
    reference = index / "reference.fa"
    reference.write_text(">chr1\nA\n")
    for suffix in BWA_INDEX_SUFFIXES:
        Path(f"{reference}{suffix}").write_text(suffix)
    inputs = {"fastq_dir": fastqs, "bwa_index": index, "installation_dir": installation}
    outputs = node_class.PLAN_OUTPUTS(inputs, tmp_path / "out")

    with pytest.raises(FileNotFoundError, match="missing required files"):
        node_class.PREPARE_EXECUTION(inputs, outputs)

    for relative in node_class.REQUIRED_INSTALLATION_FILES:
        path = installation / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(relative)
    for relative in node_class.EXECUTABLE_INSTALLATION_FILES:
        (installation / relative).chmod(0o755)
    parallel_helper = installation / node_class.PARALLEL_HIC_INSTALLATION_FILES[0]
    parallel_helper.write_text("helper")
    parallel_helper.chmod(0o755)

    with pytest.raises(ValueError, match="Unpaired Juicer FASTQs"):
        node_class.PREPARE_EXECUTION(inputs, outputs)


def test_cooler_cload_uses_zoomify_balancing_and_exact_outputs() -> None:
    node_class = _node_class("cooler")
    inputs = {
        "input_data": "pairs.pairs.gz",
        "mode": "cload",
        "chrom_sizes": "hg38.chrom.sizes",
        "bin_size": 10000,
        "threads": 8,
        "output": "/tmp/run/cooler",
    }
    cmd = node_class.render_command(inputs)

    assert cmd[:15] == [
        "cooler",
        "cload",
        "pairs",
        "--chrom1",
        "2",
        "--pos1",
        "3",
        "--chrom2",
        "4",
        "--pos2",
        "5",
        "hg38.chrom.sizes:10000",
        "pairs.pairs.gz",
        "/tmp/run/cooler/matrix.cool",
        "&&",
    ]
    assert cmd[15:] == [
        "cooler",
        "zoomify",
        "--nproc",
        "8",
        "--balance",
        "--balance-args",
        "--nproc 8 --convergence-policy error",
        "--out",
        "/tmp/run/cooler/mcool.mcool",
        "/tmp/run/cooler/matrix.cool",
    ]
    outputs = node_class.PLAN_OUTPUTS(inputs, "/tmp/run")
    assert [path.name for path in outputs] == ["matrix.cool", "mcool.mcool"]
    assert node_class.MAP_PLANNED_OUTPUTS(inputs, outputs) == {"base_cool": outputs[0], "mcool": outputs[1]}


def test_cooler_csort_uses_current_required_columns_and_declares_pairix_index() -> None:
    node_class = _node_class("cooler")
    inputs = {
        "input_data": "pairs.txt",
        "mode": "csort",
        "chrom_sizes": "hg38.chrom.sizes",
        "threads": 4,
        "output": "/tmp/run/cooler",
    }
    cmd = node_class.render_command(inputs)

    assert cmd == [
        "cooler",
        "csort",
        "pairs.txt",
        "hg38.chrom.sizes",
        "--chrom1",
        "2",
        "--pos1",
        "3",
        "--chrom2",
        "4",
        "--pos2",
        "5",
        "--index",
        "pairix",
        "--nproc",
        "4",
        "--out",
        "/tmp/run/cooler/sorted.pairs.gz",
    ]
    assert [path.name for path in node_class.PLAN_OUTPUTS(inputs, "/tmp/run")] == [
        "sorted.pairs.gz",
        "sorted.pairs.gz.px2",
    ]


def test_cooler_balance_copies_before_in_place_balancing(tmp_path: Path) -> None:
    node_class = _node_class("cooler")
    source = tmp_path / "input.mcool"
    source.write_text("matrix")
    inputs = {
        "input_data": f"{source}::resolutions/10000",
        "mode": "balance",
        "threads": 3,
        "cis_only": True,
        "output": str(tmp_path / "out" / "cooler"),
    }
    outputs = node_class.PLAN_OUTPUTS(inputs, tmp_path / "out")
    node_class.PREPARE_EXECUTION(inputs, outputs)

    assert outputs[0].read_text() == "matrix"
    assert outputs[0].stat().st_ino != source.stat().st_ino
    assert inputs["input_data"] == f"{outputs[0]}::resolutions/10000"
    assert node_class.render_command(inputs) == [
        "cooler",
        "balance",
        "--cis-only",
        "--convergence-policy",
        "error",
        "--nproc",
        "3",
        f"{outputs[0]}::resolutions/10000",
    ]


def test_cooltools_compartments_uses_documented_outputs_and_zero_ignore_diags() -> None:
    node_class = _node_class("cooltools_compartments")
    inputs = {
        "cooler_uri": "matrix.mcool::resolutions/100000",
        "n_eigs": 2,
        "ignore_diags": 0,
        "output_prefix": "case sample",
        "output": "/tmp/run/cooltools_compartments",
    }
    assert node_class.render_command(inputs) == [
        "cooltools",
        "eigs-cis",
        "--n-eigs",
        "2",
        "--ignore-diags",
        "0",
        "--out-prefix",
        "/tmp/run/cooltools_compartments/case_sample",
        "matrix.mcool::resolutions/100000",
    ]
    assert [path.name for path in node_class.PLAN_OUTPUTS(inputs, "/tmp/run")] == [
        "case_sample.cis.vecs.tsv",
        "case_sample.cis.lam.txt",
    ]


def test_cooltools_insulation_preserves_empty_weight_for_raw_data() -> None:
    node_class = _node_class("cooltools_insulation")
    inputs = {
        "cooler_uri": "matrix.cool",
        "window_sizes": "100000,250000",
        "nproc": 2,
        "clr_weight_name": "",
        "ignore_diags": 0,
        "min_frac_valid_pixels": 0.66,
        "min_dist_bad_bin": 0,
        "threshold": "0",
        "chunksize": 20000000,
        "output": "/tmp/run/cooltools_insulation",
    }
    assert node_class.render_command(inputs) == [
        "cooltools",
        "insulation",
        "--nproc",
        "2",
        "--output",
        "/tmp/run/cooltools_insulation/insulation.tsv",
        "--clr-weight-name",
        "",
        "--ignore-diags",
        "0",
        "--min-frac-valid-pixels",
        "0.66",
        "--min-dist-bad-bin",
        "0",
        "--threshold",
        "0",
        "--chunksize",
        "20000000",
        "matrix.cool",
        "100000",
        "250000",
    ]


@pytest.mark.parametrize(
    ("node_id", "inputs", "message"),
    [
        ("methyldackel", {"bam": "x"}, "Required input 'bam_index' is missing"),
        ("dss_dmr", {"methylation_files": "one.tsv"}, "Required input 'sample_info' is missing"),
        ("modkit_dmr", {"sample_a": "a"}, "Required input 'index_a' is missing"),
        ("cooler", {"input_data": "pairs", "mode": "cload"}, "chrom_sizes is required for cload"),
        ("cooltools_insulation", {"cooler_uri": "x.cool", "window_sizes": "0"}, "window sizes must be positive integers."),
    ],
)
def test_epigenomics_validation_fails_closed(node_id: str, inputs: dict[str, object], message: str) -> None:
    assert _node_class(node_id).VALIDATE_INPUTS(inputs) == message
