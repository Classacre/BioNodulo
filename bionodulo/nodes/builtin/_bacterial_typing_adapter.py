"""Shared bacterial typing contracts for final owners."""
# ruff: noqa: F403,F405
from __future__ import annotations

from bionodulo.nodes.builtin._wrapped_tool_utils import *
from bionodulo.nodes.builtin._assembly_typing_contracts import (
    TOOLS_IUC_GIT_COMMIT,
    ToolsIUCCommandContract,
)


class KleborateContractNode(ToolsIUCCommandContract):
    GIT_COMMIT = TOOLS_IUC_GIT_COMMIT
    SOURCE_URL = f"https://github.com/galaxyproject/tools-iuc/tree/{TOOLS_IUC_GIT_COMMIT}/tools/kleborate"
    GALAXY_WRAPPER_SOURCE_URL = SOURCE_URL
    GALAXY_WRAPPER_VERSION = "2.3.2+galaxy1"
    PACKAGE_CONSTRAINT = "kleborate==2.3.2; kaptive==2.0.6"


class PlasmidFinderContractNode(ToolsIUCCommandContract):
    GIT_COMMIT = TOOLS_IUC_GIT_COMMIT
    SOURCE_URL = f"https://github.com/galaxyproject/tools-iuc/tree/{TOOLS_IUC_GIT_COMMIT}/tools/plasmidfinder"
    GALAXY_WRAPPER_SOURCE_URL = SOURCE_URL
    GALAXY_WRAPPER_VERSION = "2.1.6+galaxy2"
    PACKAGE_CONSTRAINT = "plasmidfinder==2.1.6"


class StaramrContractNode(ToolsIUCCommandContract):
    GIT_COMMIT = TOOLS_IUC_GIT_COMMIT
    SOURCE_URL = f"https://github.com/galaxyproject/tools-iuc/tree/{TOOLS_IUC_GIT_COMMIT}/tools/staramr"
    GALAXY_WRAPPER_SOURCE_URL = SOURCE_URL
    GALAXY_WRAPPER_VERSION = "0.12.3+galaxy0"
    PACKAGE_CONSTRAINT = "staramr==0.12.3; mlst==2.33.1"


