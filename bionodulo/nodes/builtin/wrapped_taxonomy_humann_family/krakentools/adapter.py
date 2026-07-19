"""Shared KrakenTools and Krona contracts for focused owners."""
# ruff: noqa: F403,F405
from __future__ import annotations

from bionodulo.nodes.builtin._wrapped_tool_utils import *
from bionodulo.nodes.builtin.wrapped_taxonomy_humann_family.contracts import ToolsIUCCommandContract

class _KrakentoolsCombineKreportsContract(ToolsIUCCommandContract):
    """Combine multiple Kraken-style reports with KrakenTools."""

    LEGACY_NODE_ID = "krakentools_combine_kreports"
    DISPLAY_NAME = "Krakentools Combine Kraken Reports"
    REQUIRED_CONDA_PACKAGES = ["krakentools"]
    CATEGORY = "taxonomy"
    DESCRIPTION = "Combine multiple Kraken-style taxonomy reports into one summed report."
    SEARCH_ALIASES = [
        BIONODULO_BUILTIN_ALIAS,
        "krakentools",
        "combine_kreports.py",
        "Kraken reports",
        "combined report",
        "only combined",
    ]
    RETURN_TYPES = ("TSV",)
    RETURN_NAMES = ("combined_report",)
    REQUIRED_EXECUTABLES = ["combine_kreports.py"]
    DOCUMENTATION_URL = "https://github.com/jenniferlu717/KrakenTools"
    CITATION_DOIS = [KRAKENTOOLS_DOI]
    CITATION_URLS = [f"{DOI_URL}{KRAKENTOOLS_DOI}"]
    CITATION_TEXT = KRAKENTOOLS_CITATION_TEXT
    VERSION = "1.2.1"
    SHELL = True

    @classmethod
    def _report_names(cls, inputs: dict[str, Any], reports: list[str]) -> list[str]:
        labels = _as_list(inputs.get("element_identifiers"))
        names: list[str] = []
        for index, report in enumerate(reports):
            label = labels[index] if index < len(labels) and labels[index] else report
            names.append(_safe_identifier(label))
        return names

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> str:
        out = _out(inputs)
        reports = _as_list(inputs.get("reports"))
        display_headers = bool(inputs.get("display_headers", True))
        report_args = reports
        commands: list[str] = []
        if display_headers:
            report_args = cls._report_names(inputs, reports)
            commands.extend(
                f"ln -s {shlex.quote(report)} {shlex.quote(report_name)}"
                for report, report_name in zip(reports, report_args, strict=False)
            )

        cmd = [
            "combine_kreports.py",
            "--reports",
            *report_args,
            "--output",
            f"{out}/combined_kreport.tsv",
            "--display-headers" if display_headers else "--no-headers",
        ]
        if inputs.get("only_combined", False):
            cmd.append("--only-combined")
        commands.append(shlex.join(cmd))
        return " && ".join(commands)

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        out = Path(output_dir) / cls.NODE_ID
        out.mkdir(parents=True, exist_ok=True)
        return [out / "combined_kreport.tsv"]

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "reports": (
                    "TSV",
                    {"multiple": True, "description": "One or more Kraken-style report files to combine"},
                ),
            },
            "optional": {
                "element_identifiers": (
                    "STRING",
                    {
                        "default": [],
                        "multiple": True,
                        "description": "Optional sample names used as headers when display_headers is enabled",
                    },
                ),
                "display_headers": (
                    "BOOLEAN",
                    {"default": True, "description": "Display sample headers in the combined output"},
                ),
                "only_combined": (
                    "BOOLEAN",
                    {"default": False, "description": "Display only combined read counts and percentages"},
                ),
            },
            "hidden": {"output": ("STRING", {})},
        }

