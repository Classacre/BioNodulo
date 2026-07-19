"""Genome annotation nodes for BioNodulo.

Provides nodes for prokaryotic genome annotation with Prokka and Bakta,
and functional annotation with eggNOG-mapper.
"""
from __future__ import annotations

import csv
import json
import re
from pathlib import Path
from typing import Any

from bionodulo.nodes.base import BaseNode
from bionodulo.nodes.command_node import CommandNode, _shell_join


DOI_URL = "https://doi.org/"
BCFTOOLS_CITATION_DOIS = ["10.1093/gigascience/giab008", "10.1093/bioinformatics/btp352"]
BCFTOOLS_CITATION_URLS = [f"{DOI_URL}{doi}" for doi in BCFTOOLS_CITATION_DOIS]
BCFTOOLS_CITATION_TEXT = (
    "Twelve years of SAMtools and BCFtools; "
    "The Sequence Alignment/Map format and SAMtools."
)


def _annotation_node_output_dir(node: BaseNode, context: Any) -> Path:
    base = Path(getattr(context, "node_dir", ".") if context else ".")
    out_dir = base / node.NODE_ID
    out_dir.mkdir(parents=True, exist_ok=True)
    return out_dir


def _safe_output_stem(value: str, default: str) -> str:
    stem = "_".join(str(value or "").strip().split())
    stem = "".join(char if char.isalnum() or char in "._-" else "_" for char in stem)
    stem = stem.strip("._-")
    return stem or default


def _split_annotation_files(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, (list, tuple)):
        return [str(item).strip() for item in value if str(item).strip()]
    return [part.strip() for part in re.split(r"[\n,]+", str(value)) if part.strip()]


