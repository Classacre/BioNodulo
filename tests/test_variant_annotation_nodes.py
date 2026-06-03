from __future__ import annotations

from bionodulo.environments.constants import EXECUTABLE_TO_CONDA_PACKAGE, PACKAGE_MIN_VERSIONS
from bionodulo.nodes.registry import NodeRegistry


def _node_class(node_id: str) -> type:
    registry = NodeRegistry.create_isolated()
    registry.load_builtin_nodes()
    node_class = registry.get(node_id)
    assert node_class is not None, f"{node_id} is not registered"
    return node_class


def test_snpeff_is_registered_for_frontend_discovery() -> None:
    registry = NodeRegistry.create_isolated()
    registry.load_builtin_nodes()
    info = registry.object_info()

    node_info = info["snpeff"]
    assert node_info["display_name"] == "SnpEff"
    assert node_info["category"] == "annotation"
    assert node_info["description"].startswith("Fast variant annotation")
    assert node_info["output"] == ["VCF", "HTML_REPORT"]
    assert node_info["output_name"] == ["annotated_vcf", "summary_report"]
    assert node_info["required_executables"] == ["snpEff"]
    assert node_info["required_conda_packages"] == ["snpeff"]
    assert "variant annotation" in node_info["search_aliases"]
    assert "effect prediction" in node_info["search_aliases"]
    assert "functional effect" in node_info["search_aliases"]

    inputs = node_info["input"]
    assert set(inputs["required"]) == {"vcf", "genome", "memory"}
    assert set(inputs["optional"]) == {"canonical", "no_upstream", "no_downstream", "no_intergenic"}


def test_snpeff_renders_command_with_filter_flags() -> None:
    node_class = _node_class("snpeff")

    cmd = node_class.render_command({
        "vcf": "variants.vcf.gz",
        "genome": "GRCh38.99",
        "memory": 12,
        "canonical": True,
        "no_upstream": True,
        "no_downstream": True,
        "no_intergenic": True,
        "output": "/tmp/run/snpeff",
    })

    assert cmd == [
        "java",
        "-jar",
        "-Xmx12g",
        "snpEff.jar",
        "-v",
        "-stats",
        "/tmp/run/snpeff/summary_report.html",
        "-canon",
        "-no-upstream",
        "-no-downstream",
        "-no-intergenic",
        "GRCh38.99",
        "variants.vcf.gz",
        ">",
        "/tmp/run/snpeff/annotated_vcf.vcf",
    ]


def test_snpeff_omits_disabled_optional_flags() -> None:
    node_class = _node_class("snpeff")

    cmd = node_class.render_command({
        "vcf": "variants.vcf",
        "genome": "GRCm39",
        "memory": 4,
        "canonical": False,
        "no_upstream": False,
        "no_downstream": False,
        "no_intergenic": False,
        "output": "/tmp/run/snpeff",
    })

    assert "-canon" not in cmd
    assert "-no-upstream" not in cmd
    assert "-no-downstream" not in cmd
    assert "-no-intergenic" not in cmd
    assert cmd[-4:] == ["GRCm39", "variants.vcf", ">", "/tmp/run/snpeff/annotated_vcf.vcf"]


def test_snpeff_plans_outputs() -> None:
    node_class = _node_class("snpeff")

    outputs = node_class.PLAN_OUTPUTS({}, "/tmp/run")

    assert [str(path) for path in outputs] == [
        "/tmp/run/snpeff/annotated_vcf.vcf",
        "/tmp/run/snpeff/summary_report.html",
    ]


def test_snpeff_environment_metadata_is_declared() -> None:
    assert EXECUTABLE_TO_CONDA_PACKAGE["snpEff"] == "snpeff"
    assert EXECUTABLE_TO_CONDA_PACKAGE["java"] == "openjdk"
    assert PACKAGE_MIN_VERSIONS["snpeff"] == ">=5.2"
    assert PACKAGE_MIN_VERSIONS["openjdk"] == ">=17"


def test_vep_is_registered_for_frontend_discovery() -> None:
    registry = NodeRegistry.create_isolated()
    registry.load_builtin_nodes()
    info = registry.object_info()

    node_info = info["vep"]
    assert node_info["display_name"] == "VEP"
    assert node_info["category"] == "annotation"
    assert node_info["description"].startswith("Ensembl Variant Effect Predictor")
    assert node_info["output"] == ["VCF", "HTML_REPORT"]
    assert node_info["output_name"] == ["annotated_vcf", "vep_report"]
    assert node_info["required_executables"] == ["vep"]
    assert node_info["required_conda_packages"] == ["ensembl-vep"]
    assert "variant effect predictor" in node_info["search_aliases"]
    assert "ensembl" in node_info["search_aliases"]
    assert "clinvar" in node_info["search_aliases"]

    inputs = node_info["input"]
    assert set(inputs["required"]) == {"vcf", "assembly", "cache_dir", "threads"}
    assert set(inputs["optional"]) == {
        "everything",
        "symbol",
        "af",
        "max_af",
        "sift",
        "polyphen",
        "clinvar",
        "output_format",
    }


