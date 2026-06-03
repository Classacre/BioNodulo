"""Genome annotation nodes for BioNodulo.

Provides nodes for prokaryotic genome annotation with Prokka and Bakta,
and functional annotation with eggNOG-mapper.
"""
from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Any

from bionodulo.nodes.base import BaseNode
from bionodulo.nodes.command_node import CommandNode


def _annotation_node_output_dir(node: BaseNode, context: Any) -> Path:
    base = Path(getattr(context, "node_dir", ".") if context else ".")
    out_dir = base / node.NODE_ID
    out_dir.mkdir(parents=True, exist_ok=True)
    return out_dir


def _normalise_gene(value: Any, case_sensitive: bool) -> str:
    gene = str(value or "").strip()
    return gene if case_sensitive else gene.upper()


def _read_gene_query(path: str | Path, column: str, case_sensitive: bool) -> list[tuple[str, str]]:
    raw = Path(path).read_text(encoding="utf-8").splitlines()
    if not raw:
        return []

    if column:
        with Path(path).open(newline="", encoding="utf-8") as fh:
            sample = fh.read(2048)
            fh.seek(0)
            dialect = csv.Sniffer().sniff(sample, delimiters=",	") if sample.strip() else csv.excel_tab
            reader = csv.DictReader(fh, dialect=dialect)
            if reader.fieldnames is None or column not in reader.fieldnames:
                raise ValueError(f"Column {column!r} not found in gene input")
            values = [row.get(column, "") for row in reader]
    else:
        values = raw

    genes: list[tuple[str, str]] = []
    seen: set[str] = set()
    for value in values:
        original = str(value or "").strip()
        normalised = _normalise_gene(original, case_sensitive)
        if normalised and normalised not in seen:
            seen.add(normalised)
            genes.append((original, normalised))
    return genes


def _read_gene_sets(path: str | Path, database_format: str, case_sensitive: bool) -> dict[str, list[tuple[str, str]]]:
    fmt = str(database_format or "auto").lower()
    source = Path(path)
    if fmt == "auto":
        fmt = "json" if source.suffix.lower() == ".json" else "tsv"

    if fmt == "json":
        payload = json.loads(source.read_text(encoding="utf-8"))
        if not isinstance(payload, dict):
            raise ValueError("JSON gene set database must be an object mapping set names to gene lists")
        gene_sets: dict[str, list[tuple[str, str]]] = {}
        for name, genes in payload.items():
            if not isinstance(genes, list):
                raise ValueError(f"Gene set {name!r} must be a list")
            gene_sets[str(name)] = [(str(gene).strip(), _normalise_gene(gene, case_sensitive)) for gene in genes]
        return gene_sets

    if fmt not in {"tsv", "csv"}:
        raise ValueError(f"Unsupported database format: {database_format}")

    delimiter = "," if fmt == "csv" else "	"
    gene_sets = {}
    with source.open(newline="", encoding="utf-8") as fh:
        reader = csv.DictReader(fh, delimiter=delimiter)
        if reader.fieldnames is None or not {"gene_set", "gene"}.issubset(reader.fieldnames):
            raise ValueError("Table gene set database must contain gene_set and gene columns")
        for row in reader:
            name = str(row.get("gene_set", "")).strip()
            gene = str(row.get("gene", "")).strip()
            if name and gene:
                gene_sets.setdefault(name, []).append((gene, _normalise_gene(gene, case_sensitive)))
    return gene_sets