class _KrakentoolsAlphaDiversityContract(ToolsIUCCommandContract):
    """Calculate alpha diversity metrics from Bracken abundance estimates."""

    LEGACY_NODE_ID = "krakentools_alpha_diversity"
    DISPLAY_NAME = "Krakentools Alpha Diversity"
    REQUIRED_CONDA_PACKAGES = ["krakentools"]
    CATEGORY = "taxonomy"
    DESCRIPTION = "Calculate alpha diversity metrics from a Bracken abundance estimation table."
    SEARCH_ALIASES = [
        BIONODULO_BUILTIN_ALIAS,
        "krakentools",
        "alpha_diversity.py",
        "alpha diversity",
        "Bracken abundance",
        "Shannon diversity",
    ]
    RETURN_TYPES = ("TEXT",)
    RETURN_NAMES = ("alpha_diversity",)
    REQUIRED_EXECUTABLES = ["alpha_diversity.py"]
    DOCUMENTATION_URL = "https://github.com/jenniferlu717/KrakenTools"
    CITATION_DOIS = [KRAKENTOOLS_DOI]
    CITATION_URLS = [f"{DOI_URL}{KRAKENTOOLS_DOI}"]
    CITATION_TEXT = KRAKENTOOLS_CITATION_TEXT
    VERSION = "1.2.1"
    SHELL = True

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> str:
        out = _out(inputs)
        abundance_file = inputs.get("abundance_file", inputs.get("filename", ""))
        cmd = [
            "alpha_diversity.py",
            "--filename",
            str(abundance_file),
            "--alpha",
            str(inputs.get("alpha", "Sh")),
        ]
        _add_shell_redirect(cmd, f"{out}/alpha_diversity.txt")
        return _shell_join(cmd)

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        out = Path(output_dir) / cls.NODE_ID
        out.mkdir(parents=True, exist_ok=True)
        return [out / "alpha_diversity.txt"]

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "abundance_file": (
                    "TSV",
                    {"description": "Bracken abundance estimation table used to calculate alpha diversity"},
                ),
            },
            "optional": {
                "alpha": (
                    "STRING",
                    {
                        "default": "Sh",
                        "options": ["Sh", "BP", "Si", "ISi", "F"],
                        "description": "Alpha diversity metric: Shannon, Berger-Parker, Simpson, inverse Simpson, or Fisher",
                    },
                ),
            },
            "hidden": {"output": ("STRING", {})},
        }

