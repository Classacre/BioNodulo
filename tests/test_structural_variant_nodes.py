from __future__ import annotations

from pathlib import Path

from bionodulo.nodes.registry import NodeRegistry


def _node_class(node_id: str) -> type:
    registry = NodeRegistry.create_isolated()
    registry.load_builtin_nodes()
    node_class = registry.get(node_id)
    assert node_class is not None, f"{node_id} is not registered"
    return node_class


def test_sniffles2_is_registered_for_frontend_discovery() -> None:
    registry = NodeRegistry.create_isolated()
    registry.load_builtin_nodes()
    info = registry.object_info()

    node_info = info["sniffles2"]
    assert node_info["display_name"] == "Sniffles2 SV Caller"
    assert node_info["category"] == "variant"
    assert node_info["description"].startswith("Long-read SV caller")
    assert node_info["output"] == ["VCF_GZ"]
    assert node_info["output_name"] == ["sv_vcf"]
    assert node_info["required_executables"] == ["sniffles"]
    assert node_info["required_conda_packages"] == ["sniffles"]
    assert "long-read sv" in node_info["search_aliases"]
    assert "nanopore sv" in node_info["search_aliases"]

    inputs = node_info["input"]
    assert set(inputs["required"]) == {"bam", "reference", "threads"}
    assert set(inputs["optional"]) == {
        "tandem_repeats",
        "minsvlen",
        "minsupport",
        "phase",
    }


def test_sniffles2_renders_long_read_sv_command() -> None:
    node_class = _node_class("sniffles2")

    cmd = node_class.render_command({
        "bam": "sample.sorted.bam",
        "reference": "GRCh38.fa",
        "threads": 12,
        "tandem_repeats": "human_hs37d5.trf.bed",
        "minsvlen": 75,
        "minsupport": 6,
        "phase": True,
        "output": "/tmp/run/sniffles2",
    })

    assert cmd == [
        "sniffles",
        "--input",
        "sample.sorted.bam",
        "--vcf",
        "/tmp/run/sniffles2/sv_vcf.vcf.gz",
        "--reference",
        "GRCh38.fa",
        "--threads",
        "12",
        "--tandem-repeats",
        "human_hs37d5.trf.bed",
        "--minsvlen",
        "75",
        "--minsupport",
        "6",
        "--phase",
    ]


def test_sniffles2_plans_compressed_vcf_output() -> None:
    node_class = _node_class("sniffles2")

    outputs = node_class.PLAN_OUTPUTS({}, "/tmp/run")

    assert [str(path) for path in outputs] == ["/tmp/run/sniffles2/sv_vcf.vcf.gz"]


def test_survivor_merge_is_registered_for_frontend_discovery() -> None:
    registry = NodeRegistry.create_isolated()
    registry.load_builtin_nodes()
    info = registry.object_info()

    node_info = info["survivor_merge"]
    assert node_info["display_name"] == "SURVIVOR Merge"
    assert node_info["category"] == "variant"
    assert node_info["description"].startswith("Merge SV calls")
    assert node_info["output"] == ["VCF"]
    assert node_info["output_name"] == ["merged_sv"]
    assert node_info["required_executables"] == ["SURVIVOR"]
    assert node_info["required_conda_packages"] == ["survivor"]
    assert "consensus sv" in node_info["search_aliases"]
    assert "multi-caller" in node_info["search_aliases"]

    inputs = node_info["input"]
    assert set(inputs["required"]) == {"vcf_files", "max_distance", "min_callers"}
    assert set(inputs["optional"]) == {"use_type", "use_strand", "min_sv_size"}


def test_survivor_merge_writes_input_list_and_renders_command(tmp_path: Path) -> None:
    node_class = _node_class("survivor_merge")
    output_dir = tmp_path / "survivor_merge"
    output_dir.mkdir()

    cmd = node_class.render_command({
        "vcf_files": ["manta.vcf.gz", "delly.vcf.gz", "sniffles.vcf.gz"],
        "max_distance": 500,
        "min_callers": 2,
        "use_type": 1,
        "use_strand": 0,
        "min_sv_size": 50,
        "output": str(output_dir),
    })

    sample_list = output_dir / "sample_files.txt"
    assert sample_list.read_text(encoding="utf-8") == "manta.vcf.gz\ndelly.vcf.gz\nsniffles.vcf.gz\n"
    assert cmd == [
        "SURVIVOR",
        "merge",
        str(sample_list),
        "500",
        "2",
        "1",
        "0",
        "50",
        str(output_dir / "merged_sv.vcf"),
    ]


