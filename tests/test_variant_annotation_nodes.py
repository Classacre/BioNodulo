from __future__ import annotations

import csv
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from bionodulo.environments.constants import EXECUTABLE_TO_CONDA_PACKAGE, PACKAGE_MIN_VERSIONS
from bionodulo.nodes.builtin.annotation import FuncotateTableNode
from bionodulo.nodes.registry import NodeRegistry


def _node_class(node_id: str) -> type:
    registry = NodeRegistry.create_isolated()
    registry.load_builtin_nodes()
    node_class = registry.get(node_id)
    assert node_class is not None, f"{node_id} is not registered"
    return node_class


def _context(tmp_path: Path, name: str) -> SimpleNamespace:
    node_dir = tmp_path / name
    node_dir.mkdir()
    return SimpleNamespace(node_dir=node_dir)


def _read_table(path: str | Path, delimiter: str = "	") -> list[dict[str, str]]:
    with Path(path).open(newline="", encoding="utf-8") as fh:
        return list(csv.DictReader(fh, delimiter=delimiter))


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
    assert info["vep_annotate"]["display_name"] == "VEP Annotate"
    assert info["vep_annotate"]["category"] == "annotation"
    assert info["vep_annotate"]["output"] == ["VCF", "HTML_REPORT"]
    assert info["vep_annotate"]["output_name"] == ["annotated_vcf", "vep_report"]
    assert info["vep_annotate"]["required_executables"] == ["vep"]
    assert info["vep_annotate"]["required_conda_packages"] == ["ensembl-vep"]
    assert issubclass(registry.get("vep_annotate"), registry.get("vep"))

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


def test_funcotate_table_is_registered_for_frontend_discovery() -> None:
    registry = NodeRegistry.create_isolated()
    registry.load_builtin_nodes()
    info = registry.object_info()

    node_info = info["funcotate_table"]
    assert node_info["display_name"] == "Funcotate Table"
    assert node_info["category"] == "annotation"
    assert node_info["description"].startswith("Oncotator-style functional annotation")
    assert node_info["output"] == ["FILE", "FILE"]
    assert node_info["output_name"] == ["annotated", "summary"]
    assert node_info["required_executables"] == ["gatk"]
    assert node_info["required_conda_packages"] == ["gatk4"]
    assert "funcotator" in node_info["search_aliases"]
    assert "cancer variants" in node_info["search_aliases"]
    assert "oncotator" in node_info["search_aliases"]

    inputs = node_info["input"]
    assert set(inputs["required"]) == {"vcf", "reference", "data_sources", "ref_version"}
    assert set(inputs["optional"]) == {
        "output_format",
        "transcript_selection_mode",
        "annotation_defaults",
        "annotation_overrides",
        "intervals",
    }


def test_funcotate_table_renders_gatk_funcotator_command() -> None:
    node_class = _node_class("funcotate_table")

    cmd = node_class.render_command({
        "vcf": "somatic.vcf.gz",
        "reference": "GRCh38.fa",
        "data_sources": "/refs/funcotator",
        "ref_version": "hg38",
        "output_format": "MAF",
        "transcript_selection_mode": "CANONICAL",
        "annotation_defaults": "Center:BioNodulo,NCBI_Build:GRCh38",
        "annotation_overrides": "Tumor_Sample_Barcode:TUMOR",
        "intervals": "targets.interval_list",
        "output": "/tmp/run/funcotate_table",
    })

    assert cmd == [
        "gatk",
        "Funcotator",
        "-R",
        "GRCh38.fa",
        "-V",
        "somatic.vcf.gz",
        "-O",
        "/tmp/run/funcotate_table/annotated.maf",
        "--output-file-format",
        "MAF",
        "--data-sources-path",
        "/refs/funcotator",
        "--ref-version",
        "hg38",
        "--transcript-selection-mode",
        "CANONICAL",
        "--annotation-default",
        "Center:BioNodulo",
        "--annotation-default",
        "NCBI_Build:GRCh38",
        "--annotation-override",
        "Tumor_Sample_Barcode:TUMOR",
        "-L",
        "targets.interval_list",
        "&&",
        "printf",
        "'tool\\tgatk Funcotator\\ninput\\tsomatic.vcf.gz\\noutput\\t/tmp/run/funcotate_table/annotated.maf\\nformat\\tMAF\\nref_version\\thg38\\n'",
        ">",
        "/tmp/run/funcotate_table/summary.tsv",
    ]