def _split_annotation_lines(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, (list, tuple)):
        return [str(item).strip() for item in value if str(item).strip()]
    return [line.strip() for line in str(value).splitlines() if line.strip()]


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
    """Galaxy-aligned bacterial genome annotation with Bakta."""

    NODE_ID = "bakta"
    DISPLAY_NAME = "Bakta"
    CATEGORY = "annotation"
    DESCRIPTION = "Rapid and standardized annotation of bacterial genomes, MAGs and plasmids."
    SEARCH_ALIASES = [
        "BioNodulo builtin",
        "Bakta",
        "bakta",
        "bacterial genome annotation",
        "MAGs",
        "plasmids",
        "AMRFinderPlus",
        "GFF3",
    ]
    RETURN_TYPES = (
        "TSV",
        "GFF3",
        "GBFF",
        "EMBL",
        "FASTA",
        "FASTA",
        "FASTA",
        "TSV",
        "FASTA",
        "TXT",
        "JSON",
        "SVG",
        "TXT",
    )
    RETURN_NAMES = (
        "annotation_tsv",
        "annotation_gff3",
        "annotation_gbff",
        "annotation_embl",
        "annotation_fna",
        "annotation_ffn",
        "annotation_faa",
        "hypotheticals_tsv",
        "hypotheticals_faa",
        "summary_txt",
        "annotation_json",
        "annotation_plot",
        "logfile",
    )
    REQUIRED_EXECUTABLES = ["bakta", "ln", "mkdir", "cp"]
    REQUIRED_CONDA_PACKAGES = ["bakta"]
    DOCUMENTATION_URL = "https://github.com/oschwengers/bakta"
    CITATION_DOIS = ["10.1099/mgen.0.000685"]
    CITATION_URLS = ["https://doi.org/10.1099/mgen.0.000685"]
    CITATION_TEXT = "Bakta: rapid and standardized annotation of bacterial genomes via alignment-free sequence identification."
    VERSION = "1.9.4+galaxy1"
    SHELL = True

    SKIP_ANALYSIS_OPTIONS = [
        "--skip-trna",
        "--skip-tmrna",
        "--skip-rrna",
        "--skip-ncrna",
        "--skip-ncrna-region",
        "--skip-crispr",
        "--skip-cds",
        "--skip-pseudo",
        "--skip-sorf",
        "--skip-gap",
        "--skip-ori",
        "--skip-plot",
    ]
    OUTPUT_SELECTION_OPTIONS = [
        "file_tsv",
        "file_gff3",
        "file_gbff",
        "file_embl",
        "file_fna",
        "file_ffn",
        "file_faa",
        "hypo_tsv",
        "hypo_fa",
        "sum_txt",
        "file_json",
        "file_plot",
        "log_txt",
    ]
    DEFAULT_OUTPUT_SELECTION = ["file_tsv", "file_gff3", "file_ffn", "file_plot"]
    OUTPUT_FILES = {
        "file_tsv": ("annotation_tsv.tsv", "bakta_output/bakta_output.tsv"),
        "file_gff3": ("annotation_gff3.gff3", "bakta_output/bakta_output.gff3"),
        "file_gbff": ("annotation_gbff.gbff", "bakta_output/bakta_output.gbff"),
        "file_embl": ("annotation_embl.embl", "bakta_output/bakta_output.embl"),
        "file_fna": ("annotation_fna.fasta", "bakta_output/bakta_output.fna"),
        "file_ffn": ("annotation_ffn.fasta", "bakta_output/bakta_output.ffn"),
        "file_faa": ("annotation_faa.fasta", "bakta_output/bakta_output.faa"),
        "hypo_tsv": ("hypotheticals_tsv.tsv", "bakta_output/bakta_output.hypotheticals.tsv"),
        "hypo_fa": ("hypotheticals_faa.fasta", "bakta_output/bakta_output.hypotheticals.faa"),
        "sum_txt": ("summary_txt.txt", "bakta_output/bakta_output.txt"),
        "file_json": ("annotation_json.json", "bakta_output/bakta_output.json"),
        "file_plot": ("annotation_plot.svg", "bakta_output/bakta_output.svg"),
        "log_txt": ("logfile.txt", "logfile.txt"),
    }

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "input_file": ("FASTA", {"description": "Genome in FASTA or FASTA.GZ format"}),
                "bakta_db": ("DIRECTORY", {"description": "Bakta database path"}),
                "amrfinder_db": ("DIRECTORY", {"description": "AMRFinderPlus database path"}),
            },
            "optional": {
                "min_contig_length": (
                    "INT",
                    {
                        "default": 1,
                        "min": 0,
                        "description": "Minimum contig size; Galaxy uses 200 in compliant mode when unset",
                    },
                ),
                "genus": ("STRING", {"default": ""}),
                "species": ("STRING", {"default": ""}),
                "strain": ("STRING", {"default": ""}),
                "plasmid": ("STRING", {"default": ""}),
                "complete": ("BOOLEAN", {"default": False}),
                "prodigal": ("TXT", {"default": "", "description": "Prodigal training file"}),
                "translation_table": (
                    "STRING",
                    {"default": "11", "options": ["4", "11"], "description": "Genetic translation table"},
                ),
                "keep_contig_headers": ("BOOLEAN", {"default": False}),
                "replicons": ("TSV", {"default": ""}),
                "compliant": ("BOOLEAN", {"default": False}),
                "proteins": ("FASTA", {"default": ""}),
                "meta": ("BOOLEAN", {"default": False}),
                "regions": ("GFF", {"default": ""}),
                "skip_analysis": (
                    "STRING_LIST",
                    {"default": [], "options": cls.SKIP_ANALYSIS_OPTIONS, "is_list": True},
                ),
                "output_selection": (
                    "STRING_LIST",
                    {
                        "default": list(cls.DEFAULT_OUTPUT_SELECTION),
                        "options": cls.OUTPUT_SELECTION_OPTIONS,
                        "is_list": True,
                    },
                ),
                "threads": ("INT", {"default": 1, "min": 1, "max": 64}),
            },
            "hidden": {
                "output": ("STRING", {}),
            },
        }

    @classmethod
    def _as_list(cls, value: Any, default: list[str] | None = None) -> list[str]:
        if value is None or value == "":
            return list(default or [])
        if isinstance(value, (list, tuple, set)):
            return [str(item) for item in value if str(item)]
        return [part.strip() for part in re.split(r"[\n,]+", str(value)) if part.strip()]

    @classmethod
    def _output_selection(cls, inputs: dict[str, Any]) -> list[str]:
        return cls._as_list(inputs.get("output_selection"), cls.DEFAULT_OUTPUT_SELECTION)

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        for name in ("input_file", "bakta_db", "amrfinder_db"):
            if not str(inputs.get(name, "")).strip():
                return f"{name} is required"

        min_contig_length = inputs.get("min_contig_length")
        if min_contig_length not in (None, ""):
            try:
                if int(min_contig_length) < 0:
                    return "min_contig_length must be >= 0"
            except (TypeError, ValueError):
                return "min_contig_length must be an integer"

        if str(inputs.get("translation_table", "11") or "11") not in {"4", "11"}:
            return "translation_table must be one of: 4, 11"

        skip_analysis = cls._as_list(inputs.get("skip_analysis"))
        invalid_skip = [entry for entry in skip_analysis if entry not in cls.SKIP_ANALYSIS_OPTIONS]
        if invalid_skip:
            return f"skip_analysis entries must be one of: {', '.join(cls.SKIP_ANALYSIS_OPTIONS)}"

        output_selection = cls._output_selection(inputs)
        invalid_outputs = [entry for entry in output_selection if entry not in cls.OUTPUT_SELECTION_OPTIONS]
        if invalid_outputs:
            return f"output_selection entries must be one of: {', '.join(cls.OUTPUT_SELECTION_OPTIONS)}"

        return True

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> str:
        out_dir = str(inputs.get("output", "."))
        cmd = [
            "bakta",
            "--verbose",
            "--threads",
            str(inputs.get("threads", 1) or 1),
            "--db",
            "./database_path",
            "--output",
            "bakta_output",
            "--min-contig-length",
            str(inputs.get("min_contig_length", 1) or 1),
            "--prefix",
            "bakta_output",
        ]
        for flag, input_name in (
            ("--genus", "genus"),
            ("--species", "species"),
            ("--strain", "strain"),
            ("--plasmid", "plasmid"),
        ):
            if inputs.get(input_name):
                cmd.extend([flag, str(inputs[input_name])])

        for input_name, flag in (
            ("complete", "--complete"),
            ("meta", "--meta"),
        ):
            if inputs.get(input_name):
                cmd.append(flag)

        if inputs.get("prodigal"):
            cmd.extend(["--prodigal-tf", str(inputs["prodigal"])])
        if inputs.get("translation_table"):
            cmd.extend(["--translation-table", str(inputs["translation_table"])])
        cmd.extend(["--gram", "?"])
        if inputs.get("keep_contig_headers"):
            cmd.append("--keep-contig-headers")
        if inputs.get("replicons"):
            cmd.extend(["--replicons", str(inputs["replicons"])])
        if inputs.get("compliant"):
            cmd.append("--compliant")
        if inputs.get("proteins"):
            cmd.extend(["--proteins", str(inputs["proteins"])])
        if inputs.get("regions"):
            cmd.extend(["--regions", str(inputs["regions"])])

        cmd.extend(cls._as_list(inputs.get("skip_analysis")))
        cmd.extend([str(inputs.get("input_file", "")), "2>&1", "|", "tee", f"{out_dir}/logfile.txt"])

        commands = [
            _shell_join(["mkdir", "-p", "./database_path/amrfinderplus-db", out_dir]),
            f"ln -s {_shell_join([str(inputs.get('bakta_db', ''))])}/* database_path",
            _shell_join(["ln", "-s", f"{str(inputs.get('amrfinder_db', '')).rstrip('/')}/", "database_path/amrfinderplus-db/latest"]),
            _shell_join(cmd),
        ]
        for selected in cls._output_selection(inputs):
            if selected == "log_txt":
                continue
            target, source = cls.OUTPUT_FILES[selected]
            commands.append(_shell_join(["cp", source, f"{out_dir}/{target}"]))
        return " && ".join(commands)

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list:
        node_out = Path(output_dir) / cls.NODE_ID
        node_out.mkdir(parents=True, exist_ok=True)
        return [node_out / cls.OUTPUT_FILES[selected][0] for selected in cls._output_selection(inputs)]


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


