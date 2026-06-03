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