def test_survivor_merge_accepts_single_vcf_string(tmp_path: Path) -> None:
    node_class = _node_class("survivor_merge")
    output_dir = tmp_path / "survivor_merge"
    output_dir.mkdir()

    cmd = node_class.render_command({
        "vcf_files": "sniffles.vcf.gz",
        "output": str(output_dir),
    })

    assert (output_dir / "sample_files.txt").read_text(encoding="utf-8") == "sniffles.vcf.gz\n"
    assert cmd[2] == str(output_dir / "sample_files.txt")
    assert cmd[-1] == str(output_dir / "merged_sv.vcf")


def test_cutesv_is_registered_for_frontend_discovery() -> None:
    registry = NodeRegistry.create_isolated()
    registry.load_builtin_nodes()
    info = registry.object_info()

    node_info = info["cutesv"]
    assert node_info["display_name"] == "cuteSV Caller"
    assert node_info["category"] == "variant"
    assert node_info["description"].startswith("Efficient long-read SV caller")
    assert node_info["output"] == ["VCF"]
    assert node_info["output_name"] == ["sv_vcf"]
    assert node_info["required_executables"] == ["cuteSV"]
    assert node_info["required_conda_packages"] == ["cute-sv"]
    assert "long-read sv" in node_info["search_aliases"]
    assert "pacbio sv" in node_info["search_aliases"]

    inputs = node_info["input"]
    assert set(inputs["required"]) == {"bam", "reference", "sample_name", "threads"}
    assert set(inputs["optional"]) == {"max_cluster_bias_ins", "min_size", "max_size"}


def test_cutesv_renders_long_read_sv_command() -> None:
    node_class = _node_class("cutesv")

    cmd = node_class.render_command({
        "bam": "sample.sorted.bam",
        "reference": "GRCh38.fa",
        "sample_name": "tumor-01",
        "threads": 16,
        "max_cluster_bias_ins": 750,
        "min_size": 40,
        "max_size": 50000,
        "output": "/tmp/run/cutesv",
    })

    assert cmd == [
        "cuteSV",
        "--threads",
        "16",
        "--genome",
        "GRCh38.fa",
        "--sample",
        "tumor-01",
        "--max_cluster_bias_INS",
        "750",
        "--min_size",
        "40",
        "--max_size",
        "50000",
        "sample.sorted.bam",
        "/tmp/run/cutesv/sv_vcf.vcf",
        "/tmp/run/cutesv",
    ]


def test_cutesv_plans_vcf_output() -> None:
    node_class = _node_class("cutesv")

    outputs = node_class.PLAN_OUTPUTS({}, "/tmp/run")

    assert [str(path) for path in outputs] == ["/tmp/run/cutesv/sv_vcf.vcf"]


def test_svim_is_registered_for_frontend_discovery() -> None:
    registry = NodeRegistry.create_isolated()
    registry.load_builtin_nodes()
    info = registry.object_info()

    node_info = info["svim"]
    assert node_info["display_name"] == "SVIM SV Caller"
    assert node_info["category"] == "variant"
    assert node_info["description"].startswith("Long-read SV caller")
    assert node_info["output"] == ["VCF"]
    assert node_info["output_name"] == ["sv_vcf"]
    assert node_info["required_executables"] == ["svim"]
    assert node_info["required_conda_packages"] == ["svim"]
    assert "long-read sv" in node_info["search_aliases"]
    assert "nanopore sv" in node_info["search_aliases"]

    inputs = node_info["input"]
    assert set(inputs["required"]) == {"bam", "reference", "sample_name"}
    assert set(inputs["optional"]) == {
        "min_sv_size",
        "max_sv_size",
        "sequence_alleles",
        "symbolic_alleles",
    }


def test_svim_renders_long_read_sv_command() -> None:
    node_class = _node_class("svim")

    cmd = node_class.render_command({
        "bam": "sample.sorted.bam",
        "reference": "GRCh38.fa",
        "sample_name": "tumor-01",
        "min_sv_size": 75,
        "max_sv_size": 250000,
        "sequence_alleles": True,
        "symbolic_alleles": True,
        "output": "/tmp/run/svim",
    })

    assert cmd == [
        "svim",
        "alignment",
        "--sample",
        "tumor-01",
        "--min_sv_size",
        "75",
        "--max_sv_size",
        "250000",
        "--sequence_alleles",
        "--symbolic_alleles",
        "--interspersed_duplications_as_insertions",
        "--tandem_duplications_as_insertions",
        "/tmp/run/svim",
        "sample.sorted.bam",
        "GRCh38.fa",
    ]