class ProkkaNode(CommandNode):
    """Prokaryotic genome annotation with Prokka."""
    NODE_ID = "prokka"
    DISPLAY_NAME = "Prokka"
    REQUIRED_CONDA_PACKAGES = ['prokka']
    CATEGORY = "annotation"
    DESCRIPTION = "Rapid prokaryotic genome annotation"
    SEARCH_ALIASES = ["prokka", "annotate", "bacteria", "archaea", "genome"]
    RETURN_TYPES = ("GFF", "GBK", "FAA")
    RETURN_NAMES = ("gff", "genbank", "proteins")
    REQUIRED_EXECUTABLES = ["prokka"]
    DOCUMENTATION_URL = "https://github.com/tseemann/prokka"
    VERSION = "1.15.6"
    COMMAND = [
        "prokka",
        "--outdir", "{output}",
        "--prefix", "{inputs.prefix}",
        "--cpus", "{inputs.threads}",
        "--kingdom", "{inputs.kingdom}",
        "--force",
        "{inputs.assembly}",
    ]

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "assembly": ("ASSEMBLY", {"description": "Genome assembly FASTA"}),
                "threads": ("INT", {"default": 8, "min": 1, "max": 64, "display": "slider"}),
                "prefix": ("STRING", {"default": "genome"}),
            },
            "optional": {
                "kingdom": ("STRING", {"default": "Bacteria"}),
                "genus": ("STRING", {"default": ""}),
                "species": ("STRING", {"default": ""}),
                "strain": ("STRING", {"default": ""}),
                "gcode": ("INT", {"default": 11, "min": 1, "max": 33}),
            },
            "hidden": {
                "output": ("STRING", {}),
            },
        }

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        cmd = [
            "prokka",
            "--outdir", str(inputs.get("output", ".")),
            "--prefix", str(inputs.get("prefix", "genome")),
            "--cpus", str(inputs.get("threads", 8)),
            "--kingdom", str(inputs.get("kingdom", "Bacteria")),
            "--force",
            str(inputs.get("assembly", "")),
        ]
        if inputs.get("genus"):
            cmd.extend(["--genus", str(inputs["genus"])])
        if inputs.get("species"):
            cmd.extend(["--species", str(inputs["species"])])
        if inputs.get("strain"):
            cmd.extend(["--strain", str(inputs["strain"])])
        if inputs.get("gcode") is not None:
            cmd.extend(["--gcode", str(inputs["gcode"])])
        return cmd

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list:
        prefix = inputs.get("prefix", "genome")
        od = Path(output_dir)
        return [
            od / cls.NODE_ID / f"{prefix}.gff",
            od / cls.NODE_ID / f"{prefix}.gbk",
            od / cls.NODE_ID / f"{prefix}.faa",
        ]

    async def run(self, **kwargs: Any) -> Any:
        """Run Prokka and copy outputs to planned paths."""
        result = await super().run(**kwargs)
        import shutil
        from pathlib import Path
        node_out = Path(kwargs["output_dir"])
        base_output_dir = node_out.parent
        outputs = self.__class__.PLAN_OUTPUTS(kwargs, base_output_dir)
        prefix = kwargs.get("prefix", "genome")
        files = [f"{prefix}.gff", f"{prefix}.gbk", f"{prefix}.faa"]
        for i, fname in enumerate(files):
            if i < len(outputs):
                actual = node_out / fname
                if actual.exists():
                    outputs[i].parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(str(actual), str(outputs[i]))
        return result


class BaktaNode(CommandNode):
    """Prokaryotic annotation with Bakta (Prokka successor)."""
    NODE_ID = "bakta"
    DISPLAY_NAME = "Bakta"
    CATEGORY = "annotation"
    DESCRIPTION = "Rapid & standardized annotation of bacterial genomes"
    SEARCH_ALIASES = ["bakta", "annotate", "bacteria", "annotation"]
    RETURN_TYPES = ("GFF3", "FAA")
    RETURN_NAMES = ("gff", "proteins")
    REQUIRED_EXECUTABLES = ["bakta"]
    REQUIRED_CONDA_PACKAGES = ['bakta']
    DOCUMENTATION_URL = "https://github.com/oschwengers/bakta"
    VERSION = "1.12.0"
    COMMAND = [
        "bakta",
        "--output", "{output}",
        "--prefix", "{inputs.prefix}",
        "--threads", "{inputs.threads}",
        "{inputs.assembly}",
    ]

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "assembly": ("ASSEMBLY", {"description": "Genome assembly FASTA"}),
                "threads": ("INT", {"default": 8, "min": 1, "max": 64, "display": "slider"}),
                "prefix": ("STRING", {"default": "genome"}),
            },
            "optional": {
                "db": ("DIRECTORY", {"description": "Bakta DB path"}),
                "translation_table": ("INT", {"default": 11}),
            },
            "hidden": {
                "output": ("STRING", {}),
            },
        }

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        cmd = [
            "bakta",
            "--output", str(inputs.get("output", ".")),
            "--prefix", str(inputs.get("prefix", "genome")),
            "--threads", str(inputs.get("threads", 8)),
            str(inputs.get("assembly", "")),
        ]
        if inputs.get("db"):
            cmd.extend(["--db", str(inputs["db"])])
        return cmd

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list:
        prefix = inputs.get("prefix", "genome")
        od = Path(output_dir)
        return [
            od / cls.NODE_ID / f"{prefix}.gff3",
            od / cls.NODE_ID / f"{prefix}.faa",
        ]

    async def run(self, **kwargs: Any) -> Any:
        """Run Bakta and copy outputs to planned paths."""
        result = await super().run(**kwargs)
        import shutil
        from pathlib import Path
        node_out = Path(kwargs["output_dir"])
        base_output_dir = node_out.parent
        outputs = self.__class__.PLAN_OUTPUTS(kwargs, base_output_dir)
        prefix = kwargs.get("prefix", "genome")
        files = [f"{prefix}.gff3", f"{prefix}.faa"]
        for i, fname in enumerate(files):
            if i < len(outputs):
                actual = node_out / fname
                if actual.exists():
                    outputs[i].parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(str(actual), str(outputs[i]))
        return result