class _KrakentoolsBetaDiversityContract(ToolsIUCCommandContract):
    """Calculate Bray-Curtis beta diversity from taxonomy tables."""

    LEGACY_NODE_ID = "krakentools_beta_diversity"
    DISPLAY_NAME = "Krakentools Beta Diversity"
    REQUIRED_CONDA_PACKAGES = ["krakentools"]
    CATEGORY = "taxonomy"
    DESCRIPTION = "Calculate Bray-Curtis beta diversity from Kraken, Krona, Bracken, or tabular taxonomy files."
    SEARCH_ALIASES = [
        BIONODULO_BUILTIN_ALIAS,
        "krakentools",
        "beta_diversity.py",
        "beta diversity",
        "Bray-Curtis",
        "Krona file",
        "Bracken abundance",
    ]
    RETURN_TYPES = ("TSV",)
    RETURN_NAMES = ("beta_diversity",)
    REQUIRED_EXECUTABLES = ["beta_diversity.py"]
    DOCUMENTATION_URL = "https://github.com/jenniferlu717/KrakenTools"
    CITATION_DOIS = [KRAKENTOOLS_DOI]
    CITATION_URLS = [f"{DOI_URL}{KRAKENTOOLS_DOI}"]
    CITATION_TEXT = KRAKENTOOLS_CITATION_TEXT
    VERSION = "1.2.1"
    SHELL = True

    @classmethod
    def _input_names(cls, inputs: dict[str, Any], taxonomy_files: list[str]) -> list[str]:
        labels = _as_list(inputs.get("element_identifiers"))
        names: list[str] = []
        for index, taxonomy_file in enumerate(taxonomy_files):
            label = labels[index] if index < len(labels) and labels[index] else taxonomy_file
            names.append(_safe_identifier(label))
        return names

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> str:
        out = _out(inputs)
        taxonomy_files = _as_list(inputs.get("taxonomy_files", inputs.get("inputs")))
        input_names = cls._input_names(inputs, taxonomy_files)
        commands = [
            f"ln -s {shlex.quote(taxonomy_file)} {shlex.quote(input_name)}"
            for taxonomy_file, input_name in zip(taxonomy_files, input_names, strict=False)
        ]

        sample_type = str(inputs.get("sample_type", inputs.get("type", "single")))
        cmd = [
            "beta_diversity.py",
            "--inputs",
            *input_names,
            "--type",
            sample_type,
        ]
        if sample_type in {"kreport", "krona"}:
            cmd.extend(["--level", str(inputs.get("level", "all"))])
        _add_shell_redirect(cmd, f"{out}/beta_diversity.tsv")
        commands.append(_shell_join(cmd))
        return " && ".join(commands)

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        out = Path(output_dir) / cls.NODE_ID
        out.mkdir(parents=True, exist_ok=True)
        return [out / "beta_diversity.tsv"]

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "taxonomy_files": (
                    "TSV",
                    {"multiple": True, "description": "Kraken, Krona, Bracken, or tabular taxonomy files"},
                ),
            },
            "optional": {
                "element_identifiers": (
                    "STRING",
                    {
                        "default": [],
                        "multiple": True,
                        "description": "Optional sample labels used for beta diversity matrix headers",
                    },
                ),
                "sample_type": (
                    "STRING",
                    {
                        "default": "single",
                        "options": ["single", "simple", "bracken", "kreport", "krona"],
                        "description": "Input file type used by KrakenTools beta_diversity.py",
                    },
                ),
                "level": (
                    "STRING",
                    {
                        "default": "all",
                        "options": ["all", "S", "G", "F", "O"],
                        "description": "Taxonomic level used for Kraken report or Krona inputs",
                    },
                ),
            },
            "hidden": {"output": ("STRING", {})},
        }

class _KrakentoolsKreport2KronaContract(ToolsIUCCommandContract):
    """Convert Kraken reports to Krona-compatible text tables."""

    LEGACY_NODE_ID = "krakentools_kreport2krona"
    DISPLAY_NAME = "Krakentools Kreport2Krona"
    REQUIRED_CONDA_PACKAGES = ["krakentools"]
    CATEGORY = "taxonomy"
    DESCRIPTION = "Convert a Kraken report into a Krona-compatible text table."
    SEARCH_ALIASES = [
        BIONODULO_BUILTIN_ALIAS,
        "krakentools",
        "kreport2krona.py",
        "Krona-compatible",
        "intermediate ranks",
        "Kraken report",
    ]
    RETURN_TYPES = ("TSV",)
    RETURN_NAMES = ("krona_text",)
    REQUIRED_EXECUTABLES = ["kreport2krona.py"]
    DOCUMENTATION_URL = "https://github.com/jenniferlu717/KrakenTools"
    CITATION_DOIS = [KRAKENTOOLS_DOI]
    CITATION_URLS = [f"{DOI_URL}{KRAKENTOOLS_DOI}"]
    CITATION_TEXT = KRAKENTOOLS_CITATION_TEXT
    VERSION = "1.2.1"

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> str:
        out = _out(inputs)
        cmd = [
            "kreport2krona.py",
            "--report",
            str(inputs.get("report", "")),
            "--output",
            f"{out}/krona_text.tsv",
        ]
        if inputs.get("intermediate_ranks", False):
            cmd.append("--intermediate-ranks")
        return shlex.join(cmd)

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        out = Path(output_dir) / cls.NODE_ID
        out.mkdir(parents=True, exist_ok=True)
        return [out / "krona_text.tsv"]

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "report": ("TSV", {"description": "Kraken report file to convert to Krona-compatible text"}),
            },
            "optional": {
                "intermediate_ranks": (
                    "BOOLEAN",
                    {"default": False, "description": "Include non-standard intermediate ranks in the Krona paths"},
                ),
            },
            "hidden": {"output": ("STRING", {})},
        }