def test_vep_renders_command_with_annotation_flags() -> None:
    node_class = _node_class("vep")

    cmd = node_class.render_command({
        "vcf": "variants.vcf.gz",
        "assembly": "GRCh38",
        "cache_dir": "/refs/vep-cache",
        "threads": 8,
        "everything": True,
        "symbol": True,
        "af": True,
        "max_af": True,
        "sift": "b",
        "polyphen": "p",
        "clinvar": "clinvar.vcf.gz",
        "output_format": "vcf",
        "output": "/tmp/run/vep",
    })

    assert cmd == [
        "vep",
        "-i",
        "variants.vcf.gz",
        "-o",
        "/tmp/run/vep/annotated_vcf.vcf",
        "--format",
        "vcf",
        "--vcf",
        "--fork",
        "8",
        "--assembly",
        "GRCh38",
        "--cache",
        "--dir_cache",
        "/refs/vep-cache",
        "--everything",
        "--symbol",
        "--af",
        "--max_af",
        "--sift",
        "b",
        "--polyphen",
        "p",
        "--custom",
        "clinvar.vcf.gz,ClinVar,vcf,exact,0,CLNSIG",
        "--stats_file",
        "/tmp/run/vep/vep_report.html",
    ]


def test_vep_omits_disabled_optional_flags_and_supports_tab_output() -> None:
    node_class = _node_class("vep")

    cmd = node_class.render_command({
        "vcf": "variants.vcf",
        "assembly": "GRCh37",
        "cache_dir": "/refs/vep-cache",
        "threads": 2,
        "everything": False,
        "symbol": False,
        "af": False,
        "max_af": False,
        "sift": "",
        "polyphen": "",
        "clinvar": "",
        "output_format": "tab",
        "output": "/tmp/run/vep",
    })

    assert "--everything" not in cmd
    assert "--symbol" not in cmd
    assert "--af" not in cmd
    assert "--max_af" not in cmd
    assert "--sift" not in cmd
    assert "--polyphen" not in cmd
    assert "--custom" not in cmd
    assert cmd[:8] == ["vep", "-i", "variants.vcf", "-o", "/tmp/run/vep/annotated_vcf.tab", "--format", "vcf", "--tab"]


def test_vep_plans_outputs() -> None:
    node_class = _node_class("vep")

    outputs = node_class.PLAN_OUTPUTS({"output_format": "tab"}, "/tmp/run")

    assert [str(path) for path in outputs] == [
        "/tmp/run/vep/annotated_vcf.tab",
        "/tmp/run/vep/vep_report.html",
    ]


def test_vep_environment_metadata_is_declared() -> None:
    assert EXECUTABLE_TO_CONDA_PACKAGE["vep"] == "ensembl-vep"
    assert PACKAGE_MIN_VERSIONS["ensembl-vep"] == ">=113"


def test_annovar_is_registered_for_frontend_discovery() -> None:
    registry = NodeRegistry.create_isolated()
    registry.load_builtin_nodes()
    info = registry.object_info()

    node_info = info["annovar"]
    assert node_info["display_name"] == "ANNOVAR"
    assert node_info["category"] == "annotation"
    assert node_info["description"].startswith("Comprehensive variant annotation")
    assert node_info["output"] == ["CSV", "CSV"]
    assert node_info["output_name"] == ["variant_function", "exonic_variant_function"]
    assert node_info["required_executables"] == ["table_annovar.pl", "convert2annovar.pl"]
    assert node_info["required_conda_packages"] == ["annovar"]
    assert node_info["experimental"] is True
    assert "variant annotation" in node_info["search_aliases"]
    assert "clinical" in node_info["search_aliases"]
    assert "clinvar" in node_info["search_aliases"]
    assert "gnomad" in node_info["search_aliases"]

    inputs = node_info["input"]
    assert set(inputs["required"]) == {"vcf", "humandb_dir", "buildver", "protocol", "operation"}
    assert inputs["optional"] == {}