def test_funcotate_table_supports_vcf_output_and_omits_empty_optional_flags() -> None:
    node_class = _node_class("funcotate_table")

    cmd = node_class.render_command({
        "vcf": "germline.vcf.gz",
        "reference": "GRCh37.fa",
        "data_sources": "/refs/funcotator",
        "ref_version": "hg19",
        "output_format": "VCF",
        "transcript_selection_mode": "",
        "annotation_defaults": "",
        "annotation_overrides": "",
        "intervals": "",
        "output": "/tmp/run/funcotate_table",
    })

    assert "--transcript-selection-mode" not in cmd
    assert "--annotation-default" not in cmd
    assert "--annotation-override" not in cmd
    assert "-L" not in cmd
    assert "/tmp/run/funcotate_table/annotated.vcf" in cmd
    assert "format\\tVCF" in cmd[-3]


def test_funcotate_table_plans_outputs_by_format() -> None:
    node_class = _node_class("funcotate_table")

    maf_outputs = node_class.PLAN_OUTPUTS({"output_format": "MAF"}, "/tmp/run")
    vcf_outputs = node_class.PLAN_OUTPUTS({"output_format": "VCF"}, "/tmp/run")

    assert [str(path) for path in maf_outputs] == [
        "/tmp/run/funcotate_table/annotated.maf",
        "/tmp/run/funcotate_table/summary.tsv",
    ]
    assert [str(path) for path in vcf_outputs] == [
        "/tmp/run/funcotate_table/annotated.vcf",
        "/tmp/run/funcotate_table/summary.tsv",
    ]


def test_funcotator_alias_is_registered_for_frontend_discovery() -> None:
    registry = NodeRegistry.create_isolated()
    registry.load_builtin_nodes()
    info = registry.object_info()

    node_class = registry.get("funcotator")
    assert node_class is not None
    assert issubclass(node_class, FuncotateTableNode)
    assert node_class.render_command.__func__ is FuncotateTableNode.render_command.__func__
    assert node_class.PLAN_OUTPUTS.__func__ is FuncotateTableNode.PLAN_OUTPUTS.__func__
    assert node_class.INPUT_TYPES.__func__ is FuncotateTableNode.INPUT_TYPES.__func__
    assert {name for name in node_class.__dict__ if not name.startswith("_")} == {
        "NODE_ID",
        "DISPLAY_NAME",
        "DESCRIPTION",
        "SEARCH_ALIASES",
    }

    node_info = info["funcotator"]
    assert node_info["display_name"] == "Funcotator"
    assert node_info["category"] == "annotation"
    assert node_info["description"] == "Annotate cancer variants with GATK Funcotator."
    assert node_info["output"] == ["FILE", "FILE"]
    assert node_info["output_name"] == ["annotated", "summary"]
    assert node_info["required_executables"] == ["gatk"]
    assert node_info["required_conda_packages"] == ["gatk4"]
    assert {
        "funcotator",
        "funcotate",
        "gatk funcotator",
        "cancer variants",
        "somatic annotation",
        "oncotator",
    }.issubset(node_info["search_aliases"])


def test_funcotator_alias_renders_gatk_funcotator_command() -> None:
    node_class = _node_class("funcotator")

    cmd = node_class.render_command({
        "vcf": "somatic.vcf.gz",
        "reference": "GRCh38.fa",
        "data_sources": "/refs/funcotator",
        "ref_version": "hg38",
        "output_format": "MAF",
        "transcript_selection_mode": "CANONICAL",
        "annotation_defaults": "Center:BioNodulo,NCBI_Build:GRCh38",
        "annotation_overrides": "Tumor_Sample_Barcode:TUMOR",
        "intervals": "targets.interval_list",
        "output": "/tmp/run/funcotator",
    })

    assert cmd == [
        "gatk",
        "Funcotator",
        "-R",
        "GRCh38.fa",
        "-V",
        "somatic.vcf.gz",
        "-O",
        "/tmp/run/funcotator/annotated.maf",
        "--output-file-format",
        "MAF",
        "--data-sources-path",
        "/refs/funcotator",
        "--ref-version",
        "hg38",
        "--transcript-selection-mode",
        "CANONICAL",
        "--annotation-default",
        "Center:BioNodulo",
        "--annotation-default",
        "NCBI_Build:GRCh38",
        "--annotation-override",
        "Tumor_Sample_Barcode:TUMOR",
        "-L",
        "targets.interval_list",
        "&&",
        "printf",
        "'tool\\tgatk Funcotator\\ninput\\tsomatic.vcf.gz\\noutput\\t/tmp/run/funcotator/annotated.maf\\nformat\\tMAF\\nref_version\\thg38\\n'",
        ">",
        "/tmp/run/funcotator/summary.tsv",
    ]