class FuncotatorNode(FuncotateTableNode):
    """Compatibility alias for GATK Funcotator."""

    NODE_ID = "funcotator"
    DISPLAY_NAME = "Funcotator"
    DESCRIPTION = "Annotate cancer variants with GATK Funcotator."
    SEARCH_ALIASES = [
        "funcotator",
        "funcotate",
        "gatk funcotator",
        "cancer variants",
        "somatic annotation",
        "oncotator",
    ]


class BcftoolsAnnotateNode(CommandNode):
    """Annotate VCF records from BED, VCF, or TSV annotation files."""

    NODE_ID = "bcftools_annotate"
    DISPLAY_NAME = "BCFtools Annotate"
    CATEGORY = "variant"
    DESCRIPTION = "Annotate and edit VCF/BCF records using BED, tabular, VCF, or BCF annotation sources."
    SEARCH_ALIASES = [
        "BioNodulo builtin",
        "bcftools",
        "annotate",
        "annotate vcf",
        "edit vcf annotations",
        "custom annotation",
        "bed annotation",
        "remove annotations",
    ]
    RETURN_TYPES = ("VCF_GZ",)
    RETURN_NAMES = ("annotated_vcf",)
    REQUIRED_EXECUTABLES = ["bcftools", "bgzip", "tabix"]
    REQUIRED_CONDA_PACKAGES = ["bcftools", "htslib"]
    DOCUMENTATION_URL = "https://www.htslib.org/doc/bcftools.html#annotate"
    CITATION_DOIS = BCFTOOLS_CITATION_DOIS
    CITATION_URLS = BCFTOOLS_CITATION_URLS
    CITATION_TEXT = BCFTOOLS_CITATION_TEXT
    VERSION = "1.22+galaxy0"
    SHELL = True
    OUTPUT_TYPES = ["b", "u", "z", "v"]
    ANNOTATION_FORMATS = ["none", "vcf", "tab"]

    @classmethod
    def _out(cls, inputs: dict[str, Any]) -> str:
        return str(inputs.get("output", inputs.get("output_dir", ".")))

    @classmethod
    def _input_file(cls, inputs: dict[str, Any]) -> str:
        return str(inputs.get("input_file", inputs.get("vcf", "")))

    @classmethod
    def _annotations(cls, inputs: dict[str, Any]) -> str:
        return str(inputs.get("annotations", inputs.get("annotation_file", "")))

    @classmethod
    def _output_suffix(cls, inputs: dict[str, Any]) -> str:
        return {"b": ".bcf", "u": ".bcf", "z": ".vcf.gz", "v": ".vcf"}.get(
            str(inputs.get("output_type", "z") or "z"),
            ".vcf.gz",
        )

    @classmethod
    def _annotation_format(cls, inputs: dict[str, Any]) -> str:
        value = str(inputs.get("annotation_format", "") or "").strip()
        if value:
            return value
        annotations = cls._annotations(inputs)
        if not annotations:
            return "none"
        suffixes = "".join(Path(annotations).suffixes).lower()
        if suffixes.endswith((".vcf", ".vcf.gz", ".bcf")):
            return "vcf"
        return "tab"

    @classmethod
    def _add_if_value(cls, cmd: list[str], flag: str, value: Any) -> None:
        if value is not None and str(value) != "":
            cmd.extend([flag, str(value)])

    @classmethod
    def _annotation_prep(cls, inputs: dict[str, Any], out: str) -> tuple[list[str], str, str]:
        annotation_format = cls._annotation_format(inputs)
        annotations = cls._annotations(inputs)
        if annotation_format == "none":
            return [], "", ""
        if annotation_format == "vcf":
            if annotations.endswith(".bcf"):
                prepared = f"{out}/annotations.bcf"
                return ["ln", "-s", annotations, prepared, "&&", "bcftools", "index", prepared, "&&"], prepared, ""
            prepared = f"{out}/annotations.vcf.gz"
            return ["bgzip", "-c", annotations, ">", prepared, "&&", "bcftools", "index", prepared, "&&"], prepared, ""
        if annotations.endswith(".bed") or annotations.endswith(".bed.gz"):
            prepared = f"{out}/annotations.bed.gz"
            prep = [
                "bgzip",
                "-c",
                annotations,
                ">",
                prepared,
                "&&",
                "tabix",
                "-s",
                "1",
                "-b",
                "2",
                "-e",
                "3",
                prepared,
                "&&",
            ]
            return prep, prepared, ""
        prepared = f"{out}/annotations.tab.gz"
        prep = [
            "bgzip",
            "-c",
            annotations,
            ">",
            prepared,
            "&&",
            "tabix",
            "-s",
            "1",
            "-b",
            "2",
            "-e",
            "2",
            prepared,
            "&&",
        ]
        return prep, prepared, ""

    @classmethod
    def _annotate_cmd(cls, inputs: dict[str, Any], prepared_annotations: str, header_path: str) -> list[str]:
        cmd = ["bcftools", "annotate"]
        columns = inputs.get("columns", inputs.get("annotation_columns"))
        header_lines = str(inputs.get("header_lines", "") or "")
        header_file = header_path or inputs.get("header_file")
        if not header_file and header_lines and Path(header_lines).suffix:
            header_file = header_lines
        cls._add_if_value(cmd, "--columns", columns)
        cls._add_if_value(cmd, "--annotations", prepared_annotations)
        cls._add_if_value(cmd, "--header-lines", header_file)
        cls._add_if_value(cmd, "--set-id", inputs.get("set_id"))
        cls._add_if_value(cmd, "--mark-sites", inputs.get("mark_sites"))
        cls._add_if_value(cmd, "--min-overlap", inputs.get("min_overlap"))
        cls._add_if_value(cmd, "--rename-chrs", inputs.get("rename_chrs"))
        cls._add_if_value(cmd, "--remove", inputs.get("remove"))
        cls._add_if_value(cmd, "--rename-annots", inputs.get("rename_annots"))
        cls._add_if_value(cmd, "--collapse", inputs.get("collapse"))
        cls._add_if_value(cmd, "--regions", inputs.get("regions"))
        cls._add_if_value(cmd, "--regions-overlap", inputs.get("regions_overlap"))
        cls._add_if_value(cmd, "--targets", inputs.get("targets"))
        cls._add_if_value(cmd, "--targets-overlap", inputs.get("targets_overlap"))
        samples = inputs.get("samples")
        if samples is not None and str(samples) != "":
            prefix = "^" if inputs.get("invert_samples") else ""
            cmd.extend(["--samples", f"{prefix}{samples}"])
        samples_file = inputs.get("samples_file")
        if samples_file is not None and str(samples_file) != "":
            prefix = "^" if inputs.get("invert_samples_file") else ""
            cmd.extend(["--samples-file", f"{prefix}{samples_file}"])
        cls._add_if_value(cmd, "--include", inputs.get("include"))
        cls._add_if_value(cmd, "--exclude", inputs.get("exclude"))
        cmd.extend(["--output-type", str(inputs.get("output_type", "z") or "z")])
        threads = inputs.get("threads")
        if threads not in (None, "", 0, "0"):
            cmd.extend(["--threads", str(threads)])
        cmd.append(cls._input_file(inputs))
        cmd.extend([">", f"{cls._out(inputs)}/annotated{cls._output_suffix(inputs)}"])
        return cmd

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> str | list[str]:
        out = cls._out(inputs)
        prep, prepared_annotations, _ = cls._annotation_prep(inputs, out)
        header_lines = str(inputs.get("header_lines", "") or "")
        header_path = ""
        if header_lines and not Path(header_lines).suffix:
            header_path = f"{out}/annotation.hdr"
            header_write = f"cat > {header_path} <<'EOF'\n{header_lines}\nEOF\n"
            return header_write + _shell_join([*prep, *cls._annotate_cmd(inputs, prepared_annotations, header_path)])
        cmd = [*prep, *cls._annotate_cmd(inputs, prepared_annotations, header_path)]
        return cmd

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        node_out = Path(output_dir) / cls.NODE_ID
        node_out.mkdir(parents=True, exist_ok=True)
        return [node_out / f"annotated{cls._output_suffix(inputs)}"]

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        if not cls._input_file(inputs).strip():
            return "input_file is required"
        annotation_format = cls._annotation_format(inputs)
        if annotation_format not in cls.ANNOTATION_FORMATS:
            return f"annotation_format must be one of: {', '.join(cls.ANNOTATION_FORMATS)}"
        if annotation_format in {"vcf", "tab"} and not cls._annotations(inputs).strip():
            return f"annotations is required when annotation_format is {annotation_format}"
        columns = str(inputs.get("columns", inputs.get("annotation_columns", "")) or "").strip()
        if annotation_format in {"vcf", "tab"} and not columns:
            return f"columns is required when annotation_format is {annotation_format}"
        output_type = str(inputs.get("output_type", "z") or "z")
        if output_type not in cls.OUTPUT_TYPES:
            return f"output_type must be one of: {', '.join(cls.OUTPUT_TYPES)}"
        base_validation = super().VALIDATE_INPUTS(inputs)
        if base_validation is not True:
            return base_validation
        return True

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "input_file": ("VCF", {"description": "VCF/BCF file to annotate or edit"}),
            },
            "optional": {
                "annotation_format": (
                    "STRING",
                    {"default": "none", "options": cls.ANNOTATION_FORMATS, "description": "Annotation source type"},
                ),
                "annotations": ("FILE", {"default": "", "description": "BED, tab-delimited, VCF, or BCF annotations"}),
                "columns": ("STRING", {"default": "", "description": "Annotation columns such as CHROM,POS,REF,ALT,INFO/TAG"}),
                "header_file": ("FILE", {"description": "Header lines file to append to the output VCF"}),
                "header_lines": ("STRING", {"default": "", "description": "Inline VCF header lines to append"}),
                "set_id": ("STRING", {"default": "", "description": "Set variant IDs from a bcftools expression"}),
                "mark_sites": ("STRING", {"default": "", "description": "Flag sites present or absent from the annotation file"}),
                "min_overlap": ("STRING", {"default": "", "description": "Minimum overlap for annotation intersections"}),
                "rename_chrs": ("TSV", {"description": "Map old chromosome names to new names"}),
                "remove": ("STRING", {"default": "", "description": "Annotations to remove, such as INFO, FORMAT, or INFO/TAG"}),
                "rename_annots": ("TSV", {"description": "Rename FILTER, INFO, or FORMAT annotations"}),
                "collapse": ("STRING", {"default": "", "options": ["", "snps", "indels", "both", "some", "any", "none", "id"]}),
                "regions": ("STRING", {"default": "", "description": "Restrict to regions"}),
                "regions_overlap": ("STRING", {"default": "", "options": ["", "0", "1", "2"], "description": "Galaxy regions-overlap mode"}),
                "targets": ("STRING", {"default": "", "description": "Restrict to targets"}),
                "targets_overlap": ("STRING", {"default": "", "options": ["", "0", "1", "2"], "description": "Galaxy targets-overlap mode"}),
                "samples": ("STRING", {"default": "", "description": "Comma-separated samples to include or exclude"}),
                "invert_samples": ("BOOLEAN", {"default": False, "description": "Exclude the samples listed in samples"}),
                "samples_file": ("TSV", {"description": "File of samples to include or exclude"}),
                "invert_samples_file": ("BOOLEAN", {"default": False, "description": "Exclude samples listed in samples_file"}),
                "include": ("STRING", {"default": "", "description": "Include-expression filter"}),
                "exclude": ("STRING", {"default": "", "description": "Exclude-expression filter"}),
                "output_type": ("STRING", {"default": "z", "options": cls.OUTPUT_TYPES, "description": "BCFtools output type"}),
                "threads": ("INT", {"default": 4, "min": 1, "max": 128, "display": "slider"}),
                "vcf": ("VCF_GZ", {"description": "Compatibility alias for input_file", "advanced": True}),
                "annotation_columns": (
                    "STRING",
                    {"default": "", "description": "Compatibility alias for columns", "advanced": True},
                ),
            },
            "hidden": {
                "output": ("STRING", {}),
            },
        }