class EggNOGMapperNode(CommandNode):
    """Functional annotation with eggNOG-mapper."""
    NODE_ID = "eggnog_mapper"
    DISPLAY_NAME = "eggNOG-mapper"
    CATEGORY = "annotation"
    DESCRIPTION = "Fast genome-wide functional annotation via orthology"
    SEARCH_ALIASES = ["eggnog", "emapper", "functional", "cog", "go"]
    RETURN_TYPES = ("TSV",)
    RETURN_NAMES = ("annotations",)
    REQUIRED_EXECUTABLES = ["emapper.py"]
    REQUIRED_CONDA_PACKAGES = ['eggnog-mapper']
    DOCUMENTATION_URL = "https://github.com/eggnogdb/eggnog-mapper"
    VERSION = "2.1.14"
    COMMAND = [
        "emapper.py",
        "-i", "{inputs.proteins}",
        "--output", "{inputs.prefix}",
        "--output_dir", "{output}",
        "-m", "{inputs.mode}",
        "--cpu", "{inputs.threads}",
    ]

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "proteins": ("FASTA", {"description": "Protein FASTA file (.faa)"}),
                "threads": ("INT", {"default": 8, "min": 1, "max": 64, "display": "slider"}),
                "prefix": ("STRING", {"default": "annotations"}),
            },
            "optional": {
                "mode": ("STRING", {"default": "diamond", "description": "Search mode: diamond, mmseqs, or hmmer"}),
                "data_dir": ("DIRECTORY", {"description": "eggNOG data directory"}),
                "itype": ("STRING", {"default": "proteins", "options": ["proteins", "CDS", "genome", "metagenome"], "label": "Input Type", "advanced": True}),
            },
            "hidden": {
                "output": ("STRING", {}),
            },
        }

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        cmd = [
            "emapper.py",
            "-i", str(inputs.get("proteins", "")),
            "--output", str(inputs.get("prefix", "annotations")),
            "--output_dir", str(inputs.get("output", ".")),
            "-m", str(inputs.get("mode", "diamond")),
            "--cpu", str(inputs.get("threads", 8)),
        ]
        if inputs.get("data_dir"):
            cmd.extend(["--data_dir", str(inputs["data_dir"])])
        if inputs.get("itype"):
            cmd.extend(["--itype", str(inputs["itype"])])
        return cmd

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list:
        prefix = inputs.get("prefix", "annotations")
        od = Path(output_dir)
        return [od / cls.NODE_ID / f"{prefix}.annotations.tsv"]

    async def run(self, **kwargs: Any) -> Any:
        """Run eggNOG-mapper and copy annotations to planned path."""
        result = await super().run(**kwargs)
        import shutil
        from pathlib import Path
        node_out = Path(kwargs["output_dir"])
        base_output_dir = node_out.parent
        outputs = self.__class__.PLAN_OUTPUTS(kwargs, base_output_dir)
        prefix = kwargs.get("prefix", "annotations")
        if outputs:
            outputs[0].parent.mkdir(parents=True, exist_ok=True)
            actual = node_out / f"{prefix}.annotations"
            if actual.exists():
                shutil.copy2(str(actual), str(outputs[0]))
        return result