class _KleborateContract(KleborateContractNode):
    """Screen Klebsiella assemblies with Kleborate."""

    LEGACY_NODE_ID = "kleborate"
    DISPLAY_NAME = "Kleborate"
    REQUIRED_CONDA_PACKAGES = ["kleborate", "kaptive"]
    CATEGORY = "typing"
    DESCRIPTION = "Screen Klebsiella genome assemblies for species, MLST, virulence, resistance, and K/O loci."
    SEARCH_ALIASES = [
        BIONODULO_BUILTIN_ALIAS,
        "Kleborate",
        "kleborate",
        "Klebsiella",
        "Klebsiella pneumoniae",
        "KpSC",
        "MLST",
        "virulence score",
        "resistance score",
        "Kaptive",
        "K locus",
        "O locus",
    ]
    RETURN_TYPES = ("TSV", "TSV", "TSV", "TSV")
    RETURN_NAMES = ("concise", "full", "kaptive_k", "kaptive_o")
    REQUIRED_EXECUTABLES = ["kleborate"]
    DOCUMENTATION_URL = "https://github.com/klebgenomics/Kleborate"
    CITATION_DOIS = ["10.1038/s41467-021-24448-3", "10.1099/mgen.0.000102"]
    CITATION_URLS = [f"{DOI_URL}{doi}" for doi in CITATION_DOIS]
    CITATION_TEXT = (
        "A genomic surveillance framework and genotyping tool for Klebsiella pneumoniae and its related species complex; "
        "Kaptive: identification of Klebsiella capsule synthesis loci from whole genome data."
    )
    VERSION = "2.3.2+galaxy1"
    SHELL = True

    @classmethod
    def _assemblies(cls, inputs: dict[str, Any]) -> list[str]:
        return _as_list(inputs.get("assemblies"))

    @classmethod
    def _staged_assemblies(cls, inputs: dict[str, Any]) -> list[tuple[str, str]]:
        assemblies = cls._assemblies(inputs)
        labels = _as_list(inputs.get("assembly_labels"))
        staged: list[tuple[str, str]] = []
        for index, assembly in enumerate(assemblies):
            label = labels[index] if index < len(labels) else Path(assembly).name
            staged.append((assembly, _safe_identifier(label)))
        return staged

    @classmethod
    def _format_int(cls, inputs: dict[str, Any], key: str, default: int) -> str:
        return str(int(inputs.get(key, default) if inputs.get(key, default) not in (None, "") else default))

    @classmethod
    def _output_paths(cls, inputs: dict[str, Any]) -> dict[str, str]:
        out = _out(inputs)
        return {
            "concise": f"{out}/kleborate_concise_results.tsv",
            "full": f"{out}/kleborate_results.tsv",
            "kaptive_k": f"{out}/kleborate_kaptive_k_results.tsv",
            "kaptive_o": f"{out}/kleborate_kaptive_o_results.tsv",
        }

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> str:
        staged = cls._staged_assemblies(inputs)
        paths = cls._output_paths(inputs)
        commands = [_shell_join(["ln", "-s", source, staged_name]) for source, staged_name in staged]
        cmd = ["kleborate"]
        if inputs.get("resistance", True):
            cmd.append("--resistance")
        cmd.extend(["-o", paths["full"]])
        if inputs.get("kaptive_k"):
            cmd.extend(["--kaptive_k", "--kaptive_k_outfile", paths["kaptive_k"]])
        if inputs.get("kaptive_o"):
            cmd.extend(["--kaptive_o", "--kaptive_o_outfile", paths["kaptive_o"]])
        cmd.extend(
            [
                "--min_identity",
                cls._format_int(inputs, "min_identity", 90),
                "--min_coverage",
                cls._format_int(inputs, "min_coverage", 80),
                "--min_spurious_identity",
                cls._format_int(inputs, "min_spurious_identity", 80),
                "--min_spurious_coverage",
                cls._format_int(inputs, "min_spurious_coverage", 40),
                "--assemblies",
            ]
        )
        cmd.extend(staged_name for _, staged_name in staged)
        cmd.extend([">", paths["concise"]])
        commands.append(_shell_join(cmd))
        return " && ".join(commands)

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        out = Path(output_dir) / cls.NODE_ID
        out.mkdir(parents=True, exist_ok=True)
        outputs = [out / "kleborate_concise_results.tsv", out / "kleborate_results.tsv"]
        if inputs.get("kaptive_k"):
            outputs.append(out / "kleborate_kaptive_k_results.tsv")
        if inputs.get("kaptive_o"):
            outputs.append(out / "kleborate_kaptive_o_results.tsv")
        return outputs

    @classmethod
    def _validate_percent(cls, inputs: dict[str, Any], key: str, default: int) -> bool | str:
        try:
            value = int(inputs.get(key, default) if inputs.get(key, default) not in (None, "") else default)
        except (TypeError, ValueError):
            return f"{key} must be a number"
        if value < 0 or value > 100:
            return f"{key} must be between 0 and 100"
        return True

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        assemblies = cls._assemblies(inputs)
        if not assemblies:
            return "at least one assembly FASTA is required"
        labels = _as_list(inputs.get("assembly_labels"))
        if labels and len(labels) != len(assemblies):
            return "assembly_labels must match the number of assemblies"
        for key, default in {
            "min_identity": 90,
            "min_coverage": 80,
            "min_spurious_identity": 80,
            "min_spurious_coverage": 40,
        }.items():
            result = cls._validate_percent(inputs, key, default)
            if result is not True:
                return result
        return True

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "assemblies": (
                    "FASTA",
                    {"multiple": True, "description": "FASTA assembly file or files to screen with Kleborate"},
                ),
            },
            "optional": {
                "resistance": (
                    "BOOLEAN",
                    {"default": True, "description": "Turn on acquired resistance and resistance score screening"},
                ),
                "kaptive_k": (
                    "BOOLEAN",
                    {"default": False, "description": "Run Kaptive K-locus capsule typing"},
                ),
                "kaptive_o": (
                    "BOOLEAN",
                    {"default": False, "description": "Run Kaptive O-locus lipopolysaccharide typing"},
                ),
                "min_identity": (
                    "INT",
                    {"default": 90, "min": 0, "max": 100, "description": "Minimum alignment percent identity for main results"},
                ),
                "min_coverage": (
                    "INT",
                    {"default": 80, "min": 0, "max": 100, "description": "Minimum alignment percent coverage for main results"},
                ),
                "min_spurious_identity": (
                    "INT",
                    {"default": 80, "min": 0, "max": 100, "description": "Minimum identity for spurious hit reporting"},
                ),
                "min_spurious_coverage": (
                    "INT",
                    {"default": 40, "min": 0, "max": 100, "description": "Minimum coverage for spurious hit reporting"},
                ),
                "assembly_labels": (
                    "STRING",
                    {
                        "default": [],
                        "multiple": True,
                        "description": "Optional Galaxy element identifiers used in the output table",
                    },
                ),
            },
            "hidden": {"output": ("STRING", {})},
        }