def test_funcotator_alias_plans_outputs_under_funcotator_directory() -> None:
    node_class = _node_class("funcotator")

    maf_outputs = node_class.PLAN_OUTPUTS({"output_format": "MAF"}, "/tmp/run")
    vcf_outputs = node_class.PLAN_OUTPUTS({"output_format": "VCF"}, "/tmp/run")

    assert [str(path) for path in maf_outputs] == [
        "/tmp/run/funcotator/annotated.maf",
        "/tmp/run/funcotator/summary.tsv",
    ]
    assert [str(path) for path in vcf_outputs] == [
        "/tmp/run/funcotator/annotated.vcf",
        "/tmp/run/funcotator/summary.tsv",
    ]


def test_funcotate_table_environment_metadata_is_declared() -> None:
    assert EXECUTABLE_TO_CONDA_PACKAGE["gatk"] == "gatk4"
    assert PACKAGE_MIN_VERSIONS["gatk4"] == ">=4.4.0"


def test_bcftools_annotate_is_registered_for_frontend_discovery() -> None:
    registry = NodeRegistry.create_isolated()
    registry.load_builtin_nodes()
    info = registry.object_info()

    node_info = info["bcftools_annotate"]
    assert node_info["display_name"] == "BCFtools Annotate"
    assert node_info["category"] == "variant"
    assert node_info["description"].startswith("Annotate and edit VCF/BCF records")
    assert node_info["output"] == ["VCF_GZ"]
    assert node_info["output_name"] == ["annotated_vcf"]
    assert node_info["required_executables"] == ["bcftools", "bgzip", "tabix"]
    assert node_info["required_conda_packages"] == ["bcftools", "htslib"]
    assert node_info["documentation_url"] == "https://www.htslib.org/doc/bcftools.html#annotate"
    assert node_info["citation_dois"] == ["10.1093/gigascience/giab008", "10.1093/bioinformatics/btp352"]
    assert "bcftools" in node_info["search_aliases"]
    assert "annotate" in node_info["search_aliases"]
    assert "custom annotation" in node_info["search_aliases"]

    inputs = node_info["input"]
    assert set(inputs["required"]) == {"input_file"}
    assert "annotations" in inputs["optional"]
    assert "columns" in inputs["optional"]
    assert "remove" in inputs["optional"]
    assert "vcf" in inputs["optional"]
    assert "annotation_columns" in inputs["optional"]


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
        "bgzip",
        "-c",
        "genes.bed.gz",
        ">",
        "/tmp/run/bcftools_annotate/annotations.bed.gz",
        "&&",
        "tabix",
        "-s",
        "1",
        "-b",
        "2",
        "-e",
        "3",
        "/tmp/run/bcftools_annotate/annotations.bed.gz",
        "&&",
        "bcftools",
        "annotate",
        "--columns",
        "CHROM,FROM,TO,GENE",
        "--annotations",
        "/tmp/run/bcftools_annotate/annotations.bed.gz",
        "--header-lines",
        "genes.hdr",
        "--output-type",
        "z",
        "--threads",
        "8",
        "variants.vcf.gz",
        ">",
        "/tmp/run/bcftools_annotate/annotated.vcf.gz",
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

    assert "--columns" not in cmd
    assert "--header-lines" not in cmd
    assert "--threads" not in cmd
    assert cmd == [
        "bgzip",
        "-c",
        "annotations.tsv.gz",
        ">",
        "/tmp/run/bcftools_annotate/annotations.tab.gz",
        "&&",
        "tabix",
        "-s",
        "1",
        "-b",
        "2",
        "-e",
        "2",
        "/tmp/run/bcftools_annotate/annotations.tab.gz",
        "&&",
        "bcftools",
        "annotate",
        "--annotations",
        "/tmp/run/bcftools_annotate/annotations.tab.gz",
        "--output-type",
        "z",
        "variants.vcf.gz",
        ">",
        "/tmp/run/bcftools_annotate/annotated.vcf.gz",
    ]