class _TaxonomyKronaChartContract(ToolsIUCCommandContract):
    """Render taxonomy or tabular profiles as an interactive Krona chart."""

    LEGACY_NODE_ID = "taxonomy_krona_chart"
    DISPLAY_NAME = "Krona pie chart"
    REQUIRED_CONDA_PACKAGES = ["krona"]
    CATEGORY = "taxonomy"
    DESCRIPTION = "Render taxonomic profiles as an interactive Krona HTML pie chart."
    SEARCH_ALIASES = [
        BIONODULO_BUILTIN_ALIAS,
        "Krona",
        "taxonomy_krona_chart",
        "ktImportGalaxy",
        "ktImportText",
        "taxonomy sunburst",
        "metagenomic visualization",
        "taxonomic profile",
    ]
    RETURN_TYPES = ("HTML_REPORT",)
    RETURN_NAMES = ("output",)
    REQUIRED_EXECUTABLES = ["ktImportGalaxy", "ktImportText"]
    DOCUMENTATION_URL = "https://github.com/marbl/Krona/wiki"
    CITATION_DOIS = KRONA_CITATION_DOIS
    CITATION_URLS = [f"{DOI_URL}{doi}" for doi in KRONA_CITATION_DOIS]
    CITATION_TEXT = KRONA_CITATION_TEXT
    VERSION = "2.7.1+galaxy0"
    SHELL = True

    TYPE_OPTIONS = ["taxonomy", "text"]
    MAX_RANK_OPTIONS = [
        "8",
        "0",
        "1",
        "2",
        "3",
        "4",
        "5",
        "6",
        "7",
        "9",
        "10",
        "11",
        "12",
        "13",
        "14",
        "15",
        "16",
        "17",
        "18",
        "19",
        "20",
        "21",
    ]

    @classmethod
    def _input_files(cls, inputs: dict[str, Any]) -> list[str]:
        return _as_list(inputs.get("input"))

    @classmethod
    def _input_labels(cls, inputs: dict[str, Any], input_files: list[str]) -> list[str]:
        labels = _as_list(inputs.get("element_identifiers"))
        result: list[str] = []
        for index, input_file in enumerate(input_files):
            label = labels[index] if index < len(labels) and labels[index] else Path(input_file).stem
            result.append(_safe_identifier(label))
        return result

    @classmethod
    def _output_path(cls, inputs: dict[str, Any]) -> str:
        return f"{_out(inputs)}/krona.html"

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> str:
        out = _out(inputs)
        input_type = str(inputs.get("type_of_data_selector", "taxonomy") or "taxonomy")
        cmd = ["ktImportGalaxy" if input_type == "taxonomy" else "ktImportText"]
        if input_type == "taxonomy":
            cmd.extend(["-d", str(inputs.get("max_rank", "8") or "8")])
        cmd.extend([
            "-n",
            str(inputs.get("root_name", "Root") or "Root"),
            "-o",
            cls._output_path(inputs),
        ])
        if inputs.get("combine_inputs", False):
            cmd.append("-c")
        input_files = cls._input_files(inputs)
        labels = cls._input_labels(inputs, input_files)
        for input_file, label in zip(input_files, labels, strict=False):
            cmd.append(f"{input_file},{label}")
        return " && ".join([f"mkdir -p {shlex.quote(out)}", _shell_join(cmd)])

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        out = Path(output_dir) / cls.NODE_ID
        out.mkdir(parents=True, exist_ok=True)
        return [out / "krona.html"]

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        if not cls._input_files(inputs):
            return "at least one input file is required"
        input_type = str(inputs.get("type_of_data_selector", "taxonomy") or "taxonomy")
        if input_type not in cls.TYPE_OPTIONS:
            return f"type_of_data_selector must be one of: {', '.join(cls.TYPE_OPTIONS)}"
        max_rank = str(inputs.get("max_rank", "8") or "8")
        if max_rank not in cls.MAX_RANK_OPTIONS:
            return f"max_rank must be one of: {', '.join(cls.MAX_RANK_OPTIONS)}"
        return True

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "input": ("TSV", {"multiple": True, "description": "One or more taxonomy or tabular profile files"}),
            },
            "optional": {
                "type_of_data_selector": (
                    "STRING",
                    {
                        "default": "taxonomy",
                        "options": cls.TYPE_OPTIONS,
                        "description": "Galaxy taxonomy input or generic tabular profile input",
                    },
                ),
                "max_rank": (
                    "STRING",
                    {
                        "default": "8",
                        "options": cls.MAX_RANK_OPTIONS,
                        "description": "Maximum taxonomy rank depth for Galaxy taxonomy input",
                    },
                ),
                "root_name": ("STRING", {"default": "Root", "description": "Name for the basal rank"}),
                "combine_inputs": (
                    "BOOLEAN",
                    {"default": False, "description": "Combine multiple datasets into one Krona chart"},
                ),
                "element_identifiers": (
                    "STRING",
                    {"default": [], "multiple": True, "description": "Optional labels for the input datasets"},
                ),
            },
            "hidden": {"output": ("STRING", {})},
        }