def test_annovar_renders_convert_and_table_annovar_command() -> None:
    node_class = _node_class("annovar")

    cmd = node_class.render_command({
        "vcf": "variants.vcf.gz",
        "humandb_dir": "/refs/annovar/humandb",
        "buildver": "hg38",
        "protocol": "refGene,cytoBand,gnomad40_genome,clinvar_20220320",
        "operation": "g,r,f,f",
        "output": "/tmp/run/annovar",
    })

    assert cmd == [
        "convert2annovar.pl",
        "-format",
        "vcf4",
        "-withzyg",
        "-includeinfo",
        "variants.vcf.gz",
        ">",
        "/tmp/run/annovar/input.avinput",
        "&&",
        "table_annovar.pl",
        "/tmp/run/annovar/input.avinput",
        "/refs/annovar/humandb",
        "-buildver",
        "hg38",
        "-out",
        "/tmp/run/annovar/annovar",
        "-remove",
        "-protocol",
        "refGene,cytoBand,gnomad40_genome,clinvar_20220320",
        "-operation",
        "g,r,f,f",
        "-nastring",
        ".",
        "-vcfinput",
        "-polish",
    ]


def test_annovar_uses_default_protocol_and_operation() -> None:
    node_class = _node_class("annovar")

    cmd = node_class.render_command({
        "vcf": "variants.vcf",
        "humandb_dir": "/refs/annovar/humandb",
        "buildver": "hg19",
        "output": "/tmp/run/annovar",
    })

    assert "refGene,cytoBand,gnomad40_genome,clinvar_20220320" in cmd
    assert "g,r,f,f" in cmd
    assert cmd[cmd.index("-buildver") + 1] == "hg19"


def test_annovar_plans_outputs() -> None:
    node_class = _node_class("annovar")

    outputs = node_class.PLAN_OUTPUTS({}, "/tmp/run")

    assert [str(path) for path in outputs] == [
        "/tmp/run/annovar/variant_function.csv",
        "/tmp/run/annovar/exonic_variant_function.csv",
    ]


def test_annovar_environment_metadata_is_declared() -> None:
    assert EXECUTABLE_TO_CONDA_PACKAGE["table_annovar.pl"] == "annovar"
    assert EXECUTABLE_TO_CONDA_PACKAGE["convert2annovar.pl"] == "annovar"
    assert PACKAGE_MIN_VERSIONS["annovar"] == ">=2020-06-08"


def test_bcftools_annotate_is_registered_for_frontend_discovery() -> None:
    registry = NodeRegistry.create_isolated()
    registry.load_builtin_nodes()
    info = registry.object_info()

    node_info = info["bcftools_annotate"]
    assert node_info["display_name"] == "bcftools Annotate"
    assert node_info["category"] == "annotation"
    assert node_info["description"].startswith("Annotate VCF with custom annotations")
    assert node_info["output"] == ["VCF_GZ"]
    assert node_info["output_name"] == ["annotated_vcf"]
    assert node_info["required_executables"] == ["bcftools"]
    assert node_info["required_conda_packages"] == ["bcftools"]
    assert "bcftools" in node_info["search_aliases"]
    assert "annotate" in node_info["search_aliases"]
    assert "custom annotation" in node_info["search_aliases"]

    inputs = node_info["input"]
    assert set(inputs["required"]) == {"vcf", "annotations"}
    assert set(inputs["optional"]) == {"columns", "header_lines", "threads"}


def test_bcftools_annotate_renders_custom_annotation_command() -> None:
    node_class = _node_class("bcftools_annotate")

    cmd = node_class.render_command({
        "vcf": "variants.vcf.gz",
        "annotations": "genes.bed.gz",
        "columns": "CHROM,FROM,TO,GENE",
        "header_lines": "genes.hdr",
        "threads": 8,
        "output": "/tmp/run/bcftools_annotate",
    })

    assert cmd == [
        "bcftools",
        "annotate",
        "-a",
        "genes.bed.gz",
        "-c",
        "CHROM,FROM,TO,GENE",
        "-h",
        "genes.hdr",
        "--threads",
        "8",
        "-Oz",
        "-o",
        "/tmp/run/bcftools_annotate/annotated_vcf.vcf.gz",
        "variants.vcf.gz",
        "&&",
        "bcftools",
        "index",
        "-t",
        "/tmp/run/bcftools_annotate/annotated_vcf.vcf.gz",
    ]