class SnpEffNode(CommandNode):
    """Annotate variants and predict effects with SnpEff."""
    NODE_ID = "snpeff"
    DISPLAY_NAME = "SnpEff"
    CATEGORY = "annotation"
    DESCRIPTION = "Fast variant annotation: missense, nonsense, frameshift, splice site. Supports many genomes."
    SEARCH_ALIASES = ["snpeff", "variant annotation", "effect prediction", "functional effect"]
    RETURN_TYPES = ("VCF", "HTML_REPORT")
    RETURN_NAMES = ("annotated_vcf", "summary_report")
    REQUIRED_EXECUTABLES = ["snpEff"]
    REQUIRED_CONDA_PACKAGES = ["snpeff"]
    DOCUMENTATION_URL = "https://pcingola.github.io/SnpEff/"
    VERSION = "5.2"
    SHELL = True

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        out_dir = inputs.get("output", ".")
        genome = str(inputs.get("genome", "GRCh38"))
        cmd = [
            "java",
            "-jar",
            f"-Xmx{inputs.get('memory', 4)}g",
            "snpEff.jar",
            "-v",
            "-stats",
            f"{out_dir}/summary_report.html",
        ]
        if inputs.get("canonical"):
            cmd.append("-canon")
        if inputs.get("no_upstream"):
            cmd.append("-no-upstream")
        if inputs.get("no_downstream"):
            cmd.append("-no-downstream")
        if inputs.get("no_intergenic"):
            cmd.append("-no-intergenic")
        cmd.extend([genome, str(inputs.get("vcf", "")), ">", f"{out_dir}/annotated_vcf.vcf"])
        return cmd

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        node_out = Path(output_dir) / cls.NODE_ID
        node_out.mkdir(parents=True, exist_ok=True)
        return [node_out / "annotated_vcf.vcf", node_out / "summary_report.html"]

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "vcf": ("VCF_GZ", {"description": "VCF to annotate"}),
                "genome": ("STRING", {"default": "GRCh38", "description": "SnpEff genome (GRCh38, GRCh37, GRCm39)"}),
                "memory": ("INT", {"default": 4, "min": 1, "max": 128, "label": "Max Memory (GB)"}),
            },
            "optional": {
                "canonical": ("BOOLEAN", {"default": False, "description": "Canonical transcripts only"}),
                "no_upstream": ("BOOLEAN", {"default": False}),
                "no_downstream": ("BOOLEAN", {"default": False}),
                "no_intergenic": ("BOOLEAN", {"default": False}),
            },
            "hidden": {
                "output": ("STRING", {}),
            },
        }


class VEPNode(CommandNode):
    """Annotate variants with Ensembl Variant Effect Predictor."""
    NODE_ID = "vep"
    DISPLAY_NAME = "VEP"
    CATEGORY = "annotation"
    DESCRIPTION = "Ensembl Variant Effect Predictor. Comprehensive functional annotation with frequencies, clinical significance."
    SEARCH_ALIASES = ["vep", "variant effect predictor", "ensembl", "variant annotation", "clinvar"]
    RETURN_TYPES = ("VCF", "HTML_REPORT")
    RETURN_NAMES = ("annotated_vcf", "vep_report")
    REQUIRED_EXECUTABLES = ["vep"]
    REQUIRED_CONDA_PACKAGES = ["ensembl-vep"]
    DOCUMENTATION_URL = "https://www.ensembl.org/info/docs/tools/vep/"
    VERSION = "113"
    SHELL = True

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        out_dir = inputs.get("output", ".")
        vcf = str(inputs.get("vcf", ""))
        fmt = str(inputs.get("output_format", "vcf"))
        cmd = [
            "vep",
            "-i",
            vcf,
            "-o",
            f"{out_dir}/annotated_vcf.{fmt}",
            "--format",
            "vcf",
            f"--{fmt}",
            "--fork",
            str(inputs.get("threads", 4)),
            "--assembly",
            str(inputs.get("assembly", "GRCh38")),
            "--cache",
            "--dir_cache",
            str(inputs.get("cache_dir", "~/.vep")),
        ]
        if inputs.get("everything"):
            cmd.append("--everything")
        if inputs.get("symbol"):
            cmd.append("--symbol")
        if inputs.get("af"):
            cmd.append("--af")
        if inputs.get("max_af"):
            cmd.append("--max_af")
        if inputs.get("sift"):
            cmd.extend(["--sift", str(inputs["sift"])])
        if inputs.get("polyphen"):
            cmd.extend(["--polyphen", str(inputs["polyphen"])])
        if inputs.get("clinvar"):
            cmd.extend(["--custom", f"{inputs['clinvar']},ClinVar,vcf,exact,0,CLNSIG"])
        cmd.extend(["--stats_file", f"{out_dir}/vep_report.html"])
        return cmd

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        node_out = Path(output_dir) / cls.NODE_ID
        node_out.mkdir(parents=True, exist_ok=True)
        fmt = str(inputs.get("output_format", "vcf"))
        return [node_out / f"annotated_vcf.{fmt}", node_out / "vep_report.html"]

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "vcf": ("VCF_GZ", {"description": "Input VCF"}),
                "assembly": ("STRING", {"default": "GRCh38"}),
                "cache_dir": ("DIRECTORY", {"description": "VEP cache (~10-20GB)"}),
                "threads": ("INT", {"default": 4, "min": 1, "max": 64}),
            },
            "optional": {
                "everything": ("BOOLEAN", {"default": True}),
                "symbol": ("BOOLEAN", {"default": True}),
                "af": ("BOOLEAN", {"default": True}),
                "max_af": ("BOOLEAN", {"default": True}),
                "sift": ("STRING", {"default": "b", "options": ["b", "s", "p"]}),
                "polyphen": ("STRING", {"default": "b", "options": ["b", "s", "p"]}),
                "clinvar": ("VCF_GZ", {"description": "ClinVar VCF"}),
                "output_format": ("STRING", {"default": "vcf", "options": ["vcf", "tab"]}),
            },
            "hidden": {
                "output": ("STRING", {}),
            },
        }