def test_bcftools_annotate_plans_outputs() -> None:
    node_class = _node_class("bcftools_annotate")

    outputs = node_class.PLAN_OUTPUTS({}, "/tmp/run")

    assert [str(path) for path in outputs] == [
        "/tmp/run/bcftools_annotate/annotated.vcf.gz",
    ]


def test_bcftools_annotate_environment_metadata_is_declared() -> None:
    assert EXECUTABLE_TO_CONDA_PACKAGE["bcftools"] == "bcftools"
    assert PACKAGE_MIN_VERSIONS["bcftools"] == ">=1.15"


def test_annotate_vcf_is_registered_for_frontend_discovery() -> None:
    registry = NodeRegistry.create_isolated()
    registry.load_builtin_nodes()
    info = registry.object_info()

    node_info = info["annotate_vcf"]
    assert node_info["display_name"] == "Annotate VCF"
    assert node_info["category"] == "annotation"
    assert node_info["description"].startswith("Annotate VCF records with gene")
    assert node_info["output"] == ["VCF_GZ", "VCF_INDEX"]
    assert node_info["output_name"] == ["annotated_vcf", "annotated_vcf_index"]
    assert node_info["required_executables"] == ["bcftools", "vcfanno"]
    assert node_info["required_conda_packages"] == ["bcftools", "vcfanno"]
    assert "multi-source annotation" in node_info["search_aliases"]
    assert "roadmap" in node_info["search_aliases"]

    inputs = node_info["input"]
    assert set(inputs["required"]) == {"vcf"}
    assert set(inputs["optional"]) == {
        "mode",
        "annotation_files",
        "vcfanno_config",
        "columns",
        "header_lines",
        "output_name",
        "threads",
    }


def test_annotate_vcf_environment_metadata_is_declared() -> None:
    assert EXECUTABLE_TO_CONDA_PACKAGE["vcfanno"] == "vcfanno"
    assert PACKAGE_MIN_VERSIONS["vcfanno"] == ">=0.3.5"


def test_annotate_vcf_renders_vcfanno_multi_source_command() -> None:
    node_class = _node_class("annotate_vcf")

    cmd = node_class.render_command({
        "vcf": "variants.vcf.gz",
        "mode": "vcfanno",
        "vcfanno_config": "annotation.toml",
        "threads": 6,
        "output": "/tmp/run/annotate_vcf",
        "output_name": "sample annotations",
    })

    assert cmd == [
        "set",
        "-euo",
        "pipefail",
        "&&",
        "vcfanno",
        "-p",
        "6",
        "annotation.toml",
        "variants.vcf.gz",
        "|",
        "bcftools",
        "view",
        "-Oz",
        "-o",
        "/tmp/run/annotate_vcf/sample_annotations.annotated.vcf.gz",
        "&&",
        "bcftools",
        "index",
        "-f",
        "-t",
        "/tmp/run/annotate_vcf/sample_annotations.annotated.vcf.gz",
    ]


def test_annotate_vcf_renders_bcftools_custom_annotation_command() -> None:
    node_class = _node_class("annotate_vcf")

    cmd = node_class.render_command({
        "vcf": "variants.vcf.gz",
        "mode": "bcftools",
        "annotation_files": "genes.bed.gz\nclinvar.vcf.gz",
        "columns": "CHROM,FROM,TO,GENE\nID,INFO/CLNSIG",
        "header_lines": "genes.hdr\nclinvar.hdr",
        "threads": 4,
        "output": "/tmp/run/annotate_vcf",
    })

    assert cmd == [
        "set",
        "-euo",
        "pipefail",
        "&&",
        "bcftools",
        "annotate",
        "-a",
        "genes.bed.gz",
        "-c",
        "CHROM,FROM,TO,GENE",
        "-h",
        "genes.hdr",
        "--threads",
        "4",
        "-Ou",
        "variants.vcf.gz",
        "|",
        "bcftools",
        "annotate",
        "-a",
        "clinvar.vcf.gz",
        "-c",
        "ID,INFO/CLNSIG",
        "-h",
        "clinvar.hdr",
        "--threads",
        "4",
        "-Oz",
        "-o",
        "/tmp/run/annotate_vcf/annotated_vcf.annotated.vcf.gz",
        "-",
        "&&",
        "bcftools",
        "index",
        "-f",
        "-t",
        "/tmp/run/annotate_vcf/annotated_vcf.annotated.vcf.gz",
    ]