def test_bcftools_annotate_omits_empty_optional_flags() -> None:
    node_class = _node_class("bcftools_annotate")

    cmd = node_class.render_command({
        "vcf": "variants.vcf.gz",
        "annotations": "annotations.tsv.gz",
        "columns": "",
        "header_lines": "",
        "threads": 0,
        "output": "/tmp/run/bcftools_annotate",
    })

    assert "-c" not in cmd
    assert "-h" not in cmd
    assert "--threads" not in cmd
    assert cmd == [
        "bcftools",
        "annotate",
        "-a",
        "annotations.tsv.gz",
        "-Oz",
        "-o",
        "/tmp/run/bcftools_annotate/annotated_vcf.vcf.gz",
        "variants.vcf.gz",
        "&&",
        "bcftools",
        "index",
        "-t",
        "/tmp/run/bcftools_annotate/annotated_vcf.vcf.gz",
    ]


def test_bcftools_annotate_plans_outputs() -> None:
    node_class = _node_class("bcftools_annotate")

    outputs = node_class.PLAN_OUTPUTS({}, "/tmp/run")

    assert [str(path) for path in outputs] == [
        "/tmp/run/bcftools_annotate/annotated_vcf.vcf.gz",
    ]


def test_bcftools_annotate_environment_metadata_is_declared() -> None:
    assert EXECUTABLE_TO_CONDA_PACKAGE["bcftools"] == "bcftools"
    assert PACKAGE_MIN_VERSIONS["bcftools"] == ">=1.15"


def test_interproscan_is_registered_for_frontend_discovery() -> None:
    registry = NodeRegistry.create_isolated()
    registry.load_builtin_nodes()
    info = registry.object_info()

    node_info = info["interproscan"]
    assert node_info["display_name"] == "InterProScan"
    assert node_info["category"] == "annotation"
    assert node_info["description"].startswith("Scan proteins for domains")
    assert node_info["output"] == ["TSV", "JSON", "GFF"]
    assert node_info["output_name"] == ["ipr_matches", "ipr_json", "ipr_gff"]
    assert node_info["required_executables"] == ["interproscan.sh"]
    assert node_info["required_conda_packages"] == ["interproscan"]
    assert node_info["experimental"] is True
    assert "protein domain" in node_info["search_aliases"]
    assert "pfam" in node_info["search_aliases"]
    assert "go annotation" in node_info["search_aliases"]
    assert "interpro" in node_info["search_aliases"]

    inputs = node_info["input"]
    assert set(inputs["required"]) == {"fasta", "threads"}
    assert set(inputs["optional"]) == {"applications", "goterms", "iprlookup", "pathways"}


def test_interproscan_renders_command_with_annotation_flags() -> None:
    node_class = _node_class("interproscan")

    cmd = node_class.render_command({
        "fasta": "proteins.faa",
        "threads": 8,
        "applications": "Pfam,Gene3D",
        "goterms": True,
        "iprlookup": True,
        "pathways": True,
        "output": "/tmp/run/interproscan",
    })

    assert cmd == [
        "interproscan.sh",
        "-i",
        "proteins.faa",
        "-b",
        "/tmp/run/interproscan/ipr",
        "-f",
        "TSV,JSON,GFF3",
        "-cpu",
        "8",
        "-appl",
        "Pfam,Gene3D",
        "-goterms",
        "-iprlookup",
        "-pa",
    ]


def test_interproscan_omits_disabled_optional_flags() -> None:
    node_class = _node_class("interproscan")

    cmd = node_class.render_command({
        "fasta": "proteins.faa",
        "threads": 2,
        "applications": "",
        "goterms": False,
        "iprlookup": False,
        "pathways": False,
        "output": "/tmp/run/interproscan",
    })

    assert "-appl" not in cmd
    assert "-goterms" not in cmd
    assert "-iprlookup" not in cmd
    assert "-pa" not in cmd
    assert cmd == [
        "interproscan.sh",
        "-i",
        "proteins.faa",
        "-b",
        "/tmp/run/interproscan/ipr",
        "-f",
        "TSV,JSON,GFF3",
        "-cpu",
        "2",
    ]


def test_interproscan_plans_outputs() -> None:
    node_class = _node_class("interproscan")

    outputs = node_class.PLAN_OUTPUTS({}, "/tmp/run")

    assert [str(path) for path in outputs] == [
        "/tmp/run/interproscan/ipr.tsv",
        "/tmp/run/interproscan/ipr.json",
        "/tmp/run/interproscan/ipr.gff3",
    ]


def test_interproscan_environment_metadata_is_declared() -> None:
    assert EXECUTABLE_TO_CONDA_PACKAGE["interproscan.sh"] == "interproscan"
    assert PACKAGE_MIN_VERSIONS["interproscan"] == ">=5.71"