class VEPAnnotateNode(VEPNode):
    """Compatibility wrapper for the VEP annotation roadmap node ID."""

    NODE_ID = "vep_annotate"
    DISPLAY_NAME = "VEP Annotate"
    DESCRIPTION = "Annotate variants with Ensembl Variant Effect Predictor."
    SEARCH_ALIASES = [
        "vep annotate",
        "vep",
        "variant effect predictor",
        "ensembl",
        "variant annotation",
        "clinvar",
    ]


class ANNOVARNode(CommandNode):
    """Annotate variants with ANNOVAR."""
    NODE_ID = "annovar"
    DISPLAY_NAME = "ANNOVAR"
    CATEGORY = "annotation"
    DESCRIPTION = "Comprehensive variant annotation: gene-based, region-based, filter-based. Clinical interpretation."
    SEARCH_ALIASES = ["annovar", "variant annotation", "clinical", "clinvar", "gnomad"]
    RETURN_TYPES = ("CSV", "CSV")
    RETURN_NAMES = ("variant_function", "exonic_variant_function")
    REQUIRED_EXECUTABLES = ["table_annovar.pl", "convert2annovar.pl"]
    REQUIRED_CONDA_PACKAGES = ["annovar"]
    DOCUMENTATION_URL = "https://annovar.openbioinformatics.org/"
    VERSION = "2020-06-08"
    SHELL = True
    EXPERIMENTAL = True

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        out_dir = inputs.get("output", ".")
        vcf = str(inputs.get("vcf", ""))
        humandb_dir = str(inputs.get("humandb_dir", ""))
        buildver = str(inputs.get("buildver", "hg38"))
        protocol = str(inputs.get("protocol", "refGene,cytoBand,gnomad40_genome,clinvar_20220320"))
        operation = str(inputs.get("operation", "g,r,f,f"))
        avinput = f"{out_dir}/input.avinput"

        convert = [
            "convert2annovar.pl",
            "-format",
            "vcf4",
            "-withzyg",
            "-includeinfo",
            vcf,
            ">",
            avinput,
        ]
        annotate = [
            "&&",
            "table_annovar.pl",
            avinput,
            humandb_dir,
            "-buildver",
            buildver,
            "-out",
            f"{out_dir}/annovar",
            "-remove",
            "-protocol",
            protocol,
            "-operation",
            operation,
            "-nastring",
            ".",
            "-vcfinput",
            "-polish",
        ]
        return convert + annotate

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        node_out = Path(output_dir) / cls.NODE_ID
        node_out.mkdir(parents=True, exist_ok=True)
        return [node_out / "variant_function.csv", node_out / "exonic_variant_function.csv"]

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "vcf": ("VCF_GZ", {"description": "Input VCF"}),
                "humandb_dir": ("DIRECTORY", {"description": "ANNOVAR humandb"}),
                "buildver": ("STRING", {"default": "hg38", "options": ["hg38", "hg19"]}),
                "protocol": ("STRING", {"default": "refGene,cytoBand,gnomad40_genome,clinvar_20220320"}),
                "operation": ("STRING", {"default": "g,r,f,f", "description": "g=gene,r=region,f=filter"}),
            },
            "optional": {},
            "hidden": {
                "output": ("STRING", {}),
            },
        }