def test_svim_plans_vcf_output() -> None:
    node_class = _node_class("svim")

    outputs = node_class.PLAN_OUTPUTS({}, "/tmp/run")

    assert [str(path) for path in outputs] == ["/tmp/run/svim/sv_vcf.vcf"]


def test_smoove_is_registered_for_frontend_discovery() -> None:
    registry = NodeRegistry.create_isolated()
    registry.load_builtin_nodes()
    info = registry.object_info()

    node_info = info["smoove"]
    assert node_info["display_name"] == "Smoove SV Caller"
    assert node_info["category"] == "variant"
    assert node_info["description"].startswith("Automated SV calling")
    assert node_info["output"] == ["VCF_GZ"]
    assert node_info["output_name"] == ["genotyped_sv"]
    assert node_info["required_executables"] == ["smoove"]
    assert node_info["required_conda_packages"] == ["smoove", "lumpy-sv", "svtyper"]
    assert "lumpy" in node_info["search_aliases"]
    assert "genotyped sv" in node_info["search_aliases"]

    inputs = node_info["input"]
    assert set(inputs["required"]) == {"bam", "reference", "sample_name", "threads"}
    assert set(inputs["optional"]) == {"exclude", "genotype"}


def test_smoove_renders_structural_variant_command() -> None:
    node_class = _node_class("smoove")

    cmd = node_class.render_command({
        "bam": "sample.sorted.bam",
        "reference": "GRCh38.fa",
        "sample_name": "tumor-01",
        "threads": 12,
        "exclude": "exclude.bed",
        "genotype": True,
        "output": "/tmp/run/smoove",
    })

    assert cmd == [
        "smoove",
        "call",
        "--name",
        "tumor-01",
        "--fasta",
        "GRCh38.fa",
        "-p",
        "12",
        "--outdir",
        "/tmp/run/smoove",
        "--genotype",
        "--exclude",
        "exclude.bed",
        "sample.sorted.bam",
    ]


def test_smoove_plans_genotyped_vcf_output() -> None:
    node_class = _node_class("smoove")

    outputs = node_class.PLAN_OUTPUTS({}, "/tmp/run")

    assert [str(path) for path in outputs] == ["/tmp/run/smoove/genotyped_sv.vcf.gz"]


def test_delly_is_registered_for_frontend_discovery() -> None:
    registry = NodeRegistry.create_isolated()
    registry.load_builtin_nodes()
    info = registry.object_info()

    node_info = info["delly"]
    assert node_info["display_name"] == "DELLY SV Caller"
    assert node_info["category"] == "variant"
    assert node_info["description"].startswith("Paired-end + split-read SV caller")
    assert node_info["output"] == ["BCF"]
    assert node_info["output_name"] == ["sv_calls"]
    assert node_info["required_executables"] == ["delly"]
    assert node_info["required_conda_packages"] == ["delly"]
    assert "somatic sv" in node_info["search_aliases"]
    assert "long-read sv" in node_info["search_aliases"]

    inputs = node_info["input"]
    assert set(inputs["required"]) == {"bam", "reference", "mode"}
    assert set(inputs["optional"]) == {"exclude_regions", "map_qual"}


def test_delly_renders_short_read_structural_variant_command() -> None:
    node_class = _node_class("delly")

    cmd = node_class.render_command({
        "bam": "tumor.sorted.bam",
        "reference": "GRCh38.fa",
        "mode": "call",
        "exclude_regions": "exclude.bed",
        "map_qual": 20,
        "output": "/tmp/run/delly",
    })

    assert cmd == [
        "delly",
        "call",
        "-g",
        "GRCh38.fa",
        "-o",
        "/tmp/run/delly/sv_calls.bcf",
        "-x",
        "exclude.bed",
        "-q",
        "20",
        "tumor.sorted.bam",
    ]


def test_delly_renders_long_read_mode_command() -> None:
    node_class = _node_class("delly")

    cmd = node_class.render_command({
        "bam": "ont.sorted.bam",
        "reference": "GRCh38.fa",
        "mode": "lr",
        "output": "/tmp/run/delly",
    })

    assert cmd == [
        "delly",
        "lr",
        "-g",
        "GRCh38.fa",
        "-o",
        "/tmp/run/delly/sv_calls.bcf",
        "ont.sorted.bam",
    ]


def test_delly_plans_bcf_output() -> None:
    node_class = _node_class("delly")

    outputs = node_class.PLAN_OUTPUTS({}, "/tmp/run")

    assert [str(path) for path in outputs] == ["/tmp/run/delly/sv_calls.bcf"]