def test_annotate_vcf_plans_named_outputs() -> None:
    node_class = _node_class("annotate_vcf")

    outputs = node_class.PLAN_OUTPUTS({"output_name": "sample annotations"}, "/tmp/run")

    assert [str(path) for path in outputs] == [
        "/tmp/run/annotate_vcf/sample_annotations.annotated.vcf.gz",
        "/tmp/run/annotate_vcf/sample_annotations.annotated.vcf.gz.tbi",
    ]


def test_annotate_vcf_rejects_missing_mode_inputs_and_invalid_mode() -> None:
    node_class = _node_class("annotate_vcf")

    assert node_class.VALIDATE_INPUTS({"vcf": "variants.vcf.gz", "mode": "vcfanno"}) == "vcfanno_config is required in vcfanno mode"
    assert (
        node_class.VALIDATE_INPUTS({"vcf": "variants.vcf.gz", "mode": "bcftools"})
        == "At least one annotation file is required in bcftools mode"
    )
    assert (
        node_class.VALIDATE_INPUTS({
            "vcf": "variants.vcf.gz",
            "mode": "bcftools",
            "annotation_files": "genes.bed.gz",
        })
        == "columns is required in bcftools mode"
    )
    assert (
        node_class.VALIDATE_INPUTS({
            "vcf": "variants.vcf.gz",
            "mode": "bcftools",
            "annotation_files": "genes.bed.gz\nclinvar.vcf.gz",
            "columns": "CHROM,FROM,TO,GENE",
        })
        == "columns must provide one newline-separated entry per bcftools annotation file"
    )
    assert (
        node_class.VALIDATE_INPUTS({
            "vcf": "variants.vcf.gz",
            "mode": "bcftools",
            "annotation_files": "genes.bed.gz\nclinvar.vcf.gz",
            "columns": "CHROM,FROM,TO,GENE\nID,INFO/CLNSIG",
            "header_lines": "genes.hdr",
        })
        == "header_lines must provide one newline-separated entry per bcftools annotation file, using '-' to skip a source"
    )
    assert node_class.VALIDATE_INPUTS({"vcf": "variants.vcf.gz", "mode": "custom"}) == "Unsupported annotation mode: custom"


def test_bedtools_closest_is_registered_for_frontend_discovery() -> None:
    registry = NodeRegistry.create_isolated()
    registry.load_builtin_nodes()
    info = registry.object_info()

    node_info = info["bedtools_closest"]
    assert node_info["display_name"] == "BEDTools Closest"
    assert node_info["category"] == "annotation"
    assert node_info["description"].startswith("Find the closest features")
    assert node_info["output"] == ["BED"]
    assert node_info["output_name"] == ["closest"]
    assert node_info["required_executables"] == ["bedtools"]
    assert node_info["required_conda_packages"] == ["bedtools"]
    assert "bedtools" in node_info["search_aliases"]
    assert "closest" in node_info["search_aliases"]
    assert "nearest gene" in node_info["search_aliases"]

    inputs = node_info["input"]
    assert set(inputs["required"]) == {"variants", "annotations"}
    assert set(inputs["optional"]) == {"mode", "distance", "strand", "sorted"}


def test_bedtools_closest_renders_distance_command() -> None:
    node_class = _node_class("bedtools_closest")

    cmd = node_class.render_command({
        "variants": "variants.bed",
        "annotations": "genes.bed",
        "mode": "all",
        "distance": True,
        "strand": "same",
        "sorted": True,
        "output": "/tmp/run/bedtools_closest",
    })

    assert cmd == [
        "bedtools",
        "closest",
        "-a",
        "variants.bed",
        "-b",
        "genes.bed",
        "-d",
        "-s",
        "-t",
        "all",
        "-sorted",
        ">",
        "/tmp/run/bedtools_closest/closest.bed",
    ]