class FuncotateTableNode(CommandNode):
    """Annotate cancer variants with GATK Funcotator."""
    NODE_ID = "funcotate_table"
    DISPLAY_NAME = "Funcotate Table"
    CATEGORY = "annotation"
    DESCRIPTION = "Oncotator-style functional annotation for cancer variants using GATK Funcotator."
    SEARCH_ALIASES = ["funcotator", "funcotate", "cancer variants", "oncotator", "somatic annotation"]
    RETURN_TYPES = ("FILE", "FILE")
    RETURN_NAMES = ("annotated", "summary")
    REQUIRED_EXECUTABLES = ["gatk"]
    REQUIRED_CONDA_PACKAGES = ["gatk4"]
    DOCUMENTATION_URL = "https://gatk.broadinstitute.org/hc/en-us/articles/360037224432-Funcotator"
    VERSION = "4.6.2.0"
    SHELL = True

    @classmethod
    def _output_filename(cls, output_format: str) -> str:
        return "annotated.vcf" if output_format.upper() == "VCF" else "annotated.maf"

    @staticmethod
    def _split_annotations(value: Any) -> list[str]:
        return [item.strip() for item in str(value or "").split(",") if item.strip()]

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        out_dir = inputs.get("output", ".")
        output_format = str(inputs.get("output_format", "MAF")).upper()
        annotated = f"{out_dir}/{cls._output_filename(output_format)}"
        summary = f"{out_dir}/summary.tsv"
        vcf = str(inputs.get("vcf", ""))
        ref_version = str(inputs.get("ref_version", "hg38"))

        cmd = [
            "gatk",
            "Funcotator",
            "-R",
            str(inputs.get("reference", "")),
            "-V",
            vcf,
            "-O",
            annotated,
            "--output-file-format",
            output_format,
            "--data-sources-path",
            str(inputs.get("data_sources", "")),
            "--ref-version",
            ref_version,
        ]
        if inputs.get("transcript_selection_mode"):
            cmd.extend(["--transcript-selection-mode", str(inputs["transcript_selection_mode"])])
        for annotation in cls._split_annotations(inputs.get("annotation_defaults")):
            cmd.extend(["--annotation-default", annotation])
        for annotation in cls._split_annotations(inputs.get("annotation_overrides")):
            cmd.extend(["--annotation-override", annotation])
        if inputs.get("intervals"):
            cmd.extend(["-L", str(inputs["intervals"])])

        summary_payload = (
            f"'tool\\tgatk Funcotator\\n"
            f"input\\t{vcf}\\n"
            f"output\\t{annotated}\\n"
            f"format\\t{output_format}\\n"
            f"ref_version\\t{ref_version}\\n'"
        )
        cmd.extend(["&&", "printf", summary_payload, ">", summary])
        return cmd

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        node_out = Path(output_dir) / cls.NODE_ID
        node_out.mkdir(parents=True, exist_ok=True)
        output_format = str(inputs.get("output_format", "MAF")).upper()
        return [node_out / cls._output_filename(output_format), node_out / "summary.tsv"]

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "vcf": ("VCF_GZ", {"description": "Input VCF to annotate"}),
                "reference": ("FASTA", {"description": "Reference FASTA used for the VCF"}),
                "data_sources": ("DIRECTORY", {"description": "Funcotator data sources directory"}),
                "ref_version": ("STRING", {"default": "hg38", "options": ["hg38", "hg19"]}),
            },
            "optional": {
                "output_format": ("STRING", {"default": "MAF", "options": ["MAF", "VCF"]}),
                "transcript_selection_mode": (
                    "STRING",
                    {
                        "default": "",
                        "options": ["", "CANONICAL", "BEST_EFFECT", "ALL"],
                        "advanced": True,
                    },
                ),
                "annotation_defaults": (
                    "STRING",
                    {"default": "", "description": "Comma-separated KEY:VALUE defaults", "advanced": True},
                ),
                "annotation_overrides": (
                    "STRING",
                    {"default": "", "description": "Comma-separated KEY:VALUE overrides", "advanced": True},
                ),
                "intervals": ("FILE", {"default": "", "description": "Optional intervals to annotate", "advanced": True}),
            },
            "hidden": {
                "output": ("STRING", {}),
            },
        }


class BcftoolsAnnotateNode(CommandNode):
    """Annotate VCF records from BED, VCF, or TSV annotation files."""
    NODE_ID = "bcftools_annotate"
    DISPLAY_NAME = "bcftools Annotate"
    CATEGORY = "annotation"
    DESCRIPTION = "Annotate VCF with custom annotations from BED, VCF, or TSV files."
    SEARCH_ALIASES = ["bcftools", "annotate", "vcf annotation", "custom annotation", "bed annotation"]
    RETURN_TYPES = ("VCF_GZ",)
    RETURN_NAMES = ("annotated_vcf",)
    REQUIRED_EXECUTABLES = ["bcftools"]
    REQUIRED_CONDA_PACKAGES = ["bcftools"]
    DOCUMENTATION_URL = "https://samtools.github.io/bcftools/bcftools.html#annotate"
    VERSION = "1.15"
    SHELL = True

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        out_dir = inputs.get("output", ".")
        out_vcf = f"{out_dir}/annotated_vcf.vcf.gz"
        cmd = [
            "bcftools",
            "annotate",
            "-a",
            str(inputs.get("annotations", "")),
        ]
        if inputs.get("columns"):
            cmd.extend(["-c", str(inputs["columns"])])
        if inputs.get("header_lines"):
            cmd.extend(["-h", str(inputs["header_lines"])])
        if inputs.get("threads"):
            cmd.extend(["--threads", str(inputs["threads"])])
        cmd.extend([
            "-Oz",
            "-o",
            out_vcf,
            str(inputs.get("vcf", "")),
            "&&",
            "bcftools",
            "index",
            "-t",
            out_vcf,
        ])
        return cmd

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        node_out = Path(output_dir) / cls.NODE_ID
        node_out.mkdir(parents=True, exist_ok=True)
        return [node_out / "annotated_vcf.vcf.gz"]

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "vcf": ("VCF_GZ", {"description": "Input bgzipped VCF"}),
                "annotations": ("FILE", {"description": "BED, VCF, or TSV annotations"}),
            },
            "optional": {
                "columns": ("STRING", {"default": "", "description": "Annotation columns, e.g. CHROM,FROM,TO,GENE"}),
                "header_lines": ("FILE", {"description": "Header lines to add to the output VCF"}),
                "threads": ("INT", {"default": 4, "min": 0, "max": 64}),
            },
            "hidden": {
                "output": ("STRING", {}),
            },
        }