class _MothurTaxonomyToKronaContract(ToolsIUCCommandContract):
    """Convert mothur consensus taxonomy tables to Krona text input."""

    LEGACY_NODE_ID = "mothur_taxonomy_to_krona"
    DISPLAY_NAME = "Taxonomy-to-Krona"
    REQUIRED_CONDA_PACKAGES = []
    CATEGORY = "taxonomy"
    DESCRIPTION = "Convert a mothur consensus taxonomy file to Krona text input format."
    SEARCH_ALIASES = [
        BIONODULO_BUILTIN_ALIAS,
        "mothur",
        "mothur_taxonomy_to_krona",
        "Taxonomy-to-Krona",
        "mothur consensus taxonomy",
        "Krona text input",
        "strip confidence values",
        "cons.taxonomy",
    ]
    RETURN_TYPES = ("TSV",)
    RETURN_NAMES = ("outputfile",)
    REQUIRED_EXECUTABLES = ["cat", "tail", "cut", "sed"]
    DOCUMENTATION_URL = "https://marbl.github.io/Krona/Documentation/"
    CITATION_DOIS = [MOTHUR_DOI, KRONA_CITATION_DOIS[0]]
    CITATION_URLS = [f"{DOI_URL}{doi}" for doi in CITATION_DOIS]
    CITATION_TEXT = f"{MOTHUR_CITATION_TEXT} {KRONA_CITATION_TEXT.split(';', 1)[0]}."
    VERSION = "1.0"
    SHELL = True

    @classmethod
    def _output_path(cls, inputs: dict[str, Any]) -> str:
        return f"{_out(inputs)}/krona_taxonomy.tsv"

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> str:
        pipeline = [
            f"cat {shlex.quote(str(inputs.get('inputfile', '')))}",
            "tail -n +2",
            "cut -f2,3",
            "sed 's/;/\\t/g'",
            "sed 's/\"//g'",
            "sed 's/[ \\t]*$//'",
        ]
        if inputs.get("stripconfidences", False):
            pipeline.append("sed -r 's/[(][0-9]+[)]//g'")
        return f"{' | '.join(pipeline)} > {shlex.quote(cls._output_path(inputs))}"

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        out = Path(output_dir) / cls.NODE_ID
        out.mkdir(parents=True, exist_ok=True)
        return [out / "krona_taxonomy.tsv"]

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        if not str(inputs.get("inputfile", "")).strip():
            return "inputfile is required"
        return True

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "inputfile": (
                    "TSV",
                    {
                        "description": "Mothur consensus taxonomy table with OTU, size, and taxonomy columns",
                    },
                ),
            },
            "optional": {
                "stripconfidences": (
                    "BOOLEAN",
                    {
                        "default": False,
                        "description": "Remove taxonomy confidence values such as Bacteria(100)",
                    },
                ),
            },
            "hidden": {"output": ("STRING", {})},
        }