def test_bedtools_closest_omits_default_optional_flags() -> None:
    node_class = _node_class("bedtools_closest")

    cmd = node_class.render_command({
        "variants": "variants.bed",
        "annotations": "genes.bed",
        "mode": "first",
        "distance": False,
        "strand": "ignore",
        "sorted": False,
        "output": "/tmp/run/bedtools_closest",
    })

    assert "-d" not in cmd
    assert "-s" not in cmd
    assert "-S" not in cmd
    assert "-sorted" not in cmd
    assert cmd == [
        "bedtools",
        "closest",
        "-a",
        "variants.bed",
        "-b",
        "genes.bed",
        "-t",
        "first",
        ">",
        "/tmp/run/bedtools_closest/closest.bed",
    ]


def test_bedtools_closest_plans_outputs() -> None:
    node_class = _node_class("bedtools_closest")

    outputs = node_class.PLAN_OUTPUTS({}, "/tmp/run")

    assert [str(path) for path in outputs] == ["/tmp/run/bedtools_closest/closest.bed"]


def test_bedtools_closest_environment_metadata_is_declared() -> None:
    assert EXECUTABLE_TO_CONDA_PACKAGE["bedtools"] == "bedtools"
    assert PACKAGE_MIN_VERSIONS["bedtools"] == ">=2.31.0"


def test_intersect_genes_is_registered_for_frontend_discovery() -> None:
    registry = NodeRegistry.create_isolated()
    registry.load_builtin_nodes()
    info = registry.object_info()

    node_info = info["intersect_genes"]
    assert node_info["display_name"] == "Intersect Genes"
    assert node_info["category"] == "annotation"
    assert node_info["description"].startswith("Intersect variant or gene lists")
    assert node_info["output"] == ["TSV", "JSON"]
    assert node_info["output_name"] == ["overlap", "enrichment"]
    assert node_info["requires_external_tools"] is False
    assert "gene set" in node_info["search_aliases"]
    assert "pathway overlap" in node_info["search_aliases"]
    assert "enrichment" in node_info["search_aliases"]

    inputs = node_info["input"]
    assert set(inputs["required"]) == {"input_genes", "database"}
    assert set(inputs["optional"]) == {"input_column", "database_format", "case_sensitive"}


@pytest.mark.asyncio
async def test_intersect_genes_writes_overlap_table_and_enrichment_json(tmp_path: Path) -> None:
    genes = tmp_path / "query_genes.txt"
    genes.write_text("BRCA1\nTP53\nEGFR\nBRCA1\n", encoding="utf-8")
    database = tmp_path / "gene_sets.json"
    database.write_text(
        json.dumps({
            "DNA Repair": ["BRCA1", "BRCA2", "RAD51"],
            "Cancer Drivers": ["TP53", "EGFR", "KRAS"],
            "Metabolism": ["G6PC", "ALDOB"],
        }),
        encoding="utf-8",
    )

    overlap_path, enrichment_path = await _node_class("intersect_genes")().run(
        input_genes=str(genes),
        database=str(database),
        database_format="json",
        case_sensitive=False,
        context=_context(tmp_path, "intersect"),
    )

    assert Path(overlap_path).name == "overlap.tsv"
    assert _read_table(overlap_path) == [
        {"gene": "BRCA1", "gene_set": "DNA Repair"},
        {"gene": "TP53", "gene_set": "Cancer Drivers"},
        {"gene": "EGFR", "gene_set": "Cancer Drivers"},
    ]

    enrichment = json.loads(Path(enrichment_path).read_text(encoding="utf-8"))
    assert enrichment["query_gene_count"] == 3
    assert enrichment["overlap_gene_count"] == 3
    assert enrichment["sets"] == [
        {"gene_set": "Cancer Drivers", "overlap_count": 2, "set_size": 3, "genes": ["TP53", "EGFR"]},
        {"gene_set": "DNA Repair", "overlap_count": 1, "set_size": 3, "genes": ["BRCA1"]},
    ]