class BEDToolsClosestNode(CommandNode):
    """Find nearest annotation features for variant or region intervals."""
    NODE_ID = "bedtools_closest"
    DISPLAY_NAME = "BEDTools Closest"
    CATEGORY = "annotation"
    DESCRIPTION = "Find the closest features in a BED file to variants or regions."
    SEARCH_ALIASES = ["bedtools", "closest", "nearest gene", "nearest feature", "bed annotation"]
    RETURN_TYPES = ("BED",)
    RETURN_NAMES = ("closest",)
    REQUIRED_EXECUTABLES = ["bedtools"]
    REQUIRED_CONDA_PACKAGES = ["bedtools"]
    DOCUMENTATION_URL = "https://bedtools.readthedocs.io/en/latest/content/tools/closest.html"
    VERSION = "2.31.0"
    SHELL = True

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        out_dir = inputs.get("output", ".")
        cmd = [
            "bedtools",
            "closest",
            "-a",
            str(inputs.get("variants", "")),
            "-b",
            str(inputs.get("annotations", "")),
        ]
        if inputs.get("distance"):
            cmd.append("-d")
        strand = str(inputs.get("strand", "ignore"))
        if strand == "same":
            cmd.append("-s")
        elif strand == "opposite":
            cmd.append("-S")
        cmd.extend(["-t", str(inputs.get("mode", "first"))])
        if inputs.get("sorted"):
            cmd.append("-sorted")
        cmd.extend([">", f"{out_dir}/closest.bed"])
        return cmd

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        node_out = Path(output_dir) / cls.NODE_ID
        node_out.mkdir(parents=True, exist_ok=True)
        return [node_out / "closest.bed"]

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "variants": ("BED", {"description": "Variants or regions in BED format"}),
                "annotations": ("BED", {"description": "Annotation features in BED format"}),
            },
            "optional": {
                "mode": ("STRING", {"default": "first", "options": ["first", "last", "all"]}),
                "distance": ("BOOLEAN", {"default": True, "description": "Include distance to closest feature"}),
                "strand": ("STRING", {"default": "ignore", "options": ["ignore", "same", "opposite"]}),
                "sorted": ("BOOLEAN", {"default": False, "advanced": True}),
            },
            "hidden": {
                "output": ("STRING", {}),
            },
        }