class _KrakentoolsKreport2MpaContract(ToolsIUCCommandContract):
    """Convert Kraken reports to MetaPhlAn-style profile tables."""

    LEGACY_NODE_ID = "krakentools_kreport2mpa"
    DISPLAY_NAME = "Krakentools Kreport2MPA"
    REQUIRED_CONDA_PACKAGES = ["krakentools"]
    CATEGORY = "taxonomy"
    DESCRIPTION = "Convert a Kraken report into a MetaPhlAn-style profile table."
    SEARCH_ALIASES = [
        BIONODULO_BUILTIN_ALIAS,
        "krakentools",
        "kreport2mpa.py",
        "MetaPhlAn-style",
        "percentages",
        "intermediate ranks",
        "Kraken report",
    ]
    RETURN_TYPES = ("TSV",)
    RETURN_NAMES = ("metaphlan_profile",)
    REQUIRED_EXECUTABLES = ["kreport2mpa.py"]
    DOCUMENTATION_URL = "https://github.com/jenniferlu717/KrakenTools"
    CITATION_DOIS = [KRAKENTOOLS_DOI]
    CITATION_URLS = [f"{DOI_URL}{KRAKENTOOLS_DOI}"]
    CITATION_TEXT = KRAKENTOOLS_CITATION_TEXT
    VERSION = "1.2.1"

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> str:
        out = _out(inputs)
        cmd = [
            "kreport2mpa.py",
            "--report",
            str(inputs.get("report", "")),
            "--output",
            f"{out}/metaphlan_profile.tsv",
        ]
        if inputs.get("intermediate_ranks", False):
            cmd.append("--intermediate-ranks")
        if inputs.get("percentages", False):
            cmd.append("--percentages")
        return shlex.join(cmd)

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        out = Path(output_dir) / cls.NODE_ID
        out.mkdir(parents=True, exist_ok=True)
        return [out / "metaphlan_profile.tsv"]

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "report": ("TSV", {"description": "Kraken report file to convert to MetaPhlAn-style format"}),
            },
            "optional": {
                "intermediate_ranks": (
                    "BOOLEAN",
                    {"default": False, "description": "Include non-standard intermediate ranks in the output profile"},
                ),
                "percentages": (
                    "BOOLEAN",
                    {"default": False, "description": "Report percentage of total reads instead of raw read counts"},
                ),
            },
            "hidden": {"output": ("STRING", {})},
        }