class _PlasmidFinderContract(PlasmidFinderContractNode):
    """Identify bacterial plasmid replicons with PlasmidFinder."""

    LEGACY_NODE_ID = "plasmidfinder"
    DISPLAY_NAME = "PlasmidFinder"
    REQUIRED_CONDA_PACKAGES = ["plasmidfinder"]
    CATEGORY = "annotation"
    DESCRIPTION = "Identify plasmid replicons in bacterial assemblies or reads with PlasmidFinder."
    SEARCH_ALIASES = [
        BIONODULO_BUILTIN_ALIAS,
        "PlasmidFinder",
        "plasmidfinder",
        "plasmid identification",
        "plasmid replicon",
        "pMLST",
        "bacterial WGS",
        "replicon typing",
    ]
    RETURN_TYPES = ("JSON", "FASTA", "FASTA", "TSV", "TXT", "TXT")
    RETURN_NAMES = ("json_file", "hit_file", "plasmid_file", "result_file", "raw_file", "log_file")
    REQUIRED_EXECUTABLES = ["plasmidfinder.py"]
    DOCUMENTATION_URL = PLASMIDFINDER_DOCUMENTATION_URL
    CITATION_DOIS = [PLASMIDFINDER_CITATION_DOI]
    CITATION_URLS = [f"{DOI_URL}{PLASMIDFINDER_CITATION_DOI}"]
    CITATION_TEXT = PLASMIDFINDER_CITATION_TEXT
    VERSION = "2.1.6"
    SHELL = True

    INPUT_FORMATS = ["fasta", "fastq"]
    OUTPUT_SELECTIONS = [
        "data_json",
        "hit_fasta",
        "plasmid_fasta",
        "result_tsv",
        "result_txt",
        "logfile",
    ]
    DEFAULT_OUTPUT_SELECTIONS = ["hit_fasta", "plasmid_fasta", "result_tsv", "result_txt"]
    OUTPUT_FILES = {
        "data_json": "data.json",
        "hit_fasta": "Hit_in_genome_seq.fsa",
        "plasmid_fasta": "Plasmid_seqs.fsa",
        "result_tsv": "results_tab.tsv",
        "result_txt": "results.txt",
        "logfile": "log.txt",
    }

    @classmethod
    def _format_fraction(cls, value: Any, default: float) -> str:
        parsed = float(value if value not in (None, "") else default)
        return str(int(parsed)) if parsed.is_integer() else str(parsed)

    @classmethod
    def _output_dir(cls, inputs: dict[str, Any]) -> str:
        return f"{_out(inputs)}/output_dir"

    @classmethod
    def _temp_dir(cls, inputs: dict[str, Any]) -> str:
        return f"{_out(inputs)}/temp_dir"

    @classmethod
    def _log_path(cls, inputs: dict[str, Any]) -> str:
        return f"{_out(inputs)}/log.txt"

    @classmethod
    def _selected_outputs(cls, inputs: dict[str, Any]) -> list[str]:
        selected = _as_list(inputs.get("output_selection"))
        return selected or list(cls.DEFAULT_OUTPUT_SELECTIONS)

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> str:
        input_format = str(inputs.get("input_format", "fasta") or "fasta")
        method = "kma" if input_format == "fastq" else "blastn"
        cmd = [
            "plasmidfinder.py",
            "-i",
            str(inputs.get("input_file", "")),
            "-p",
            str(inputs.get("database", "")),
            "-l",
            cls._format_fraction(inputs.get("min_cov"), 0.6),
            "-t",
            cls._format_fraction(inputs.get("threshold"), 0.95),
            "-mp",
            method,
            "-x",
            "-o",
            cls._output_dir(inputs),
            "-tmp",
            cls._temp_dir(inputs),
        ]
        return (
            f"mkdir -p {shlex.quote(cls._output_dir(inputs))} {shlex.quote(cls._temp_dir(inputs))} && "
            f"{_shell_join(cmd)} | tee {shlex.quote(cls._log_path(inputs))}"
        )

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        out = Path(output_dir) / cls.NODE_ID
        out.mkdir(parents=True, exist_ok=True)
        return [out / cls.OUTPUT_FILES[selection] for selection in cls._selected_outputs(inputs)]

    @classmethod
    def _fraction_range(cls, inputs: dict[str, Any], name: str, default: float) -> bool | str:
        try:
            value = float(inputs.get(name, default))
        except (TypeError, ValueError):
            return f"{name} must be a number"
        if value < 0 or value > 1:
            return f"{name} must be between 0 and 1"
        return True

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        if not str(inputs.get("input_file", "")).strip():
            return "input_file is required"
        if not str(inputs.get("database", "")).strip():
            return "database is required"
        input_format = str(inputs.get("input_format", "fasta") or "fasta")
        if input_format not in cls.INPUT_FORMATS:
            return f"input_format must be one of: {', '.join(cls.INPUT_FORMATS)}"
        for name, default in [("min_cov", 0.6), ("threshold", 0.95)]:
            result = cls._fraction_range(inputs, name, default)
            if result is not True:
                return result
        invalid_outputs = [selection for selection in cls._selected_outputs(inputs) if selection not in cls.OUTPUT_SELECTIONS]
        if invalid_outputs:
            return f"output_selection values must be one of: {', '.join(cls.OUTPUT_SELECTIONS)}"
        return True

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "input_file": (
                    "FILE",
                    {"description": "FASTA assembly or FASTQ reads to scan for plasmid replicons"},
                ),
                "database": (
                    "DIRECTORY",
                    {"description": "PlasmidFinder database directory from Galaxy's plasmidfinder_database table"},
                ),
            },
            "optional": {
                "input_format": (
                    "STRING",
                    {
                        "default": "fasta",
                        "options": cls.INPUT_FORMATS,
                        "description": "Input data type; FASTA uses blastn and FASTQ uses KMA like the Galaxy wrapper",
                    },
                ),
                "min_cov": (
                    "FLOAT",
                    {
                        "default": 0.6,
                        "min": 0,
                        "max": 1,
                        "description": "Minimum fraction of target sequence covered",
                    },
                ),
                "threshold": (
                    "FLOAT",
                    {
                        "default": 0.95,
                        "min": 0,
                        "max": 1,
                        "description": "Minimum nucleotide identity fraction",
                    },
                ),
                "output_selection": (
                    "STRING_LIST",
                    {
                        "default": cls.DEFAULT_OUTPUT_SELECTIONS,
                        "options": cls.OUTPUT_SELECTIONS,
                        "multiple": True,
                        "description": "Galaxy output files to collect from the PlasmidFinder run",
                    },
                ),
            },
            "hidden": {"output": ("STRING", {})},
        }