@pytest.mark.asyncio
async def test_intersect_genes_reads_table_gene_sets(tmp_path: Path) -> None:
    genes = tmp_path / "variants.tsv"
    genes.write_text("gene\timpact\nbrca1\thigh\ntp53\tmoderate\n", encoding="utf-8")
    database = tmp_path / "pathways.tsv"
    database.write_text("gene_set\tgene\nDNA Repair\tBRCA1\nCancer Drivers\tTP53\n", encoding="utf-8")

    overlap_path, enrichment_path = await _node_class("intersect_genes")().run(
        input_genes=str(genes),
        database=str(database),
        input_column="gene",
        database_format="tsv",
        case_sensitive=False,
        context=_context(tmp_path, "intersect_table"),
    )

    assert _read_table(overlap_path) == [
        {"gene": "brca1", "gene_set": "DNA Repair"},
        {"gene": "tp53", "gene_set": "Cancer Drivers"},
    ]
    enrichment = json.loads(Path(enrichment_path).read_text(encoding="utf-8"))
    assert [item["gene_set"] for item in enrichment["sets"]] == ["Cancer Drivers", "DNA Repair"]


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


def test_pbsv_is_registered_for_frontend_discovery() -> None:
    registry = NodeRegistry.create_isolated()
    registry.load_builtin_nodes()
    info = registry.object_info()

    node_info = info["pbsv"]
    assert node_info["display_name"] == "PBSV Caller"
    assert node_info["category"] == "variant"
    assert node_info["description"].startswith("PacBio structural variant caller")
    assert node_info["output"] == ["VCF", "FILE"]
    assert node_info["output_name"] == ["sv_vcf", "svsig"]
    assert node_info["required_executables"] == ["pbsv"]
    assert node_info["required_conda_packages"] == ["pbsv"]
    assert "pacbio" in node_info["search_aliases"]
    assert "hifi sv" in node_info["search_aliases"]
    assert "structural variant" in node_info["search_aliases"]

    inputs = node_info["input"]
    assert set(inputs["required"]) == {"bam", "reference", "sample_name", "threads"}
    assert set(inputs["optional"]) == {"tandem_repeats", "ccs"}


def test_pbsv_renders_discover_and_call_command() -> None:
    node_class = _node_class("pbsv")

    cmd = node_class.render_command({
        "bam": "aligned.bam",
        "reference": "ref.fa",
        "sample_name": "HG002",
        "threads": 8,
        "tandem_repeats": "repeats.bed",
        "ccs": True,
        "output": "/tmp/run/pbsv",
    })

    assert cmd == [
        "pbsv",
        "discover",
        "aligned.bam",
        "/tmp/run/pbsv/HG002.svsig.gz",
        "--tandem-repeats",
        "repeats.bed",
        "&&",
        "pbsv",
        "call",
        "--ccs",
        "-j",
        "8",
        "ref.fa",
        "/tmp/run/pbsv/HG002.svsig.gz",
        "/tmp/run/pbsv/HG002.pbsv.vcf",
    ]


def test_pbsv_omits_disabled_optional_flags() -> None:
    node_class = _node_class("pbsv")

    cmd = node_class.render_command({
        "bam": "aligned.bam",
        "reference": "ref.fa",
        "sample_name": "sample",
        "threads": 2,
        "tandem_repeats": "",
        "ccs": False,
        "output": "/tmp/run/pbsv",
    })

    assert "--tandem-repeats" not in cmd
    assert "--ccs" not in cmd
    assert cmd == [
        "pbsv",
        "discover",
        "aligned.bam",
        "/tmp/run/pbsv/sample.svsig.gz",
        "&&",
        "pbsv",
        "call",
        "-j",
        "2",
        "ref.fa",
        "/tmp/run/pbsv/sample.svsig.gz",
        "/tmp/run/pbsv/sample.pbsv.vcf",
    ]


def test_pbsv_plans_outputs() -> None:
    node_class = _node_class("pbsv")

    outputs = node_class.PLAN_OUTPUTS({"sample_name": "HG002"}, "/tmp/run")

    assert [str(path) for path in outputs] == [
        "/tmp/run/pbsv/HG002.pbsv.vcf",
        "/tmp/run/pbsv/HG002.svsig.gz",
    ]


def test_pbsv_rejects_empty_sample_name() -> None:
    node_class = _node_class("pbsv")

    validation = node_class.VALIDATE_INPUTS({
        "bam": "aligned.bam",
        "reference": "ref.fa",
        "sample_name": "   ",
        "threads": 4,
    })

    assert validation == "Input 'sample_name' must not be empty"


def test_pbsv_environment_metadata_is_declared() -> None:
    assert EXECUTABLE_TO_CONDA_PACKAGE["pbsv"] == "pbsv"
    assert PACKAGE_MIN_VERSIONS["pbsv"] == ">=2.10.0"