class AnnotateVCFNode(CommandNode):
    """Annotate VCF records from one or more custom annotation sources."""

    NODE_ID = "annotate_vcf"
    DISPLAY_NAME = "Annotate VCF"
    CATEGORY = "annotation"
    DESCRIPTION = "Annotate VCF records with gene names, consequences, and frequencies from multiple sources."
    SEARCH_ALIASES = [
        "annotate vcf",
        "variant annotation",
        "multi-source annotation",
        "vcfanno",
        "bcftools annotate",
        "roadmap",
    ]
    RETURN_TYPES = ("VCF_GZ", "VCF_INDEX")
    RETURN_NAMES = ("annotated_vcf", "annotated_vcf_index")
    REQUIRED_EXECUTABLES = ["bcftools", "vcfanno"]
    REQUIRED_CONDA_PACKAGES = ["bcftools", "vcfanno"]
    DOCUMENTATION_URL = "https://github.com/brentp/vcfanno"
    VERSION = "1.0.0"
    SHELL = True

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "vcf": ("VCF_GZ", {"description": "Input bgzipped VCF"}),
            },
            "optional": {
                "mode": (
                    "STRING",
                    {
                        "default": "vcfanno",
                        "options": ["vcfanno", "bcftools"],
                        "description": "Annotation backend",
                    },
                ),
                "annotation_files": ("STRING", {"default": "", "description": "Comma- or newline-separated BED/VCF/TSV annotation files"}),
                "vcfanno_config": ("FILE", {"default": "", "description": "vcfanno TOML configuration"}),
                "columns": (
                    "STRING",
                    {
                        "default": "",
                        "description": "Newline-separated bcftools column specs matching annotation_files, e.g. CHROM,FROM,TO,GENE",
                    },
                ),
                "header_lines": (
                    "STRING",
                    {
                        "default": "",
                        "description": "Newline-separated bcftools header files matching annotation_files; use '-' to skip a source",
                    },
                ),
                "output_name": ("STRING", {"default": "", "description": "Optional output filename stem"}),
                "threads": ("INT", {"default": 4, "min": 0, "max": 64}),
            },
            "hidden": {
                "output": ("STRING", {}),
            },
        }

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        base_validation = super().VALIDATE_INPUTS(inputs)
        if base_validation is not True:
            return base_validation
        mode = str(inputs.get("mode", "vcfanno") or "vcfanno").lower()
        if mode not in {"vcfanno", "bcftools"}:
            return f"Unsupported annotation mode: {mode}"
        if mode == "vcfanno" and not str(inputs.get("vcfanno_config", "") or "").strip():
            return "vcfanno_config is required in vcfanno mode"
        if mode == "bcftools":
            annotation_files = _split_annotation_files(inputs.get("annotation_files"))
            columns = _split_annotation_lines(inputs.get("columns"))
            header_lines = _split_annotation_lines(inputs.get("header_lines"))
            if not annotation_files:
                return "At least one annotation file is required in bcftools mode"
            if not columns:
                return "columns is required in bcftools mode"
            if len(columns) != len(annotation_files):
                return "columns must provide one newline-separated entry per bcftools annotation file"
            if header_lines and len(header_lines) != len(annotation_files):
                return "header_lines must provide one newline-separated entry per bcftools annotation file, using '-' to skip a source"
        return True

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        validation = cls.VALIDATE_INPUTS(inputs)
        if validation is not True:
            raise ValueError(str(validation))

        output_vcf = cls._output_vcf_path(inputs, inputs.get("output", inputs.get("output_dir", ".")))
        mode = str(inputs.get("mode", "vcfanno") or "vcfanno").lower()
        threads = int(inputs.get("threads", 4) or 0)
        if mode == "vcfanno":
            return cls._render_vcfanno_command(inputs, output_vcf, threads)
        return cls._render_bcftools_command(inputs, output_vcf, threads)

    @classmethod
    def _render_vcfanno_command(cls, inputs: dict[str, Any], output_vcf: Path, threads: int) -> list[str]:
        cmd = ["set", "-euo", "pipefail", "&&", "vcfanno"]
        if threads > 0:
            cmd.extend(["-p", str(threads)])
        cmd.extend([
            str(inputs.get("vcfanno_config", "")),
            str(inputs.get("vcf", "")),
            "|",
            "bcftools",
            "view",
            "-Oz",
            "-o",
            str(output_vcf),
            "&&",
            "bcftools",
            "index",
            "-f",
            "-t",
            str(output_vcf),
        ])
        return cmd

    @classmethod
    def _render_bcftools_command(cls, inputs: dict[str, Any], output_vcf: Path, threads: int) -> list[str]:
        annotation_files = _split_annotation_files(inputs.get("annotation_files"))
        columns = _split_annotation_lines(inputs.get("columns"))
        header_lines = _split_annotation_lines(inputs.get("header_lines"))
        cmd: list[str] = ["set", "-euo", "pipefail", "&&"]
        for index, annotation_file in enumerate(annotation_files):
            if index > 0:
                cmd.append("|")
            cmd.extend(["bcftools", "annotate", "-a", annotation_file])
            cmd.extend(["-c", columns[index]])
            if header_lines and header_lines[index] != "-":
                cmd.extend(["-h", header_lines[index]])
            if threads > 0:
                cmd.extend(["--threads", str(threads)])
            cmd.append("-Oz" if index == len(annotation_files) - 1 else "-Ou")
            if index == len(annotation_files) - 1:
                cmd.extend(["-o", str(output_vcf)])
            if index == 0:
                cmd.append(str(inputs.get("vcf", "")))
            else:
                cmd.append("-")
        cmd.extend(["&&", "bcftools", "index", "-f", "-t", str(output_vcf)])
        return cmd

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        output_vcf = cls._output_vcf_path(inputs, Path(output_dir) / cls.NODE_ID)
        output_index = Path(str(output_vcf) + ".tbi")
        output_vcf.parent.mkdir(parents=True, exist_ok=True)
        return [output_vcf, output_index]

    @classmethod
    def _output_vcf_path(cls, inputs: dict[str, Any], output_dir: str | Path) -> Path:
        stem = _safe_output_stem(str(inputs.get("output_name", "") or ""), "annotated_vcf")
        return Path(output_dir) / f"{stem}.annotated.vcf.gz"


from bionodulo.nodes.builtin.bedtools_family.closest import BEDToolsClosestNode  # noqa: E402,F401


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