class IntersectGenesNode(BaseNode):
    """Intersect a query gene list with pathway or gene set databases."""
    NODE_ID = "intersect_genes"
    DISPLAY_NAME = "Intersect Genes"
    CATEGORY = "annotation"
    DESCRIPTION = "Intersect variant or gene lists with pathway or gene set databases."
    SEARCH_ALIASES = ["gene set", "pathway overlap", "enrichment", "intersect", "genes"]
    RETURN_TYPES = ("TSV", "JSON")
    RETURN_NAMES = ("overlap", "enrichment")
    REQUIRES_EXTERNAL_TOOLS = False
    DOCUMENTATION_URL = "https://en.wikipedia.org/wiki/Gene_set_enrichment_analysis"
    VERSION = "1.0.0"

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "input_genes": ("FILE", {"description": "Gene list or table containing query genes"}),
                "database": ("FILE", {"description": "Gene set database as JSON or gene_set/gene table"}),
            },
            "optional": {
                "input_column": ("STRING", {"default": "", "description": "Column name when input_genes is a table"}),
                "database_format": ("STRING", {"default": "auto", "options": ["auto", "json", "tsv", "csv"]}),
                "case_sensitive": ("BOOLEAN", {"default": False}),
            },
            "hidden": {},
        }

    async def run(self, **kwargs: Any) -> tuple[str, str]:
        context = kwargs.pop("context", None)
        case_sensitive = bool(kwargs.get("case_sensitive", False))
        query_genes = _read_gene_query(kwargs["input_genes"], str(kwargs.get("input_column", "")), case_sensitive)
        gene_sets = _read_gene_sets(kwargs["database"], str(kwargs.get("database_format", "auto")), case_sensitive)
        query_index = {normalised: original for original, normalised in query_genes}

        overlap_rows: list[dict[str, str]] = []
        enrichment_sets: list[dict[str, Any]] = []
        for gene_set, genes in gene_sets.items():
            matched: list[str] = []
            seen: set[str] = set()
            for _source_gene, normalised in genes:
                if normalised in query_index and normalised not in seen:
                    seen.add(normalised)
                    matched.append(query_index[normalised])
            for gene in matched:
                overlap_rows.append({"gene": gene, "gene_set": gene_set})
            if matched:
                enrichment_sets.append({
                    "gene_set": gene_set,
                    "overlap_count": len(matched),
                    "set_size": len({normalised for _gene, normalised in genes if normalised}),
                    "genes": matched,
                })

        enrichment_sets.sort(key=lambda item: (-item["overlap_count"], item["gene_set"]))
        out_dir = _annotation_node_output_dir(self, context)
        overlap_path = out_dir / "overlap.tsv"
        enrichment_path = out_dir / "enrichment.json"

        with overlap_path.open("w", newline="", encoding="utf-8") as fh:
            writer = csv.DictWriter(fh, fieldnames=["gene", "gene_set"], delimiter="	")
            writer.writeheader()
            writer.writerows(overlap_rows)

        enrichment_path.write_text(
            json.dumps({
                "query_gene_count": len(query_genes),
                "overlap_gene_count": len({row["gene"] for row in overlap_rows}),
                "sets": enrichment_sets,
            }, indent=2, ensure_ascii=True) + "\n",
            encoding="utf-8",
        )
        return str(overlap_path), str(enrichment_path)


class InterProScanNode(CommandNode):
    """Scan protein sequences for domains and functional annotations."""
    NODE_ID = "interproscan"
    DISPLAY_NAME = "InterProScan"
    CATEGORY = "annotation"
    DESCRIPTION = "Scan proteins for domains, families, functional sites (Pfam, InterPro, GO, KEGG)."
    SEARCH_ALIASES = ["interproscan", "protein domain", "pfam", "go annotation", "interpro"]
    RETURN_TYPES = ("TSV", "JSON", "GFF")
    RETURN_NAMES = ("ipr_matches", "ipr_json", "ipr_gff")
    REQUIRED_EXECUTABLES = ["interproscan.sh"]
    REQUIRED_CONDA_PACKAGES = ["interproscan"]
    DOCUMENTATION_URL = "https://www.ebi.ac.uk/interpro/"
    VERSION = "5.71-102.0"
    SHELL = True
    EXPERIMENTAL = True

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        out_dir = inputs.get("output", ".")
        cmd = [
            "interproscan.sh",
            "-i",
            str(inputs.get("fasta", "")),
            "-b",
            f"{out_dir}/ipr",
            "-f",
            "TSV,JSON,GFF3",
            "-cpu",
            str(inputs.get("threads", 4)),
        ]
        if inputs.get("applications"):
            cmd.extend(["-appl", str(inputs["applications"])])
        if inputs.get("goterms", True):
            cmd.append("-goterms")
        if inputs.get("iprlookup", True):
            cmd.append("-iprlookup")
        if inputs.get("pathways", True):
            cmd.append("-pa")
        return cmd

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        node_out = Path(output_dir) / cls.NODE_ID
        node_out.mkdir(parents=True, exist_ok=True)
        return [node_out / "ipr.tsv", node_out / "ipr.json", node_out / "ipr.gff3"]

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "fasta": ("FASTA", {"description": "Protein FASTA"}),
                "threads": ("INT", {"default": 4, "min": 1, "max": 64}),
            },
            "optional": {
                "applications": ("STRING", {"default": "", "description": "e.g., Pfam,Gene3D,PANTHER"}),
                "goterms": ("BOOLEAN", {"default": True}),
                "iprlookup": ("BOOLEAN", {"default": True}),
                "pathways": ("BOOLEAN", {"default": True}),
            },
            "hidden": {
                "output": ("STRING", {}),
            },
        }