class _StaramrSearchContract(StaramrContractNode):
    """Scan bacterial assemblies for AMR genes, point mutations, plasmids, and MLST."""

    LEGACY_NODE_ID = "staramr_search"
    DISPLAY_NAME = "staramr"
    REQUIRED_CONDA_PACKAGES = ["staramr", "mlst"]
    CATEGORY = "annotation"
    DESCRIPTION = "Scan bacterial genome assemblies against ResFinder, PointFinder, and PlasmidFinder databases with starAMR."
    SEARCH_ALIASES = [
        BIONODULO_BUILTIN_ALIAS,
        "staramr",
        "starAMR",
        "ResFinder",
        "PointFinder",
        "PlasmidFinder",
        "antimicrobial resistance",
        "AMR genes",
        "bacterial WGS",
    ]
    RETURN_TYPES = ("TSV", "TSV", "TSV", "TSV", "TSV", "TSV", "TXT", "XLSX", "DIRECTORY")
    RETURN_NAMES = (
        "mlst",
        "summary",
        "detailed_summary",
        "resfinder",
        "plasmidfinder",
        "pointfinder",
        "settings",
        "excel",
        "blast_hits",
    )
    REQUIRED_EXECUTABLES = ["staramr"]
    DOCUMENTATION_URL = STARAMR_DOCUMENTATION_URL
    CITATION_DOIS = [STARAMR_CITATION_DOI]
    CITATION_URLS = [f"{DOI_URL}{STARAMR_CITATION_DOI}"]
    CITATION_TEXT = STARAMR_CITATION_TEXT
    VERSION = "0.12.3"
    SHELL = True

    POINTFINDER_ORGANISMS = [
        "disabled",
        "campylobacter",
        "enterococcus_faecalis",
        "enterococcus_faecium",
        "escherichia_coli",
        "helicobacter_pylori",
        "salmonella",
        "klebsiella",
        "mycobacterium_tuberculosis",
        "neisseria_gonorrhoeae",
        "plasmodium_falciparum",
        "staphylococcus_aureus",
    ]
    EXCLUDE_GENE_OPTIONS = ["default", "custom", "none"]
    PLASMIDFINDER_TYPES = ["include_all", "gram_positive", "enterobacteriaceae"]
    OUTPUT_SELECTIONS = [
        "mlst_table",
        "summary_table",
        "detailed_summary_table",
        "resfinder_table",
        "plasmidfinder_table",
        "pointfinder_table",
        "settings_output",
        "excel_output",
    ]
    DEFAULT_OUTPUT_SELECTIONS = list(OUTPUT_SELECTIONS)
    OUTPUT_FILES = {
        "mlst_table": "mlst.tsv",
        "summary_table": "summary.tsv",
        "detailed_summary_table": "detailed_summary.tsv",
        "resfinder_table": "resfinder.tsv",
        "plasmidfinder_table": "plasmidfinder.tsv",
        "pointfinder_table": "pointfinder.tsv",
        "settings_output": "settings.txt",
        "excel_output": "results.xlsx",
    }
    PERCENT_OPTIONS = {
        "pid_threshold": 98.0,
        "percent_length_overlap_resfinder": 60.0,
        "percent_length_overlap_plasmidfinder": 60.0,
        "percent_length_overlap_pointfinder": 95.0,
    }
    INTEGER_OPTIONS = {
        "genome_size_lower_bound": 4000000,
        "genome_size_upper_bound": 6000000,
        "minimum_N50_value": 10000,
        "minimum_contig_length": 300,
        "unacceptable_number_contigs": 1000,
    }

    @classmethod
    def _out_dir(cls, inputs: dict[str, Any]) -> str:
        return _out(inputs)

    @classmethod
    def _selected_outputs(cls, inputs: dict[str, Any]) -> list[str]:
        selected = _as_list(inputs.get("output_selection"))
        return selected or list(cls.DEFAULT_OUTPUT_SELECTIONS)

    @classmethod
    def _format_number(cls, value: Any, default: float | int) -> str:
        parsed = float(value if value not in (None, "") else default)
        return str(int(parsed)) if parsed.is_integer() else str(parsed)

    @classmethod
    def _integer_value(cls, inputs: dict[str, Any], name: str) -> str:
        value = inputs.get(name, cls.INTEGER_OPTIONS[name])
        return str(int(value if value not in (None, "") else cls.INTEGER_OPTIONS[name]))

    @classmethod
    def _genomes(cls, inputs: dict[str, Any]) -> list[str]:
        return _as_list(inputs.get("genomes"))

    @classmethod
    def _labels(cls, inputs: dict[str, Any], genomes: list[str]) -> list[str]:
        labels = _as_list(inputs.get("genome_labels"))
        if len(labels) != len(genomes):
            return [Path(genome).stem for genome in genomes]
        return labels

    @classmethod
    def _linked_genomes(cls, inputs: dict[str, Any]) -> list[tuple[str, str]]:
        genomes = cls._genomes(inputs)
        labels = cls._labels(inputs, genomes)
        return [
            (genome, f"{_safe_element_identifier(label)}.fasta")
            for genome, label in zip(genomes, labels)
        ]

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> str:
        out = cls._out_dir(inputs)
        commands = [f"mkdir -p {shlex.quote(out)}"]
        linked_genomes = cls._linked_genomes(inputs)
        for genome, linked_name in linked_genomes:
            commands.append(f"ln -sf {shlex.quote(genome)} {shlex.quote(linked_name)}")
        commands.append("export GIT_CONFIG_COUNT=1 GIT_CONFIG_KEY_0=safe.directory GIT_CONFIG_VALUE_0='*'")

        cmd = [
            "staramr",
            "search",
            "-d",
            str(inputs.get("database", "")),
            "--nprocs",
            "${GALAXY_SLOTS:-1}",
            "--genome-size-lower-bound",
            cls._integer_value(inputs, "genome_size_lower_bound"),
            "--genome-size-upper-bound",
            cls._integer_value(inputs, "genome_size_upper_bound"),
            "--minimum-N50-value",
            cls._integer_value(inputs, "minimum_N50_value"),
            "--minimum-contig-length",
            cls._integer_value(inputs, "minimum_contig_length"),
            "--unacceptable-number-contigs",
            cls._integer_value(inputs, "unacceptable_number_contigs"),
            "--pid-threshold",
            cls._format_number(inputs.get("pid_threshold"), cls.PERCENT_OPTIONS["pid_threshold"]),
            "--percent-length-overlap-resfinder",
            cls._format_number(
                inputs.get("percent_length_overlap_resfinder"),
                cls.PERCENT_OPTIONS["percent_length_overlap_resfinder"],
            ),
            "--percent-length-overlap-plasmidfinder",
            cls._format_number(
                inputs.get("percent_length_overlap_plasmidfinder"),
                cls.PERCENT_OPTIONS["percent_length_overlap_plasmidfinder"],
            ),
            "--percent-length-overlap-pointfinder",
            cls._format_number(
                inputs.get("percent_length_overlap_pointfinder"),
                cls.PERCENT_OPTIONS["percent_length_overlap_pointfinder"],
            ),
        ]
        mlst_scheme = str(inputs.get("mlst_scheme", "auto") or "auto")
        if mlst_scheme != "auto":
            cmd.extend(["--mlst-scheme", mlst_scheme])
        for key, flag in (
            ("report_all_blast", "--report-all-blast"),
            ("exclude_negatives", "--exclude-negatives"),
            ("exclude_resistance_phenotypes", "--exclude-resistance-phenotypes"),
        ):
            if inputs.get(key):
                cmd.append(flag)
        exclude_genes_condition = str(inputs.get("exclude_genes_condition", "default") or "default")
        if exclude_genes_condition == "custom":
            cmd.extend(["--exclude-genes-file", str(inputs.get("exclude_genes_file", ""))])
        elif exclude_genes_condition == "none":
            cmd.append("--no-exclude-genes")
        if inputs.get("complex_mutations_file"):
            cmd.extend(["--complex-mutations-file", str(inputs.get("complex_mutations_file"))])
        plasmidfinder_type = str(inputs.get("plasmidfinder_type", "include_all") or "include_all")
        if plasmidfinder_type != "include_all":
            cmd.extend(["--plasmidfinder-database-type", plasmidfinder_type])

        cmd.extend([
            "--output-summary",
            f"{out}/summary.tsv",
            "--output-detailed-summary",
            f"{out}/detailed_summary.tsv",
            "--output-resfinder",
            f"{out}/resfinder.tsv",
            "--output-plasmidfinder",
            f"{out}/plasmidfinder.tsv",
            "--output-settings",
            f"{out}/settings.txt",
            "--output-excel",
            f"{out}/results.xlsx",
            "--output-mlst",
            f"{out}/mlst.tsv",
            "--output-hits-dir",
            f"{out}/staramr_hits",
        ])
        pointfinder_organism = str(inputs.get("pointfinder_organism", "disabled") or "disabled")
        if pointfinder_organism != "disabled":
            cmd.extend(["--output-pointfinder", f"{out}/pointfinder.tsv", "--pointfinder-organism", pointfinder_organism])
        cmd.extend(linked_name for _, linked_name in linked_genomes)
        commands.append(_shell_join(cmd).replace("'${GALAXY_SLOTS:-1}'", "${GALAXY_SLOTS:-1}"))
        return " && ".join(commands)

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        out = Path(output_dir) / cls.NODE_ID
        out.mkdir(parents=True, exist_ok=True)
        pointfinder_enabled = str(inputs.get("pointfinder_organism", "disabled") or "disabled") != "disabled"
        outputs = [
            out / cls.OUTPUT_FILES[selection]
            for selection in cls._selected_outputs(inputs)
            if selection != "pointfinder_table" or pointfinder_enabled
        ]
        outputs.append(out / "staramr_hits")
        return outputs

    @classmethod
    def _validate_percent(cls, inputs: dict[str, Any], name: str) -> bool | str:
        try:
            value = float(inputs.get(name, cls.PERCENT_OPTIONS[name]))
        except (TypeError, ValueError):
            return f"{name} must be a number"
        if value < 0 or value > 100:
            return f"{name} must be between 0 and 100"
        return True

    @classmethod
    def _validate_integer(cls, inputs: dict[str, Any], name: str) -> bool | str:
        try:
            value = int(inputs.get(name, cls.INTEGER_OPTIONS[name]))
        except (TypeError, ValueError):
            return f"{name} must be an integer"
        if value < 0:
            return f"{name} must be at least 0"
        return True

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        genomes = cls._genomes(inputs)
        if not genomes:
            return "at least one genome FASTA is required"
        if not str(inputs.get("database", "")).strip():
            return "database is required"
        labels = _as_list(inputs.get("genome_labels"))
        if labels and len(labels) != len(genomes):
            return "genome_labels must match the number of genomes"
        pointfinder_organism = str(inputs.get("pointfinder_organism", "disabled") or "disabled")
        if pointfinder_organism not in cls.POINTFINDER_ORGANISMS:
            return f"pointfinder_organism must be one of: {', '.join(cls.POINTFINDER_ORGANISMS)}"
        plasmidfinder_type = str(inputs.get("plasmidfinder_type", "include_all") or "include_all")
        if plasmidfinder_type not in cls.PLASMIDFINDER_TYPES:
            return f"plasmidfinder_type must be one of: {', '.join(cls.PLASMIDFINDER_TYPES)}"
        exclude_genes_condition = str(inputs.get("exclude_genes_condition", "default") or "default")
        if exclude_genes_condition not in cls.EXCLUDE_GENE_OPTIONS:
            return f"exclude_genes_condition must be one of: {', '.join(cls.EXCLUDE_GENE_OPTIONS)}"
        if exclude_genes_condition == "custom" and not str(inputs.get("exclude_genes_file", "")).strip():
            return "exclude_genes_file is required when exclude_genes_condition is custom"
        for name in cls.PERCENT_OPTIONS:
            result = cls._validate_percent(inputs, name)
            if result is not True:
                return result
        for name in cls.INTEGER_OPTIONS:
            result = cls._validate_integer(inputs, name)
            if result is not True:
                return result
        invalid_outputs = [selection for selection in cls._selected_outputs(inputs) if selection not in cls.OUTPUT_SELECTIONS]
        if invalid_outputs:
            return f"output_selection values must be one of: {', '.join(cls.OUTPUT_SELECTIONS)}"
        return True

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "genomes": ("FASTA_LIST", {"multiple": True, "description": "Genome assembly FASTA files to scan"}),
                "database": (
                    "DIRECTORY",
                    {"description": "starAMR database directory containing ResFinder, PointFinder, and PlasmidFinder data"},
                ),
            },
            "optional": {
                "pointfinder_organism": (
                    "STRING",
                    {
                        "default": "disabled",
                        "options": cls.POINTFINDER_ORGANISMS,
                        "description": "Enable PointFinder scanning for a validated or unvalidated organism",
                    },
                ),
                "pid_threshold": ("FLOAT", {"default": 98.0, "min": 0, "max": 100, "description": "BLAST percent identity threshold"}),
                "percent_length_overlap_resfinder": (
                    "FLOAT",
                    {"default": 60.0, "min": 0, "max": 100, "description": "Minimum ResFinder BLAST hit length overlap"},
                ),
                "percent_length_overlap_plasmidfinder": (
                    "FLOAT",
                    {"default": 60.0, "min": 0, "max": 100, "description": "Minimum PlasmidFinder BLAST hit length overlap"},
                ),
                "percent_length_overlap_pointfinder": (
                    "FLOAT",
                    {"default": 95.0, "min": 0, "max": 100, "description": "Minimum PointFinder BLAST hit length overlap"},
                ),
                "genome_size_lower_bound": ("INT", {"default": 4000000, "min": 0, "description": "Lower genome size bound for quality metrics"}),
                "genome_size_upper_bound": ("INT", {"default": 6000000, "min": 0, "description": "Upper genome size bound for quality metrics"}),
                "minimum_N50_value": ("INT", {"default": 10000, "min": 0, "description": "Minimum N50 value for quality metrics"}),
                "minimum_contig_length": ("INT", {"default": 300, "min": 0, "description": "Minimum contig length for quality metrics"}),
                "unacceptable_number_contigs": (
                    "INT",
                    {"default": 1000, "min": 0, "description": "Unacceptable number of contigs for quality metrics"},
                ),
                "mlst_scheme": (
                    "STRING",
                    {"default": "auto", "description": "MLST scheme name; auto lets starAMR detect the scheme"},
                ),
                "report_all_blast": ("BOOLEAN", {"default": False, "description": "Report all BLAST hits"}),
                "exclude_negatives": ("BOOLEAN", {"default": False, "description": "Exclude non-resistant phenotype results"}),
                "exclude_resistance_phenotypes": (
                    "BOOLEAN",
                    {"default": False, "description": "Exclude predicted resistance phenotype columns"},
                ),
                "exclude_genes_condition": (
                    "STRING",
                    {
                        "default": "default",
                        "options": cls.EXCLUDE_GENE_OPTIONS,
                        "description": "Use starAMR's default gene exclusion list, a custom list, or no exclusion list",
                    },
                ),
                "exclude_genes_file": (
                    "FILE",
                    {"default": "", "description": "Custom gene exclusion table used when exclude_genes_condition is custom"},
                ),
                "complex_mutations_file": (
                    "FILE",
                    {"default": "", "description": "Optional complex mutations table for PointFinder reports"},
                ),
                "plasmidfinder_type": (
                    "STRING",
                    {
                        "default": "include_all",
                        "options": cls.PLASMIDFINDER_TYPES,
                        "description": "Restrict PlasmidFinder database type or include all available types",
                    },
                ),
                "output_selection": (
                    "STRING_LIST",
                    {
                        "default": cls.DEFAULT_OUTPUT_SELECTIONS,
                        "options": cls.OUTPUT_SELECTIONS,
                        "multiple": True,
                        "description": "Galaxy output reports to collect from the starAMR run",
                    },
                ),
                "genome_labels": (
                    "STRING_LIST",
                    {
                        "default": [],
                        "multiple": True,
                        "description": "Optional labels matching genomes; used for Galaxy-style sanitized symlink names",
                    },
                ),
            },
            "hidden": {"output": ("STRING", {})},
        }