class _KrakentoolsExtractKrakenReadsContract(ToolsIUCCommandContract):
    """Extract reads assigned to selected taxonomy IDs from Kraken output."""

    LEGACY_NODE_ID = "krakentools_extract_kraken_reads"
    DISPLAY_NAME = "Krakentools Extract Kraken Reads By ID"
    REQUIRED_CONDA_PACKAGES = ["krakentools", "gzip"]
    CATEGORY = "taxonomy"
    DESCRIPTION = (
        "Extract FASTA or FASTQ reads assigned to selected taxonomic IDs from "
        "Kraken, KrakenUniq, or Kraken2 classifications."
    )
    SEARCH_ALIASES = [
        BIONODULO_BUILTIN_ALIAS,
        "krakentools",
        "extract_kraken_reads.py",
        "Kraken reads",
        "taxonomic IDs",
        "include children",
        "paired collection",
    ]
    RETURN_TYPES = ("FASTA", "FASTA", "DIRECTORY")
    RETURN_NAMES = ("forward_reads", "reverse_reads", "paired_reads")
    REQUIRED_EXECUTABLES = ["extract_kraken_reads.py", "gzip"]
    DOCUMENTATION_URL = "https://github.com/jenniferlu717/KrakenTools"
    CITATION_DOIS = [KRAKENTOOLS_DOI]
    CITATION_URLS = [f"{DOI_URL}{KRAKENTOOLS_DOI}"]
    CITATION_TEXT = KRAKENTOOLS_CITATION_TEXT
    VERSION = "1.2.1"
    SHELL = True

    @classmethod
    def _library_type(cls, inputs: dict[str, Any]) -> str:
        return str(inputs.get("library_type", inputs.get("type", "single")))

    @classmethod
    def _is_paired(cls, inputs: dict[str, Any]) -> bool:
        return cls._library_type(inputs) in {"paired", "paired_collection"}

    @classmethod
    def _output_ext(cls, inputs: dict[str, Any]) -> str:
        return "fastq" if inputs.get("fastq_output", False) else "fasta"

    @classmethod
    def _temp_output_name(cls, inputs: dict[str, Any], index: int) -> str:
        return f"output_{index}.{cls._output_ext(inputs)}"

    @classmethod
    def _compressed_output_name(cls, inputs: dict[str, Any], index: int) -> str:
        return f"{cls._temp_output_name(inputs, index)}.gz"

    @classmethod
    def _is_gzipped(cls, inputs: dict[str, Any], key: str, path: str) -> bool:
        ext = str(inputs.get(f"{key}_ext", "")).lower()
        return ext.endswith("gz") or path.lower().endswith(".gz")

    @classmethod
    def _paired_collection_reads(cls, inputs: dict[str, Any]) -> tuple[str, str]:
        collection = inputs.get("paired_collection", inputs.get("input_1", ""))
        if isinstance(collection, dict):
            forward = collection.get("forward", collection.get("input_1", ""))
            reverse = collection.get("reverse", collection.get("input_2", ""))
            return str(forward), str(reverse)
        if isinstance(collection, (list, tuple)) and len(collection) >= 2:
            return str(collection[0]), str(collection[1])
        if collection:
            collection_path = str(collection).rstrip("/")
            return f"{collection_path}/forward", f"{collection_path}/reverse"
        return str(inputs.get("input_1", "")), str(inputs.get("input_2", ""))

    @classmethod
    def _input_paths(cls, inputs: dict[str, Any]) -> tuple[str, str]:
        if cls._library_type(inputs) == "paired_collection":
            return cls._paired_collection_reads(inputs)
        return str(inputs.get("input_1", "")), str(inputs.get("input_2", ""))

    @classmethod
    def _linked_inputs(cls, inputs: dict[str, Any]) -> tuple[list[str], str, str]:
        input_1, input_2 = cls._input_paths(inputs)
        commands: list[str] = []
        if cls._is_gzipped(inputs, "input_1", input_1):
            commands.append(f"ln -s {shlex.quote(input_1)} input_1.gz")
            input_1 = "input_1.gz"
        if cls._is_paired(inputs) and cls._is_gzipped(inputs, "input_2", input_2):
            commands.append(f"ln -s {shlex.quote(input_2)} input_2.gz")
            input_2 = "input_2.gz"
        return commands, input_1, input_2

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        validation = super().VALIDATE_INPUTS(inputs)
        if validation is not True:
            return validation
        taxids = str(inputs.get("taxid", "")).strip().split()
        if not taxids or any(not taxid.isdigit() for taxid in taxids):
            return "Taxonomic ID(s) must be a space-separated list of numeric tax IDs"
        if (inputs.get("include_parents") or inputs.get("include_children")) and not inputs.get("report"):
            return "Report is required when including parent or child taxonomic assignments"
        return True

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> str:
        out = _out(inputs)
        commands, input_1, input_2 = cls._linked_inputs(inputs)
        cmd = [
            "extract_kraken_reads.py",
            "-k",
            str(inputs.get("results", "")),
            "-s",
            input_1,
            "-o",
            cls._temp_output_name(inputs, 1),
            "--taxid",
            *str(inputs.get("taxid", "")).strip().split(),
            "--max",
            str(inputs.get("max_reads", inputs.get("max", 100000000))),
        ]
        if inputs.get("include_parents", False):
            cmd.append("--include-parents")
        if inputs.get("include_children", False):
            cmd.append("--include-children")
        if inputs.get("exclude", False):
            cmd.append("--exclude")
        if inputs.get("fastq_output", False):
            cmd.append("--fastq-output")
        if cls._is_paired(inputs):
            cmd.extend(["-s2", input_2, "-o2", cls._temp_output_name(inputs, 2)])
        if inputs.get("include_parents", False) or inputs.get("include_children", False):
            cmd.extend(["--report", str(inputs.get("report", ""))])
        commands.append(shlex.join(cmd))

        gzip_1 = ["gzip", "-cvf", cls._temp_output_name(inputs, 1)]
        _add_shell_redirect(gzip_1, f"{out}/{cls._compressed_output_name(inputs, 1)}")
        commands.append(_shell_join(gzip_1))
        if cls._is_paired(inputs):
            gzip_2 = ["gzip", "-cvf", cls._temp_output_name(inputs, 2)]
            _add_shell_redirect(gzip_2, f"{out}/{cls._compressed_output_name(inputs, 2)}")
            commands.append(_shell_join(gzip_2))
        return " && ".join(commands)

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        out = Path(output_dir) / cls.NODE_ID
        paired_out = out / "paired_reads"
        paired_out.mkdir(parents=True, exist_ok=True)
        return [
            out / cls._compressed_output_name(inputs, 1),
            out / cls._compressed_output_name(inputs, 2),
            paired_out,
        ]

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        sequence_formats = ["fastq", "fasta", "fastq.gz", "fasta.gz"]
        return {
            "required": {
                "library_type": (
                    "STRING",
                    {
                        "default": "single",
                        "options": ["single", "paired", "paired_collection"],
                        "description": "Single, paired, or paired-collection read input mode",
                    },
                ),
                "input_1": ("FASTQ", {"description": "Single-end input or paired-end forward reads"}),
                "results": ("TSV", {"description": "Kraken, KrakenUniq, or Kraken2 classification results file"}),
                "taxid": (
                    "STRING",
                    {"description": "Space-delimited numeric taxonomy ID list used to select matching reads"},
                ),
            },
            "optional": {
                "input_2": ("FASTQ", {"default": "", "description": "Paired-end reverse reads"}),
                "paired_collection": (
                    "DIRECTORY",
                    {"default": "", "description": "Directory or collection-like value containing forward and reverse reads"},
                ),
                "report": (
                    "TSV",
                    {
                        "default": "",
                        "description": "Kraken report required when include_parents or include_children is enabled",
                    },
                ),
                "max_reads": (
                    "INT",
                    {"default": 100000000, "min": 1, "description": "Maximum number of reads to save for each taxonomic ID"},
                ),
                "exclude": (
                    "BOOLEAN",
                    {"default": False, "description": "Invert output to save reads that do not match the selected tax IDs"},
                ),
                "fastq_output": (
                    "BOOLEAN",
                    {"default": False, "description": "Write FASTQ output instead of the default FASTA output"},
                ),
                "include_parents": (
                    "BOOLEAN",
                    {"default": False, "description": "Include reads classified at parent levels of the selected tax IDs"},
                ),
                "include_children": (
                    "BOOLEAN",
                    {"default": False, "description": "Include reads classified below the selected tax IDs"},
                ),
                "input_1_ext": (
                    "STRING",
                    {"default": "fastq", "options": sequence_formats, "advanced": True},
                ),
                "input_2_ext": (
                    "STRING",
                    {"default": "fastq", "options": sequence_formats, "advanced": True},
                ),
            },
            "hidden": {"output": ("STRING", {})},
        }
