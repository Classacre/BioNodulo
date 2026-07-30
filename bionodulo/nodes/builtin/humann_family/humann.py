"""HUMAnN 3.9 functional profiling."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from bionodulo.nodes.builtin.metagenomics_family.adapter import (
    MetagenomicsCommandNode,
    add_flag,
    path_value,
    validate_choice,
    validate_int,
    validate_number,
)


class HUMAnNNode(MetagenomicsCommandNode):
    """Profile gene families and pathways using explicit reference databases."""

    #: HUMAnN MUST NOT share an environment with anything that needs bowtie2.
    #: The bioconda `humann` package vendors bowtie2 2.2.3 binaries at the SAME
    #: file paths the real `bowtie2` package owns -- `bin/bowtie2-build-s` is
    #: listed in both conda-meta records of a solved env. Whichever unpacks last
    #: wins, so an env that locks bowtie2 2.5.5 can still expose 2.2.3 on PATH.
    #: That is how `bowtie2-build --threads` died as "Encountered internal
    #: Bowtie 2 exception (#1)": `--threads` did not exist until 2.3. Confirmed
    #: by reading conda-meta in the solved env, not inferred from the symptom.
    ENVIRONMENT = {"type": "pixi", "name": "humann"}

    NODE_ID = "humann"
    DISPLAY_NAME = "HUMAnN"
    DESCRIPTION = "Profile microbial gene families and pathways from reads plus an explicit taxonomic profile."
    SEARCH_ALIASES = ["BioNodulo builtin", "HUMAnN 3", "gene families", "pathways", "functional profiling"]
    RETURN_TYPES = ("HUMANN_OUTPUT", "TSV", "TSV", "TSV", "TXT")
    RETURN_NAMES = ("output_dir", "genefamilies", "pathabundance", "pathcoverage", "log")
    REQUIRED_EXECUTABLES = ["humann"]
    # `python` is listed so the 3.12 pin in PACKAGE_MIN_VERSIONS reaches this
    # environment: the bioconda humann build targets 3.12 but does not say so.
    REQUIRED_CONDA_PACKAGES = ["humann", "python"]
    VERSION = "3.9"
    BIOCONDA_VERSION = VERSION
    BIOCONDA_CONSTRAINT = "humann=3.9"
    BIOCONDA_PACKAGE_URL = "https://anaconda.org/bioconda/humann/files?version=3.9"
    GIT_URL = "https://github.com/biobakery/humann.git"
    GIT_COMMIT = "9c6dfef873837c0ed281e1093718769d1aea98c9"
    UPSTREAM_TAG = "v3.9"
    UPSTREAM_SOURCE = "setup.py; humann/humann.py; humann/config.py; readme.md"
    SOURCE_PATHS = ("setup.py", "humann/humann.py", "humann/config.py", "readme.md")
    SOURCE_REVISION = GIT_COMMIT
    SOURCE_URL = f"{GIT_URL}/blob/{GIT_COMMIT}"
    AUDIT_STATUS = "contract-checked-no-binary-execution"
    DOCUMENTATION_URL = "https://github.com/biobakery/humann/blob/9c6dfef873837c0ed281e1093718769d1aea98c9/readme.md"
    CITATION_DOIS = ["10.7554/eLife.65088", "10.1371/journal.pcbi.1002358"]
    CITATION_URLS = [
        "https://doi.org/10.7554/eLife.65088",
        "https://doi.org/10.1371/journal.pcbi.1002358",
    ]
    CITATION_TEXT = "bioBakery 3 and the HUMAnN metabolic reconstruction framework."
    REQUIRED_PATH_INPUTS = ("input", "taxonomic_profile", "nucleotide_database", "protein_database")
    INPUT_FORMATS = ("fastq", "fastq.gz", "fasta", "fasta.gz")
    MEMORY_MODES = ("minimum", "maximum")
    SEARCH_MODES = ("uniref50", "uniref90")
    TRANSLATED_ALIGNERS = ("diamond", "rapsearch", "usearch")
    CHOCOPHLAN_RELEASE_TOKEN = "v201901_v31"
    CHOCOPHLAN_SEQUENCE_SUFFIXES = (".ffn", ".ffn.gz")
    CHOCOPHLAN_FILENAME_PREFIXES = ("g__",)
    UNIREF_RELEASE_TOKEN = "201901b"
    TRANSLATED_DATABASE_EXTENSIONS = {
        "diamond": ".dmnd",
        "rapsearch": ".info",
        "usearch": ".udb",
    }
    GENERATED_BOWTIE2_INDEX_SUFFIXES = (
        ".1.bt2",
        ".2.bt2",
        ".3.bt2",
        ".4.bt2",
        ".rev.1.bt2",
        ".rev.2.bt2",
    )
    SIDECAR_POLICY = (
        "For the raw-read contract, the nucleotide directory contains ChocoPhlAn "
        "v201901_v31 pangenome sequence members. HUMAnN merges the selected members and "
        "builds Bowtie2 indexes in its temporary output directory, so Bowtie2 index files "
        "are not input sidecars. The protein directory must contain a UniRef 201901b database "
        "formatted for the selected translated aligner (.dmnd for DIAMOND, .udb for USEARCH, "
        "or a RAPSearch basename plus .info sidecar)."
    )
    EXIT_SEMANTICS = (
        "HUMAnN exits nonzero for unreadable inputs, unavailable dependencies, incompatible databases, "
        "or output failures; BioNodulo additionally verifies the native output directory, tables, and log."
    )

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "input": (
                    "FILE",
                    {"description": "One FASTA/FASTQ file; upstream requires paired reads to be concatenated first"},
                ),
                "taxonomic_profile": (
                    "METAPHLAN_PROFILE",
                    {"description": "MetaPhlAn profile for the same sample, avoiding an implicit internal prescreen"},
                ),
                "nucleotide_database": ("DIRECTORY", {"description": "ChocoPhlAn nucleotide database directory"}),
                "protein_database": ("DIRECTORY", {"description": "UniRef translated-search database directory"}),
            },
            "optional": {
                "threads": ("INT", {"default": 1, "min": 1}),
                "input_format": ("STRING", {"options": list(cls.INPUT_FORMATS)}),
                "search_mode": ("STRING", {"options": list(cls.SEARCH_MODES)}),
                "memory_use": ("STRING", {"default": "minimum", "options": list(cls.MEMORY_MODES)}),
                "prescreen_threshold": ("FLOAT", {"default": 0.01, "min": 0.0, "max": 100.0}),
                "translated_alignment": (
                    "STRING",
                    {"default": "diamond", "options": list(cls.TRANSLATED_ALIGNERS)},
                ),
                "output_max_decimals": ("INT", {"default": 10, "min": 0}),
                "remove_temp_output": ("BOOLEAN", {"default": False}),
                "remove_stratified_output": ("BOOLEAN", {"default": False}),
                "remove_column_description_output": ("BOOLEAN", {"default": False}),
            },
            "hidden": {"output": ("STRING", {})},
        }

    @classmethod
    def results_dir(cls, inputs: dict[str, Any]) -> Path:
        return cls.output_dir(inputs) / "output"

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        node_dir = Path(output_dir) / cls.NODE_ID
        results_dir = node_dir / "output"
        return [
            results_dir,
            results_dir / "humann_genefamilies.tsv",
            results_dir / "humann_pathabundance.tsv",
            results_dir / "humann_pathcoverage.tsv",
            node_dir / "humann.log",
        ]

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        validation = super().VALIDATE_INPUTS(inputs)
        if validation is not True:
            return validation
        if inputs.get("input_format") is not None:
            validation = validate_choice(inputs["input_format"], "input_format", cls.INPUT_FORMATS)
            if validation is not True:
                return validation
        if inputs.get("search_mode") is not None:
            validation = validate_choice(inputs["search_mode"], "search_mode", cls.SEARCH_MODES)
            if validation is not True:
                return validation
        for key, value, choices in (
            ("memory_use", inputs.get("memory_use", "minimum"), cls.MEMORY_MODES),
            ("translated_alignment", inputs.get("translated_alignment", "diamond"), cls.TRANSLATED_ALIGNERS),
        ):
            validation = validate_choice(value, key, choices)
            if validation is not True:
                return validation
        for key, default, minimum in (("threads", 1, 1), ("output_max_decimals", 10, 0)):
            validation = validate_int(inputs.get(key, default), key, minimum=minimum)
            if validation is not True:
                return validation
        return validate_number(
            inputs.get("prescreen_threshold", 0.01),
            "prescreen_threshold",
            minimum=0.0,
            maximum=100.0,
        )

    @classmethod
    def _materialized_database_entries(cls, inputs: dict[str, Any], key: str, label: str) -> list[Path] | None:
        """Return a materialized database directory's direct members, if available."""

        database = Path(path_value(inputs.get(key)))
        if not database.exists():
            # Staging can materialize a declared directory after node validation.
            return None
        if not database.is_dir():
            raise ValueError(f"HUMAnN {label} database must be a directory: {database}")
        entries = sorted(database.iterdir(), key=lambda path: path.name)
        if not entries:
            raise ValueError(f"HUMAnN {label} database is empty: {database}")
        return entries

    @classmethod
    def _validate_release_members(
        cls,
        entries: list[Path],
        release_token: str,
        label: str,
    ) -> None:
        """Mirror HUMAnN's requirement that one database directory contains one release."""

        wrong_release = [entry.name for entry in entries if release_token not in entry.name]
        if wrong_release:
            raise ValueError(
                f"HUMAnN {label} database has member(s) outside required release {release_token}: "
                + ", ".join(wrong_release)
            )

    @classmethod
    def PREPARE_EXECUTION(cls, inputs: dict[str, Any], outputs: list[Path]) -> None:
        """Fail early when a staged HUMAnN database cannot satisfy the selected native mode."""

        nucleotide_entries = cls._materialized_database_entries(
            inputs,
            "nucleotide_database",
            "ChocoPhlAn nucleotide",
        )
        if nucleotide_entries is not None:
            cls._validate_release_members(
                nucleotide_entries,
                cls.CHOCOPHLAN_RELEASE_TOKEN,
                "ChocoPhlAn nucleotide",
            )
            invalid_members = [
                entry
                for entry in nucleotide_entries
                if not (
                    entry.is_file()
                    and entry.name.startswith(cls.CHOCOPHLAN_FILENAME_PREFIXES)
                    and entry.name.endswith(cls.CHOCOPHLAN_SEQUENCE_SUFFIXES)
                )
            ]
            if invalid_members:
                raise ValueError(
                    "HUMAnN ChocoPhlAn database contains non-pangenome sequence member(s); "
                    "expected release-matched g__*.ffn or g__*.ffn.gz files: "
                    + ", ".join(entry.name for entry in invalid_members)
                )

        protein_entries = cls._materialized_database_entries(
            inputs,
            "protein_database",
            "UniRef protein",
        )
        if protein_entries is None:
            return
        cls._validate_release_members(protein_entries, cls.UNIREF_RELEASE_TOKEN, "UniRef protein")
        aligner = str(inputs.get("translated_alignment", "diamond"))
        extension = cls.TRANSLATED_DATABASE_EXTENSIONS[aligner]
        formatted_members = [entry for entry in protein_entries if entry.is_file() and entry.name.endswith(extension)]
        if not formatted_members:
            raise ValueError(
                f"HUMAnN UniRef database is missing a release-matched {aligner} database member (*{extension})"
            )
        if aligner == "rapsearch":
            complete_members = [
                entry for entry in formatted_members if (entry.parent / entry.name[: -len(extension)]).is_file()
            ]
            if not complete_members:
                raise ValueError("HUMAnN RAPSearch database requires both each database basename and its .info sidecar")

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        node_dir = cls.output_dir(inputs)
        command = cls.checked_command(
            inputs,
            "humann",
            "--input",
            path_value(inputs.get("input")),
            "--output",
            str(node_dir / "output"),
            "--threads",
            str(inputs.get("threads", 1)),
            "--taxonomic-profile",
            path_value(inputs.get("taxonomic_profile")),
            "--nucleotide-database",
            path_value(inputs.get("nucleotide_database")),
            "--protein-database",
            path_value(inputs.get("protein_database")),
            "--prescreen-threshold",
            str(inputs.get("prescreen_threshold", 0.01)),
            "--memory-use",
            str(inputs.get("memory_use", "minimum")),
            "--translated-alignment",
            str(inputs.get("translated_alignment", "diamond")),
            "--output-basename",
            "humann",
            "--output-format",
            "tsv",
            "--output-max-decimals",
            str(inputs.get("output_max_decimals", 10)),
            "--o-log",
            str(node_dir / "humann.log"),
        )
        if inputs.get("input_format") is not None:
            command.extend(["--input-format", str(inputs["input_format"])])
        if inputs.get("search_mode") is not None:
            command.extend(["--search-mode", str(inputs["search_mode"])])
        add_flag(command, "--remove-temp-output", inputs.get("remove_temp_output"))
        add_flag(command, "--remove-stratified-output", inputs.get("remove_stratified_output"))
        add_flag(
            command,
            "--remove-column-description-output",
            inputs.get("remove_column_description_output"),
        )
        return command
