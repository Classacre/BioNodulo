from __future__ import annotations

from bionodulo.environments.constants import EXECUTABLE_TO_CONDA_PACKAGE, PACKAGE_MIN_VERSIONS
from bionodulo.nodes.builtin.annotation import FuncotateTableNode
from bionodulo.nodes.registry import NodeRegistry


def _node_class(node_id: str) -> type:
    registry = NodeRegistry.create_isolated()
    registry.load_builtin_nodes()
    node_class = registry.get(node_id)
    assert node_class is not None, f"{node_id} is not registered"
    return node_class


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
    assert PACKAGE_MIN_VERSIONS["gatk4"] == "4.6.2.0"


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
    assert PACKAGE_MIN_VERSIONS["bcftools"] == "1.24"


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
