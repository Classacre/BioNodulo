"""BioNodulo built-in wrapped tool nodes split by tool family."""
# ruff: noqa: F403,F405
from __future__ import annotations

from bionodulo.nodes.builtin._wrapped_tool_utils import *

class Beacon2ImportNode(CommandNode):
    """Import Beacon JSON documents into a Beacon MongoDB collection."""

    NODE_ID = "beacon2_import"
    DISPLAY_NAME = "Beacon2 Import"
    CATEGORY = "metadata"
    DESCRIPTION = "Import a Beacon JSON document into a Beacon MongoDB collection."
    REQUIRED_CONDA_PACKAGES = ["beacon2-import"]
    REQUIRED_EXECUTABLES = ["beacon2-import"]
    DOCUMENTATION_URL = "https://github.com/galaxyproject/tools-iuc/tree/main/tools/beacon2-import"
    CITATION_DOIS = [BEACON2_IMPORT_DOI]
    CITATION_URLS = [f"{DOI_URL}{BEACON2_IMPORT_DOI}"]
    CITATION_TEXT = BEACON2_IMPORT_CITATION_TEXT
    VERSION = "2.2.4+galaxy0"
    SHELL = True
    SEARCH_ALIASES = [
        BIONODULO_BUILTIN_ALIAS,
        "Beacon2",
        "Beacon v2",
        "beacon2_import",
        "Beacon2 Import",
        "beacon2-import",
        "Beacon JSON",
        "MongoDB import",
        "clearAll",
        "clearColl",
    ]
    RETURN_TYPES = ("TEXT",)
    RETURN_NAMES = ("out_logs",)

    @classmethod
    def _db_host(cls, inputs: dict[str, Any]) -> str:
        return str(inputs.get("db_host", "127.0.0.1") or "127.0.0.1")

    @classmethod
    def _db_port(cls, inputs: dict[str, Any]) -> int:
        return int(inputs.get("db_port", 27017) or 27017)

    @classmethod
    def _credentials_path(cls, inputs: dict[str, Any]) -> str:
        return f"{_out(inputs)}/beacon2_db_auth.json"

    @classmethod
    def _credentials_json(cls, inputs: dict[str, Any]) -> str:
        credentials = {
            "db_auth_source": str(inputs.get("db_auth_source", "admin") or "admin"),
            "db_user": str(inputs.get("db_user", "root") or "root"),
            "db_password": str(inputs.get("db_password", "example") or "example"),
        }
        return json.dumps(credentials, indent=2)

    @classmethod
    def _import_cmd(cls, inputs: dict[str, Any], credentials_path: str) -> list[str]:
        out = _out(inputs)
        cmd = [
            "beacon2-import",
            "--input_json_file",
            f"{out}/input.json",
            "--db-host",
            cls._db_host(inputs),
            "--db-port",
            str(cls._db_port(inputs)),
            "--database",
            str(inputs.get("database", "")),
            "--collection",
            str(inputs.get("collection", "")),
            "--advance-connection",
            "--db-auth-config",
            credentials_path,
        ]
        if inputs.get("clearAll"):
            cmd.append("--clearAll")
        if inputs.get("clearColl"):
            cmd.append("--clearColl")
            cmd.extend(["--removeCollection", str(inputs.get("removeCollection", ""))])
        cmd.extend([">", f"{out}/logs.txt"])
        return cmd

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> str:
        out = _out(inputs)
        input_json = str(inputs.get("input_json_file", ""))
        staged_input = f"{out}/input.json"
        credentials_path = cls._credentials_path(inputs)
        config = f"cat > {shlex.quote(credentials_path)} <<'JSON'\n{cls._credentials_json(inputs)}\nJSON\n"
        return " && ".join(
            [
                f"mkdir -p {shlex.quote(out)}",
                _shell_join(["ln", "-s", input_json, staged_input]),
                f"{config}{_shell_join(cls._import_cmd(inputs, credentials_path))}",
            ]
        )

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        out = Path(output_dir) / cls.NODE_ID
        out.mkdir(parents=True, exist_ok=True)
        return [out / "logs.txt"]

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        if not str(inputs.get("input_json_file", "")).strip():
            return "input_json_file is required"
        if not str(inputs.get("database", "")).strip():
            return "database is required"
        if not str(inputs.get("collection", "")).strip():
            return "collection is required"
        try:
            cls._db_port(inputs)
        except (TypeError, ValueError):
            return "db_port must be an integer"
        if inputs.get("clearColl") and not str(inputs.get("removeCollection", "")).strip():
            return "removeCollection is required when clearColl is enabled"
        return True

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "input_json_file": ("JSON", {"description": "Beacon JSON document to import"}),
                "database": ("STRING", {"description": "Targeted Beacon database"}),
                "collection": ("STRING", {"description": "Targeted Beacon collection in the selected database"}),
            },
            "optional": {
                "db_host": (
                    "STRING",
                    {"default": "127.0.0.1", "description": "Hostname or IP address of the Beacon MongoDB database"},
                ),
                "db_port": ("INT", {"default": 27017, "description": "Port of the Beacon MongoDB database"}),
                "db_auth_source": (
                    "STRING",
                    {"default": "admin", "advanced": True, "description": "MongoDB authentication source for Beacon2 import"},
                ),
                "db_user": (
                    "STRING",
                    {"default": "root", "advanced": True, "description": "MongoDB username for Beacon2 import"},
                ),
                "db_password": (
                    "STRING",
                    {"default": "example", "advanced": True, "description": "MongoDB password for Beacon2 import"},
                ),
                "clearAll": ("BOOLEAN", {"default": False, "description": "Delete all collections before import"}),
                "clearColl": ("BOOLEAN", {"default": False, "description": "Delete a specific collection before import"}),
                "removeCollection": ("STRING", {"default": "", "description": "Collection name to delete when clearColl is enabled"}),
            },
            "hidden": {"output": ("STRING", {})},
        }

class _Beacon2MultiInputBaseNode(CommandNode):
    """Shared command rendering for Beacon2 converters that symlink multi-input collections."""

    REQUIRED_CONDA_PACKAGES = ["beacon2-ri-tools", "gzip"]
    DOCUMENTATION_URL = "https://github.com/galaxyproject/tools-iuc/tree/main/tools/beacon2"
    CITATION_DOIS = [BEACON2_DOI]
    CITATION_URLS = [f"{DOI_URL}{BEACON2_DOI}"]
    CITATION_TEXT = BEACON2_CITATION_TEXT
    VERSION = "2.0.0+galaxy0"
    SHELL = True

    INPUT_NAME = ""

    @classmethod
    def _input_files(cls, inputs: dict[str, Any]) -> list[str]:
        return _as_list(inputs.get(cls.INPUT_NAME))

    @classmethod
    def _staged_paths(cls, inputs: dict[str, Any]) -> list[str]:
        out = _out(inputs)
        labels = _as_list(inputs.get("element_identifiers"))
        staged: list[str] = []
        for index, input_file in enumerate(cls._input_files(inputs)):
            label = labels[index] if index < len(labels) and labels[index] else input_file
            staged.append(f"{out}/{_safe_element_identifier(label)}")
        return staged

    @classmethod
    def _symlink_commands(cls, inputs: dict[str, Any]) -> list[str]:
        return [
            _shell_join(["ln", "-s", input_file, staged_path])
            for input_file, staged_path in zip(cls._input_files(inputs), cls._staged_paths(inputs), strict=False)
        ]

class Beacon2Csv2XlsxNode(_Beacon2MultiInputBaseNode):
    """Convert Beacon v2 Model CSV files into a multi-sheet XLSX template."""

    NODE_ID = "beacon2_csv2xlsx"
    DISPLAY_NAME = "Beacon2 CSV2XLSX"
    CATEGORY = "metadata"
    DESCRIPTION = "Convert Beacon v2 Model CSV files into a multi-sheet XLSX template."
    SEARCH_ALIASES = [
        BIONODULO_BUILTIN_ALIAS,
        "Beacon2",
        "Beacon v2",
        "Beacon v2 Models",
        "beacon2_csv2xlsx",
        "csv2xlsx",
        "CSV Models to XLSX",
        "Beacon-v2-Models_template",
    ]
    RETURN_TYPES = ("XLSX",)
    RETURN_NAMES = ("Beacon_v2_Models_template",)
    REQUIRED_EXECUTABLES = ["csv2xlsx"]
    INPUT_NAME = "csvs"

    @classmethod
    def _output_path(cls, inputs: dict[str, Any]) -> str:
        return f"{_out(inputs)}/Beacon-v2-Models_template.xlsx"

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> str:
        cmd = ["csv2xlsx", *cls._staged_paths(inputs), "-o", cls._output_path(inputs)]
        return " && ".join([*cls._symlink_commands(inputs), _shell_join(cmd)])

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        out = Path(output_dir) / cls.NODE_ID
        out.mkdir(parents=True, exist_ok=True)
        return [out / "Beacon-v2-Models_template.xlsx"]

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        if not cls._input_files(inputs):
            return "at least one CSV file is required"
        return True

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "csvs": (
                    "CSV",
                    {"multiple": True, "description": "Beacon v2 Model CSV files to collect into one XLSX workbook"},
                ),
            },
            "optional": {
                "element_identifiers": (
                    "STRING",
                    {
                        "default": [],
                        "multiple": True,
                        "description": "Optional Galaxy element identifiers used as staged CSV filenames",
                    },
                ),
            },
            "hidden": {"output": ("STRING", {})},
        }

class Beacon2Pxf2BffNode(_Beacon2MultiInputBaseNode):
    """Combine Phenopacket JSON files into Beacon Friendly Format JSON."""

    NODE_ID = "beacon2_pxf2bff"
    DISPLAY_NAME = "Beacon2 PXF2BFF"
    CATEGORY = "metadata"
    DESCRIPTION = "Combine Phenopacket JSON files into Beacon Friendly Format JSON."
    SEARCH_ALIASES = [
        BIONODULO_BUILTIN_ALIAS,
        "Beacon2",
        "Beacon v2",
        "beacon2_pxf2bff",
        "pxf2bff",
        "Phenopacket",
        "Phenopacket JSON",
        "Beacon Friendly Format",
        "individuals.json",
    ]
    RETURN_TYPES = ("JSON",)
    RETURN_NAMES = ("BFF_JSON_File",)
    REQUIRED_EXECUTABLES = ["pxf2bff"]
    INPUT_NAME = "input"

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> str:
        cmd = ["pxf2bff"]
        for staged_path in cls._staged_paths(inputs):
            cmd.extend(["-i", staged_path])
        cmd.extend(["-o", _out(inputs)])
        return " && ".join([*cls._symlink_commands(inputs), _shell_join(cmd)])

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        out = Path(output_dir) / cls.NODE_ID
        out.mkdir(parents=True, exist_ok=True)
        return [out / "individuals.json"]

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        if not cls._input_files(inputs):
            return "at least one Phenopacket JSON file is required"
        return True

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "input": (
                    "JSON",
                    {"multiple": True, "description": "Phenopacket JSON files to combine into Beacon Friendly Format"},
                ),
            },
            "optional": {
                "element_identifiers": (
                    "STRING",
                    {
                        "default": [],
                        "multiple": True,
                        "description": "Optional Galaxy element identifiers used as staged JSON filenames",
                    },
                ),
            },
            "hidden": {"output": ("STRING", {})},
        }

class Beacon2Vcf2BffNode(CommandNode):
    """Convert annotated VCF files to Beacon v2 genomic variations JSON."""

    NODE_ID = "beacon2_vcf2bff"
    DISPLAY_NAME = "Beacon2 VCF2BFF"
    REQUIRED_CONDA_PACKAGES = ["beacon2-ri-tools", "gzip"]
    CATEGORY = "variant"
    DESCRIPTION = "Convert annotated VCF files to Beacon v2 genomic variations JSON."
    SEARCH_ALIASES = [
        BIONODULO_BUILTIN_ALIAS,
        "Beacon2",
        "Beacon v2",
        "beacon2_vcf2bff",
        "vcf2bff.pl",
        "annotated VCF",
        "Beacon Friendly Format",
        "genomicVariations",
        "genomicVariationsVcf",
    ]
    RETURN_TYPES = ("JSON",)
    RETURN_NAMES = ("genomicVariationsVcf",)
    REQUIRED_EXECUTABLES = ["vcf2bff.pl", "gunzip"]
    DOCUMENTATION_URL = "https://github.com/galaxyproject/tools-iuc/tree/main/tools/beacon2"
    CITATION_DOIS = [BEACON2_DOI]
    CITATION_URLS = [f"{DOI_URL}{BEACON2_DOI}"]
    CITATION_TEXT = BEACON2_CITATION_TEXT
    VERSION = "2.0.0+galaxy0"
    SHELL = True

    FORMATS = ["bff", "hash", "json"]

    @classmethod
    def _format(cls, inputs: dict[str, Any]) -> str:
        return str(inputs.get("format", "bff") or "bff")

    @classmethod
    def _staged_input(cls, inputs: dict[str, Any]) -> str:
        return f"{_out(inputs)}/sample.vcf.gz"

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> str:
        out = _out(inputs)
        staged_input = cls._staged_input(inputs)
        setup = _shell_join(["ln", "-s", str(inputs.get("input", "")), staged_input])
        cmd = [
            "vcf2bff.pl",
            "--input",
            staged_input,
            "--format",
            cls._format(inputs),
            "--project-dir",
            out,
            "--dataset-id",
            str(inputs.get("dataset_id", "")),
            "--genome",
            str(inputs.get("genome", "")),
        ]
        return f"{setup} && {_shell_join(cmd)} && {_shell_join(['gunzip', f'{out}/genomicVariationsVcf.json.gz'])}"

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        out = Path(output_dir) / cls.NODE_ID
        out.mkdir(parents=True, exist_ok=True)
        return [out / "genomicVariationsVcf.json"]

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        if not str(inputs.get("input", "")).strip():
            return "input VCF.GZ is required"
        output_format = cls._format(inputs)
        if output_format not in cls.FORMATS:
            return f"format must be one of: {', '.join(cls.FORMATS)}"
        return True

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "input": ("FILE", {"description": "Annotated compressed VCF produced by bcftools, SnpEff, or SnpSift"}),
            },
            "optional": {
                "format": (
                    "STRING",
                    {
                        "default": "bff",
                        "options": cls.FORMATS,
                        "description": "Beacon2 output representation requested from vcf2bff.pl",
                    },
                ),
                "dataset_id": (
                    "STRING",
                    {"default": "", "description": "Dataset ID assigned to generated genomic variations records"},
                ),
                "genome": (
                    "STRING",
                    {"default": "", "description": "Reference genome label used to annotate the VCF, such as hs37 or hg38"},
                ),
            },
            "hidden": {"output": ("STRING", {})},
        }

class QQManhattanNode(CommandNode):
    """Create a GWAS Manhattan plot with qqman."""

    NODE_ID = "qq_manhattan"
    DISPLAY_NAME = "Manhattan Plots"
    REQUIRED_CONDA_PACKAGES = ["r-qqman", "r-optparse"]
    CATEGORY = "visualization"
    DESCRIPTION = "Create a GWAS Manhattan plot PDF from a tabular association-results file."
    SEARCH_ALIASES = [
        BIONODULO_BUILTIN_ALIAS,
        "qqman",
        "qq_manhattan",
        "Manhattan Plots",
        "GWAS Manhattan plot",
        "association results",
        "genome-wide association study",
        "SNP p-values",
    ]
    RETURN_TYPES = ("PDF",)
    RETURN_NAMES = ("manhattan",)
    REQUIRED_EXECUTABLES = ["Rscript"]
    DOCUMENTATION_URL = "https://cran.r-project.org/package=qqman"
    CITATION_DOIS = QQMAN_CITATION_DOIS
    CITATION_URLS = [f"{DOI_URL}{doi}" for doi in QQMAN_CITATION_DOIS]
    CITATION_TEXT = QQMAN_CITATION_TEXT
    VERSION = "0.1.0"
    SHELL = True

    COLUMN_DEFAULTS = {
        "pval": "P",
        "chr": "CHR",
        "bp": "BP",
        "snp": "SNP",
        "name": "Manhattan Plot",
    }

    @classmethod
    def _param(cls, inputs: dict[str, Any], name: str) -> str:
        return str(inputs.get(name, cls.COLUMN_DEFAULTS[name]) or cls.COLUMN_DEFAULTS[name])

    @classmethod
    def _output_path(cls, inputs: dict[str, Any]) -> str:
        return f"{_out(inputs)}/manhattan.pdf"

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> str:
        cmd = [
            "Rscript",
            str(inputs.get("script_path", "manhattan.R")),
            "--file",
            str(inputs.get("data", "")),
            "--pval",
            cls._param(inputs, "pval"),
            "--chr",
            cls._param(inputs, "chr"),
            "--bp",
            cls._param(inputs, "bp"),
            "--snp",
            cls._param(inputs, "snp"),
            "--name",
            cls._param(inputs, "name"),
        ]
        return f"{_shell_join(cmd)} && {_shell_join(['mv', 'manhattan.pdf', cls._output_path(inputs)])}"

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        out = Path(output_dir) / cls.NODE_ID
        out.mkdir(parents=True, exist_ok=True)
        return [out / "manhattan.pdf"]

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        if not str(inputs.get("data", "")).strip():
            return "data is required"
        for name, label in (
            ("pval", "pval column name"),
            ("chr", "chr column name"),
            ("bp", "bp column name"),
            ("snp", "snp column name"),
            ("name", "plot title"),
        ):
            if name in inputs and not str(inputs.get(name, "")).strip():
                return f"{label} is required"
        return True

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "data": ("TSV", {"description": "Tabular GWAS association results with SNP, chromosome, position, and p-value columns"}),
            },
            "optional": {
                "pval": (
                    "STRING",
                    {"default": "P", "description": "P-value column name in the input file"},
                ),
                "chr": (
                    "STRING",
                    {"default": "CHR", "description": "Chromosome column name in the input file"},
                ),
                "bp": (
                    "STRING",
                    {"default": "BP", "description": "Base-pair coordinate column name in the input file"},
                ),
                "snp": (
                    "STRING",
                    {"default": "SNP", "description": "SNP identifier column name in the input file"},
                ),
                "name": (
                    "STRING",
                    {"default": "Manhattan Plot", "description": "Plot title"},
                ),
                "script_path": (
                    "FILE",
                    {"default": "manhattan.R", "advanced": True, "description": "Path to the Galaxy qqman R wrapper script"},
                ),
            },
            "hidden": {"output": ("STRING", {})},
        }

class HeinzVisualizationNode(CommandNode):
    """Render a Heinz optimal scoring subnetwork as a PDF graph."""

    NODE_ID = "heinz_visualization"
    DISPLAY_NAME = "Visualize Heinz subnetwork"
    REQUIRED_CONDA_PACKAGES = ["graphviz", "py-graphviz", "fonts-conda-ecosystem"]
    CATEGORY = "visualization"
    DESCRIPTION = "Render a Heinz optimal scoring subnetwork DOT output as a PDF graph."
    SEARCH_ALIASES = [
        BIONODULO_BUILTIN_ALIAS,
        "Heinz",
        "heinz_visualization",
        "Visualize Heinz subnetwork",
        "optimal scoring subnetwork",
        "DOT graph",
        "Graphviz",
        "subnetwork PDF",
    ]
    RETURN_TYPES = ("PDF",)
    RETURN_NAMES = ("visualization",)
    REQUIRED_EXECUTABLES = ["python"]
    DOCUMENTATION_URL = "https://github.com/galaxyproject/tools-iuc/tree/main/tools/heinz"
    CITATION_DOIS = HEINZ_CITATION_DOIS
    CITATION_URLS = [f"{DOI_URL}{doi}" for doi in HEINZ_CITATION_DOIS]
    CITATION_TEXT = HEINZ_CITATION_TEXT
    VERSION = "0.1.1"
    SHELL = True

    @classmethod
    def _output_path(cls, inputs: dict[str, Any]) -> str:
        return f"{_out(inputs)}/visualization.pdf"

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> str:
        cmd = [
            "python",
            str(inputs.get("script_path", "visualization.py")),
            "-i",
            str(inputs.get("subnetwork", "")),
            "-o",
            cls._output_path(inputs),
        ]
        return _shell_join(cmd)

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        out = Path(output_dir) / cls.NODE_ID
        out.mkdir(parents=True, exist_ok=True)
        return [out / "visualization.pdf"]

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        if not str(inputs.get("subnetwork", "")).strip():
            return "subnetwork is required"
        return True

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "subnetwork": (
                    "FILE",
                    {"description": "Raw Heinz optimal scoring subnetwork output containing DOT graph content"},
                ),
            },
            "optional": {
                "script_path": (
                    "FILE",
                    {"default": "visualization.py", "advanced": True, "description": "Path to the Galaxy Heinz visualization script"},
                ),
            },
            "hidden": {"output": ("STRING", {})},
        }

class HeinzNode(CommandNode):
    """Identify an optimal scoring subnetwork with Heinz."""

    NODE_ID = "heinz"
    DISPLAY_NAME = "Identify optimal scoring subnetwork"
    REQUIRED_CONDA_PACKAGES = ["heinz"]
    CATEGORY = "statistics"
    DESCRIPTION = "Identify an optimal scoring subnetwork from Heinz score and edge files."
    SEARCH_ALIASES = [
        BIONODULO_BUILTIN_ALIAS,
        "Heinz",
        "heinz",
        "optimal scoring subnetwork",
        "protein-protein interaction networks",
        "functional modules",
        "score file",
        "edge file",
    ]
    RETURN_TYPES = ("TXT",)
    RETURN_NAMES = ("subnetwork",)
    REQUIRED_EXECUTABLES = ["heinz"]
    DOCUMENTATION_URL = "https://github.com/ls-cwi/heinz"
    CITATION_DOIS = [HEINZ_CITATION_DOIS[0]]
    CITATION_URLS = [f"{DOI_URL}{HEINZ_CITATION_DOIS[0]}"]
    CITATION_TEXT = "Heinz identifies optimal scoring subnetworks in protein-protein interaction networks."
    VERSION = "1.0"
    SHELL = True

    @classmethod
    def _output_path(cls, inputs: dict[str, Any]) -> str:
        return f"{_out(inputs)}/subnetwork.txt"

    @classmethod
    def _threads_arg(cls, inputs: dict[str, Any]) -> str:
        if "threads" not in inputs or inputs.get("threads") in (None, ""):
            return "${GALAXY_SLOTS:-2}"
        return str(inputs.get("threads"))

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> str:
        threads = cls._threads_arg(inputs)
        cmd = ["heinz", "-m"]
        if threads == "${GALAXY_SLOTS:-2}":
            cmd_text = f"{_shell_join(cmd)} {threads}"
        else:
            cmd_text = _shell_join([*cmd, threads])
        cmd_text = " ".join(
            [
                cmd_text,
                _shell_join(["-n", str(inputs.get("score", "")), "-e", str(inputs.get("edge", ""))]),
            ]
        )
        return f"{cmd_text} > {shlex.quote(cls._output_path(inputs))}"

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        out = Path(output_dir) / cls.NODE_ID
        out.mkdir(parents=True, exist_ok=True)
        return [out / "subnetwork.txt"]

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        if not str(inputs.get("score", "")).strip():
            return "score is required"
        if not str(inputs.get("edge", "")).strip():
            return "edge is required"
        if "threads" in inputs and inputs.get("threads") not in (None, ""):
            try:
                threads = int(inputs["threads"])
            except (TypeError, ValueError):
                return "threads must be an integer"
            if threads <= 0:
                return "threads must be greater than 0"
        return True

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "score": (
                    "TXT",
                    {"description": "Two-column Heinz score file with node identifier and score"},
                ),
                "edge": (
                    "TXT",
                    {"description": "Two-column edge list defining the background network"},
                ),
            },
            "optional": {
                "threads": (
                    "INT",
                    {"default": 2, "min": 1, "description": "Worker count passed to heinz -m"},
                ),
            },
            "hidden": {"output": ("STRING", {})},
        }

class HeinzScoringNode(CommandNode):
    """Calculate per-node Heinz scores from p-values and BUM parameters."""

    NODE_ID = "heinz_scoring"
    DISPLAY_NAME = "Calculate a Heinz score"
    REQUIRED_CONDA_PACKAGES = ["pandas", "numpy"]
    CATEGORY = "statistics"
    DESCRIPTION = "Calculate Heinz node scores from p-values and BUM model parameters."
    SEARCH_ALIASES = [
        BIONODULO_BUILTIN_ALIAS,
        "Heinz",
        "heinz_scoring",
        "Calculate a Heinz score",
        "Heinz score",
        "BUM model",
        "Beta-Uniform Mixture",
        "p-value scoring",
        "node p-values",
    ]
    RETURN_TYPES = ("TXT",)
    RETURN_NAMES = ("score",)
    REQUIRED_EXECUTABLES = ["python"]
    DOCUMENTATION_URL = "https://github.com/galaxyproject/tools-iuc/tree/main/tools/heinz"
    CITATION_DOIS = HEINZ_CITATION_DOIS
    CITATION_URLS = [f"{DOI_URL}{doi}" for doi in HEINZ_CITATION_DOIS]
    CITATION_TEXT = HEINZ_CITATION_TEXT
    VERSION = "1.0"
    SHELL = True
    INPUT_TYPE_OPTIONS = ["bum_output", "bum_type"]

    @classmethod
    def _output_path(cls, inputs: dict[str, Any]) -> str:
        return f"{_out(inputs)}/score.txt"

    @staticmethod
    def _format_float(value: Any, default: float) -> str:
        if value in (None, ""):
            value = default
        return f"{float(value):g}"

    @staticmethod
    def _validate_float(value: Any, name: str, default: float) -> tuple[float, str] | str:
        if value in (None, ""):
            value = default
        try:
            return float(value), f"{float(value):g}"
        except (TypeError, ValueError):
            return f"{name} must be a number"

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> str:
        cmd = [
            "python",
            str(inputs.get("script_path", "heinz_scoring.py")),
            "-n",
            str(inputs.get("node", "")),
            "-f",
            cls._format_float(inputs.get("FDR"), 0.5),
            "-o",
            cls._output_path(inputs),
        ]
        if str(inputs.get("input_type_selector", "bum_output")) == "bum_type":
            cmd.extend(
                [
                    "-l",
                    cls._format_float(inputs.get("lambda_param"), 0.5),
                    "-a",
                    cls._format_float(inputs.get("alpha"), 0.5),
                ]
            )
        else:
            cmd.extend(["-m", str(inputs.get("input_bum", ""))])
        return _shell_join(cmd)

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        out = Path(output_dir) / cls.NODE_ID
        out.mkdir(parents=True, exist_ok=True)
        return [out / "score.txt"]

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        if not str(inputs.get("node", "")).strip():
            return "node is required"

        fdr = cls._validate_float(inputs.get("FDR"), "FDR", 0.5)
        if isinstance(fdr, str):
            return fdr
        if fdr[0] <= 0 or fdr[0] >= 1:
            return "FDR must be greater than 0 and less than 1"

        input_type_selector = str(inputs.get("input_type_selector", "bum_output") or "bum_output")
        if input_type_selector not in cls.INPUT_TYPE_OPTIONS:
            return f"input_type_selector must be one of: {', '.join(cls.INPUT_TYPE_OPTIONS)}"
        if input_type_selector == "bum_output":
            if not str(inputs.get("input_bum", "")).strip():
                return "input_bum is required when input_type_selector is bum_output"
            return True

        lam = cls._validate_float(inputs.get("lambda_param"), "lambda_param", 0.5)
        if isinstance(lam, str):
            return lam
        if lam[0] < 0 or lam[0] > 1:
            return "lambda_param must be between 0 and 1"

        alpha = cls._validate_float(inputs.get("alpha"), "alpha", 0.5)
        if isinstance(alpha, str):
            return alpha
        if alpha[0] < 0 or alpha[0] >= 1:
            return "alpha must be greater than or equal to 0 and less than 1"
        return True

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "node": (
                    "TXT",
                    {"description": "Two-column text file containing node identifiers and p-values"},
                ),
            },
            "optional": {
                "FDR": (
                    "FLOAT",
                    {"default": 0.5, "min": 0, "max": 1, "description": "False discovery rate used to calculate the score threshold"},
                ),
                "input_type_selector": (
                    "STRING",
                    {
                        "default": "bum_output",
                        "options": cls.INPUT_TYPE_OPTIONS,
                        "description": "Choose whether BUM parameters come from a BUM output file or manual values",
                    },
                ),
                "input_bum": (
                    "TXT",
                    {"default": "", "description": "BUM model output with lambda on the first line and alpha on the second"},
                ),
                "lambda_param": (
                    "FLOAT",
                    {"default": 0.5, "min": 0, "max": 1, "description": "Manual BUM lambda parameter"},
                ),
                "alpha": (
                    "FLOAT",
                    {"default": 0.5, "min": 0, "max": 1, "description": "Manual BUM alpha parameter"},
                ),
                "script_path": (
                    "FILE",
                    {
                        "default": "heinz_scoring.py",
                        "advanced": True,
                        "description": "Path to the Galaxy Heinz scoring Python wrapper script",
                    },
                ),
            },
            "hidden": {"output": ("STRING", {})},
        }

class HeinzBumNode(CommandNode):
    """Fit a Beta-Uniform Mixture model to p-values with BioNet."""

    NODE_ID = "heinz_bum"
    DISPLAY_NAME = "Fit a BUM model"
    REQUIRED_CONDA_PACKAGES = ["bioconductor-bionet", "r-getopt"]
    CATEGORY = "statistics"
    DESCRIPTION = "Fit a Beta-Uniform Mixture model to a one-column p-value distribution."
    SEARCH_ALIASES = [
        BIONODULO_BUILTIN_ALIAS,
        "Heinz",
        "BioNet",
        "heinz_bum",
        "BUM model",
        "Beta-Uniform Mixture",
        "p-value distribution",
        "fitBumModel",
    ]
    RETURN_TYPES = ("TXT",)
    RETURN_NAMES = ("dist_params",)
    REQUIRED_EXECUTABLES = ["Rscript"]
    DOCUMENTATION_URL = "https://bioconductor.org/packages/BioNet"
    CITATION_DOIS = HEINZ_BUM_CITATION_DOIS
    CITATION_URLS = [f"{DOI_URL}{doi}" for doi in HEINZ_BUM_CITATION_DOIS]
    CITATION_TEXT = HEINZ_BUM_CITATION_TEXT
    VERSION = "1.0"
    SHELL = True

    @classmethod
    def _output_path(cls, inputs: dict[str, Any]) -> str:
        return f"{_out(inputs)}/dist_params.txt"

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> str:
        cmd = [
            "Rscript",
            str(inputs.get("script_path", "bum.R")),
            "--input",
            str(inputs.get("p_values", "")),
            "--output",
            cls._output_path(inputs),
        ]
        return _shell_join(cmd)

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        out = Path(output_dir) / cls.NODE_ID
        out.mkdir(parents=True, exist_ok=True)
        return [out / "dist_params.txt"]

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        if not str(inputs.get("p_values", "")).strip():
            return "p_values is required"
        return True

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "p_values": (
                    "FILE",
                    {"description": "Text file containing one p-value per line"},
                ),
            },
            "optional": {
                "script_path": (
                    "FILE",
                    {"default": "bum.R", "advanced": True, "description": "Path to the Galaxy Heinz BUM R wrapper script"},
                ),
            },
            "hidden": {"output": ("STRING", {})},
        }

class Brew3rRNode(CommandNode):
    """Extend GTF annotations at 3' ends with BREW3R.r."""

    NODE_ID = "brew3r_r"
    DISPLAY_NAME = "BREW3R.r"
    REQUIRED_CONDA_PACKAGES = ["bioconductor-brew3r.r", "bioconductor-rtracklayer", "r-getopt"]
    CATEGORY = "annotation"
    DESCRIPTION = "Extend GTF annotations at 3' ends with another GTF while preventing new gene overlaps."
    SEARCH_ALIASES = [
        BIONODULO_BUILTIN_ALIAS,
        "BREW3R.r",
        "brew3r_r",
        "extend GTF",
        "GTF extension",
        "3-prime exon extension",
        "StringTie annotation extension",
    ]
    RETURN_TYPES = ("GTF", "TSV")
    RETURN_NAMES = ("output", "output_table")
    REQUIRED_EXECUTABLES = ["Rscript"]
    DOCUMENTATION_URL = BREW3R_R_CITATION_URL
    CITATION_URLS = [BREW3R_R_CITATION_URL]
    CITATION_TEXT = BREW3R_R_CITATION_TEXT
    VERSION = "1.0.2+galaxy1"
    SHELL = True

    @classmethod
    def _output_path(cls, inputs: dict[str, Any]) -> str:
        return f"{_out(inputs)}/output.gtf"

    @classmethod
    def _table_path(cls, inputs: dict[str, Any]) -> str:
        return f"{_out(inputs)}/output_table.tsv"

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> str:
        cmd = [
            "Rscript",
            str(inputs.get("script_path", "brew3r.r_script.R")),
            "--gtf_to_extend",
            str(inputs.get("gtf_to_extend", "")),
            "--gtf_to_overlap",
            str(inputs.get("gtf_to_overlap", "")),
        ]
        if inputs.get("sup_output", False):
            cmd.extend(["--sup_output", cls._table_path(inputs)])
        if inputs.get("no_add", False):
            cmd.append("--no_add")
        _add_if_value(cmd, "--exclude_pattern", inputs.get("exclude_pattern"))
        if inputs.get("filter_unstranded", False):
            cmd.append("--filter_unstranded")
        cmd.extend(["-o", cls._output_path(inputs)])
        return _shell_join(cmd)

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        out = Path(output_dir) / cls.NODE_ID
        out.mkdir(parents=True, exist_ok=True)
        outputs = [out / "output.gtf"]
        if inputs.get("sup_output", False):
            outputs.append(out / "output_table.tsv")
        return outputs

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        if not str(inputs.get("gtf_to_extend", "")).strip():
            return "gtf_to_extend is required"
        if not str(inputs.get("gtf_to_overlap", "")).strip():
            return "gtf_to_overlap is required"
        for key in ("sup_output", "no_add", "filter_unstranded"):
            value = inputs.get(key)
            if value is not None and not isinstance(value, bool):
                return f"{key} must be a boolean"
        if any(quote in str(inputs.get("exclude_pattern", "")) for quote in ("'", '"')):
            return "exclude_pattern must not contain quotes"
        return True

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "gtf_to_extend": ("GTF", {"description": "Input GTF annotation to extend at 3' ends"}),
                "gtf_to_overlap": ("GTF", {"description": "Template GTF annotation used to extend the input"}),
            },
            "optional": {
                "sup_output": (
                    "BOOLEAN",
                    {"default": False, "description": "Write a supplementary overlap-resolution table"},
                ),
                "no_add": ("BOOLEAN", {"default": False, "description": "Do not add new exons"}),
                "exclude_pattern": (
                    "STRING",
                    {"default": "", "description": "Regular-expression pattern for gene names that should not be extended"},
                ),
                "filter_unstranded": (
                    "BOOLEAN",
                    {
                        "default": False,
                        "description": "Filter unstranded template intervals that overlap genes on both strands",
                    },
                ),
                "script_path": (
                    "FILE",
                    {
                        "default": "brew3r.r_script.R",
                        "advanced": True,
                        "description": "Path to the Galaxy BREW3R.r R wrapper script",
                    },
                ),
            },
            "hidden": {"output": ("STRING", {})},
        }

class _UcscSingleFileUtilityNode(CommandNode):
    """Shared behavior for single-input UCSC Genome Browser utilities."""

    CATEGORY = "genomics"
    RETURN_TYPES = ("FILE",)
    RETURN_NAMES = ("out",)
    DOCUMENTATION_URL = ""
    CITATION_DOIS = [UCSC_UTILS_CITATION_DOI]
    CITATION_URLS = [f"{DOI_URL}{UCSC_UTILS_CITATION_DOI}"]
    CITATION_TEXT = UCSC_UTILS_CITATION_TEXT
    VERSION = "482+galaxy0"
    TOOL_NAME = ""
    INPUT_NAME = ""
    OUTPUT_FILENAME = ""
    INPUT_DESCRIPTION = ""

    @classmethod
    def _output_path(cls, inputs: dict[str, Any]) -> str:
        return f"{_out(inputs)}/{cls.OUTPUT_FILENAME}"

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> str:
        return _shell_join([cls.TOOL_NAME, str(inputs.get(cls.INPUT_NAME, "")), cls._output_path(inputs)])

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        out = Path(output_dir) / cls.NODE_ID
        out.mkdir(parents=True, exist_ok=True)
        return [out / cls.OUTPUT_FILENAME]

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        if not str(inputs.get(cls.INPUT_NAME, "")).strip():
            return f"{cls.INPUT_NAME} is required"
        return True

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                cls.INPUT_NAME: ("FILE", {"description": cls.INPUT_DESCRIPTION}),
            },
            "hidden": {"output": ("STRING", {})},
        }

class UcscChainSwapNode(_UcscSingleFileUtilityNode):
    """Swap target and query sequences in a UCSC chain file."""

    NODE_ID = "ucsc_chainswap"
    DISPLAY_NAME = "chainSwap"
    REQUIRED_CONDA_PACKAGES = ["ucsc-chainswap"]
    DESCRIPTION = "Swap target and query sequences in a UCSC chain alignment file."
    SEARCH_ALIASES = [
        BIONODULO_BUILTIN_ALIAS,
        "UCSC Genome Browser Utilities",
        "ucsc_chainswap",
        "chainSwap",
        "chain file",
        "UCSC chain",
        "swap target query",
    ]
    REQUIRED_EXECUTABLES = ["chainSwap"]
    DOCUMENTATION_URL = "https://genome.ucsc.edu/goldenPath/help/chain.html"
    TOOL_NAME = "chainSwap"
    INPUT_NAME = "in_chain"
    OUTPUT_FILENAME = "out.chain"
    INPUT_DESCRIPTION = "UCSC chain alignment file whose target and query coordinates should be swapped"

class UcscChainSortNode(_UcscSingleFileUtilityNode):
    """Sort records in a UCSC chain file."""

    NODE_ID = "ucsc_chainsort"
    DISPLAY_NAME = "chainSort"
    REQUIRED_CONDA_PACKAGES = ["ucsc-chainsort"]
    DESCRIPTION = "Sort UCSC chain alignment records by score, target start, or query start."
    SEARCH_ALIASES = [
        BIONODULO_BUILTIN_ALIAS,
        "UCSC Genome Browser Utilities",
        "ucsc_chainsort",
        "chainSort",
        "chain file",
        "UCSC chain",
        "sort chains",
        "target start",
        "query start",
    ]
    REQUIRED_EXECUTABLES = ["chainSort"]
    DOCUMENTATION_URL = "https://genome.ucsc.edu/goldenPath/help/chain.html"
    TOOL_NAME = "chainSort"
    INPUT_NAME = "in_chain"
    OUTPUT_FILENAME = "out.chain"
    INPUT_DESCRIPTION = "UCSC chain alignment file to sort"
    SORT_MODES = ["", "-target", "-query"]

    @classmethod
    def _sort_by(cls, inputs: dict[str, Any]) -> str:
        return str(inputs.get("sort_by", "") or "")

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> str:
        cmd = [cls.TOOL_NAME, str(inputs.get(cls.INPUT_NAME, ""))]
        if sort_by := cls._sort_by(inputs):
            cmd.append(sort_by)
        cmd.append(cls._output_path(inputs))
        return _shell_join(cmd)

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        required = super().VALIDATE_INPUTS(inputs)
        if required is not True:
            return required
        sort_by = cls._sort_by(inputs)
        if sort_by not in cls.SORT_MODES:
            return f"sort_by must be one of: {', '.join(cls.SORT_MODES)}"
        return True

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                cls.INPUT_NAME: ("FILE", {"description": cls.INPUT_DESCRIPTION}),
            },
            "optional": {
                "sort_by": (
                    "STRING",
                    {
                        "default": "",
                        "options": cls.SORT_MODES,
                        "description": "Sort chains by score, target start, or query start",
                    },
                ),
            },
            "hidden": {"output": ("STRING", {})},
        }

class UcscNetSyntenicNode(_UcscSingleFileUtilityNode):
    """Add synteny annotations to a UCSC net file."""

    NODE_ID = "ucsc_netsyntenic"
    DISPLAY_NAME = "netSyntenic"
    REQUIRED_CONDA_PACKAGES = ["ucsc-netsyntenic"]
    DESCRIPTION = "Add synteny information to a UCSC net alignment file."
    SEARCH_ALIASES = [
        BIONODULO_BUILTIN_ALIAS,
        "UCSC Genome Browser Utilities",
        "ucsc_netsyntenic",
        "netSyntenic",
        "net file",
        "UCSC net",
        "synteny info",
    ]
    REQUIRED_EXECUTABLES = ["netSyntenic"]
    DOCUMENTATION_URL = "https://genome.ucsc.edu/goldenPath/help/net.html"
    TOOL_NAME = "netSyntenic"
    INPUT_NAME = "in_net"
    OUTPUT_FILENAME = "out.ucsc.net"
    INPUT_DESCRIPTION = "UCSC net alignment file to annotate with synteny information"

class UcscNetChainSubsetNode(CommandNode):
    """Extract the subset of chains referenced by a UCSC net file."""

    NODE_ID = "ucsc_netchainsubset"
    DISPLAY_NAME = "netChainSubset"
    REQUIRED_CONDA_PACKAGES = ["ucsc-netchainsubset"]
    CATEGORY = "genomics"
    DESCRIPTION = "Create a UCSC chain file containing only chains that appear in a net file."
    SEARCH_ALIASES = [
        BIONODULO_BUILTIN_ALIAS,
        "UCSC Genome Browser Utilities",
        "ucsc_netchainsubset",
        "netChainSubset",
        "UCSC net",
        "UCSC chain",
        "liftOver",
        "chain subset",
    ]
    RETURN_TYPES = ("FILE",)
    RETURN_NAMES = ("out",)
    REQUIRED_EXECUTABLES = ["netChainSubset"]
    DOCUMENTATION_URL = "https://genome.ucsc.edu/goldenPath/help/net.html"
    CITATION_DOIS = [UCSC_UTILS_CITATION_DOI]
    CITATION_URLS = [f"{DOI_URL}{UCSC_UTILS_CITATION_DOI}"]
    CITATION_TEXT = UCSC_UTILS_CITATION_TEXT
    VERSION = "482+galaxy0"

    FLAG_INPUTS = (
        ("splitOnInsert", "-splitOnInsert"),
        ("wholeChains", "-wholeChains"),
        ("skipMissing", "-skipMissing"),
    )

    @classmethod
    def _output_path(cls, inputs: dict[str, Any]) -> str:
        return f"{_out(inputs)}/out.chain"

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> str:
        cmd = [
            "netChainSubset",
            str(inputs.get("in_net", "")),
            str(inputs.get("in_chain", "")),
            cls._output_path(inputs),
        ]
        for name, flag in cls.FLAG_INPUTS:
            if inputs.get(name):
                cmd.append(flag)
        return _shell_join(cmd)

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        out = Path(output_dir) / cls.NODE_ID
        out.mkdir(parents=True, exist_ok=True)
        return [out / "out.chain"]

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        if not str(inputs.get("in_net", "")).strip():
            return "in_net is required"
        if not str(inputs.get("in_chain", "")).strip():
            return "in_chain is required"
        return True

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "in_net": ("FILE", {"description": "UCSC net file identifying chains to keep"}),
                "in_chain": ("FILE", {"description": "UCSC chain file to subset"}),
            },
            "optional": {
                "splitOnInsert": (
                    "BOOLEAN",
                    {"default": False, "description": "Split chains when an insertion of another chain is encountered"},
                ),
                "wholeChains": (
                    "BOOLEAN",
                    {"default": False, "description": "Write entire referenced chains instead of splitting high-level nets"},
                ),
                "skipMissing": (
                    "BOOLEAN",
                    {"default": False, "description": "Skip chains that are not found instead of failing"},
                ),
            },
            "hidden": {"output": ("STRING", {})},
        }

class UcscNetFilterNode(CommandNode):
    """Filter a UCSC net file."""

    NODE_ID = "ucsc_netfilter"
    DISPLAY_NAME = "netFilter"
    REQUIRED_CONDA_PACKAGES = ["ucsc-netfilter"]
    CATEGORY = "genomics"
    DESCRIPTION = "Filter out parts of a UCSC net alignment file."
    SEARCH_ALIASES = [
        BIONODULO_BUILTIN_ALIAS,
        "UCSC Genome Browser Utilities",
        "ucsc_netfilter",
        "netFilter",
        "UCSC net",
        "net file",
        "synteny filter",
        "minimum gap",
    ]
    RETURN_TYPES = ("FILE",)
    RETURN_NAMES = ("out",)
    REQUIRED_EXECUTABLES = ["netFilter"]
    DOCUMENTATION_URL = "https://genome.ucsc.edu/goldenPath/help/net.html"
    CITATION_DOIS = [UCSC_UTILS_CITATION_DOI]
    CITATION_URLS = [f"{DOI_URL}{UCSC_UTILS_CITATION_DOI}"]
    CITATION_TEXT = UCSC_UTILS_CITATION_TEXT
    VERSION = "482+galaxy0"

    SYN_FILTERS = ["skipsyn", "filtersyn"]
    SYN_TYPES = ["-syn", "-chimpSyn", "-nonsyn"]
    NONNEGATIVE_THRESHOLDS = ("minSynSize", "minSynAli", "minGap")

    @classmethod
    def _output_path(cls, inputs: dict[str, Any]) -> str:
        return f"{_out(inputs)}/out.ucsc.net"

    @classmethod
    def _syn_filter(cls, inputs: dict[str, Any]) -> str:
        return str(inputs.get("syn_filter", "skipsyn") or "skipsyn")

    @classmethod
    def _syn_type(cls, inputs: dict[str, Any]) -> str:
        return str(inputs.get("syntype", "-syn") or "-syn")

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> str:
        cmd = ["netFilter", str(inputs.get("in_net", ""))]
        if cls._syn_filter(inputs) == "filtersyn":
            cmd.append(cls._syn_type(inputs))
            for name in ("minSynScore", "minSynSize", "minSynAli"):
                if str(inputs.get(name, "")) != "":
                    cmd.append(f"-{name}={inputs.get(name)}")
        if str(inputs.get("minGap", "")) != "":
            cmd.append(f"-minGap={inputs.get('minGap')}")
        return f"{_shell_join(cmd)} > {shlex.quote(cls._output_path(inputs))}"

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        out = Path(output_dir) / cls.NODE_ID
        out.mkdir(parents=True, exist_ok=True)
        return [out / "out.ucsc.net"]

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        if not str(inputs.get("in_net", "")).strip():
            return "in_net is required"
        syn_filter = cls._syn_filter(inputs)
        if syn_filter not in cls.SYN_FILTERS:
            return f"syn_filter must be one of: {', '.join(cls.SYN_FILTERS)}"
        syntype = cls._syn_type(inputs)
        if syntype not in cls.SYN_TYPES:
            return f"syntype must be one of: {', '.join(cls.SYN_TYPES)}"
        for name in cls.NONNEGATIVE_THRESHOLDS:
            value = inputs.get(name, "")
            if str(value) != "" and int(value) < 0:
                return f"{name} must be greater than or equal to 0"
        return True

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "in_net": ("FILE", {"description": "UCSC net alignment file to filter"}),
            },
            "optional": {
                "syn_filter": (
                    "STRING",
                    {
                        "default": "skipsyn",
                        "options": cls.SYN_FILTERS,
                        "description": "Enable synteny-based filtering",
                    },
                ),
                "syntype": (
                    "STRING",
                    {
                        "default": "-syn",
                        "options": cls.SYN_TYPES,
                        "description": "Synteny filter mode used when synteny filtering is enabled",
                    },
                ),
                "minSynScore": (
                    "INT",
                    {"default": "", "description": "Minimum syntenic block score"},
                ),
                "minSynSize": (
                    "INT",
                    {"default": "", "min": 0, "description": "Minimum syntenic block size"},
                ),
                "minSynAli": (
                    "INT",
                    {"default": "", "min": 0, "description": "Minimum syntenic alignment size"},
                ),
                "minGap": (
                    "INT",
                    {"default": "", "min": 0, "description": "Minimum gap size to keep"},
                ),
            },
            "hidden": {"output": ("STRING", {})},
        }

class UcscChainPreNetNode(CommandNode):
    """Remove chains unlikely to be netted."""

    NODE_ID = "ucsc_chainprenet"
    DISPLAY_NAME = "chainPreNet"
    REQUIRED_CONDA_PACKAGES = ["ucsc-chainprenet"]
    CATEGORY = "genomics"
    DESCRIPTION = "Remove UCSC chains that do not have a chance of being netted."
    SEARCH_ALIASES = [
        BIONODULO_BUILTIN_ALIAS,
        "UCSC Genome Browser Utilities",
        "ucsc_chainprenet",
        "chainPreNet",
        "UCSC chain",
        "UCSC net",
        "netted chains",
        "chrom sizes",
        "haplotype pseudochromosomes",
    ]
    RETURN_TYPES = ("FILE",)
    RETURN_NAMES = ("out",)
    REQUIRED_EXECUTABLES = ["chainPreNet"]
    DOCUMENTATION_URL = "https://genome.ucsc.edu/goldenPath/help/chain.html"
    CITATION_DOIS = [UCSC_UTILS_CITATION_DOI]
    CITATION_URLS = [f"{DOI_URL}{UCSC_UTILS_CITATION_DOI}"]
    CITATION_TEXT = UCSC_UTILS_CITATION_TEXT
    VERSION = "482+galaxy0"

    REFERENCE_SOURCE_OPTIONS = ["cached", "history"]

    @classmethod
    def _output_path(cls, inputs: dict[str, Any]) -> str:
        return f"{_out(inputs)}/out.chain"

    @classmethod
    def _source(cls, inputs: dict[str, Any], prefix: str) -> str:
        return str(inputs.get(f"{prefix}_reference_index_source_selector", "history") or "history")

    @classmethod
    def _index_path(cls, inputs: dict[str, Any], prefix: str) -> str:
        source = cls._source(inputs, prefix)
        if prefix == "target":
            return str(inputs.get("tar_ref_index_path" if source == "cached" else "in_tar_ref_index", ""))
        return str(inputs.get("que_ref_index_path" if source == "cached" else "in_que_ref_index", ""))

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> str:
        cmd = [
            "chainPreNet",
            str(inputs.get("in_chain", "")),
            cls._index_path(inputs, "target"),
            cls._index_path(inputs, "query"),
            cls._output_path(inputs),
        ]
        if str(inputs.get("pad", "")) != "":
            cmd.append(f"-pad={inputs.get('pad')}")
        if inputs.get("inclHap"):
            cmd.append("-inclHap")
        return _shell_join(cmd)

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        out = Path(output_dir) / cls.NODE_ID
        out.mkdir(parents=True, exist_ok=True)
        return [out / "out.chain"]

    @classmethod
    def _validate_index(cls, inputs: dict[str, Any], prefix: str) -> bool | str:
        selector_name = f"{prefix}_reference_index_source_selector"
        source = cls._source(inputs, prefix)
        if source not in cls.REFERENCE_SOURCE_OPTIONS:
            return f"{selector_name} must be one of: {', '.join(cls.REFERENCE_SOURCE_OPTIONS)}"
        if prefix == "target":
            required_name = "tar_ref_index_path" if source == "cached" else "in_tar_ref_index"
        else:
            required_name = "que_ref_index_path" if source == "cached" else "in_que_ref_index"
        if not cls._index_path(inputs, prefix).strip():
            return f"{required_name} is required"
        return True

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        if not str(inputs.get("in_chain", "")).strip():
            return "in_chain is required"
        for prefix in ("target", "query"):
            index_validation = cls._validate_index(inputs, prefix)
            if index_validation is not True:
                return index_validation
        if str(inputs.get("pad", "")) != "" and int(inputs.get("pad")) < 0:
            return "pad must be greater than or equal to 0"
        return True

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "in_chain": ("FILE", {"description": "UCSC chain alignment file to pre-filter before netting"}),
            },
            "optional": {
                "target_reference_index_source_selector": (
                    "STRING",
                    {
                        "default": "history",
                        "options": cls.REFERENCE_SOURCE_OPTIONS,
                        "description": "Use a cached or history target genome index",
                    },
                ),
                "in_tar_ref_index": (
                    "FILE",
                    {"description": "History target chrom sizes or FASTA index file"},
                ),
                "tar_ref_index_path": (
                    "STRING",
                    {"default": "", "description": "Path to cached target chrom sizes or FASTA index file"},
                ),
                "query_reference_index_source_selector": (
                    "STRING",
                    {
                        "default": "history",
                        "options": cls.REFERENCE_SOURCE_OPTIONS,
                        "description": "Use a cached or history query genome index",
                    },
                ),
                "in_que_ref_index": (
                    "FILE",
                    {"description": "History query chrom sizes or FASTA index file"},
                ),
                "que_ref_index_path": (
                    "STRING",
                    {"default": "", "description": "Path to cached query chrom sizes or FASTA index file"},
                ),
                "pad": (
                    "INT",
                    {"default": "", "min": 0, "description": "Extra bases to pad around blocks to decrease trash"},
                ),
                "inclHap": (
                    "BOOLEAN",
                    {"default": False, "description": "Include query sequences named *_hap* or *_alt*"},
                ),
            },
            "hidden": {"output": ("STRING", {})},
        }

class UcscNetToAxtNode(CommandNode):
    """Convert UCSC net and chain alignments to AXT."""

    NODE_ID = "ucsc_nettoaxt"
    DISPLAY_NAME = "netToAxt"
    REQUIRED_CONDA_PACKAGES = ["ucsc-nettoaxt"]
    CATEGORY = "genomics"
    DESCRIPTION = "Convert UCSC net and chain alignments to AXT format."
    SEARCH_ALIASES = [
        BIONODULO_BUILTIN_ALIAS,
        "UCSC Genome Browser Utilities",
        "ucsc_nettoaxt",
        "netToAxt",
        "UCSC net",
        "UCSC chain",
        "net to AXT",
        "pairwise alignment",
    ]
    RETURN_TYPES = ("FILE",)
    RETURN_NAMES = ("out",)
    REQUIRED_EXECUTABLES = ["netToAxt"]
    DOCUMENTATION_URL = "https://genome.ucsc.edu/goldenPath/help/axt.html"
    CITATION_DOIS = [UCSC_UTILS_CITATION_DOI]
    CITATION_URLS = [f"{DOI_URL}{UCSC_UTILS_CITATION_DOI}"]
    CITATION_TEXT = UCSC_UTILS_CITATION_TEXT
    VERSION = "482+galaxy0"

    @classmethod
    def _output_path(cls, inputs: dict[str, Any]) -> str:
        return f"{_out(inputs)}/out.axt"

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> str:
        cmd = [
            "netToAxt",
            str(inputs.get("in_net", "")),
            str(inputs.get("in_chain", "")),
            str(inputs.get("in_target", "")),
            str(inputs.get("in_query", "")),
            cls._output_path(inputs),
        ]
        if inputs.get("qChain"):
            cmd.append("-qChain")
        if str(inputs.get("maxGap", "")) != "":
            cmd.append(f"-maxGap={inputs.get('maxGap')}")
        if inputs.get("noSplit"):
            cmd.append("-noSplit")
        return _shell_join(cmd)

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        out = Path(output_dir) / cls.NODE_ID
        out.mkdir(parents=True, exist_ok=True)
        return [out / "out.axt"]

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        for name in ("in_net", "in_chain", "in_target", "in_query"):
            if not str(inputs.get(name, "")).strip():
                return f"{name} is required"
        if str(inputs.get("maxGap", "")) != "" and int(inputs.get("maxGap")) < 0:
            return "maxGap must be greater than or equal to 0"
        return True

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "in_net": ("FILE", {"description": "UCSC net alignment file"}),
                "in_chain": ("FILE", {"description": "UCSC chain alignment file"}),
                "in_target": ("FILE", {"description": "TwoBit file containing the target sequence"}),
                "in_query": ("FILE", {"description": "TwoBit file containing the query sequence"}),
            },
            "optional": {
                "qChain": (
                    "BOOLEAN",
                    {"default": False, "description": "Treat the net as being with respect to the query side of chains"},
                ),
                "maxGap": (
                    "INT",
                    {"default": "", "min": 0, "description": "Maximum gap size before breaking alignment blocks"},
                ),
                "noSplit": (
                    "BOOLEAN",
                    {"default": False, "description": "Do not split chains at insertions of another chain"},
                ),
            },
            "hidden": {"output": ("STRING", {})},
        }

class UcscTwoBitToFaNode(CommandNode):
    """Convert UCSC TwoBit sequence files to FASTA."""

    NODE_ID = "ucsc-twobittofa"
    DISPLAY_NAME = "twoBitToFa"
    REQUIRED_CONDA_PACKAGES = ["ucsc-twobittofa"]
    CATEGORY = "genomics"
    DESCRIPTION = "Convert all or part of a TwoBit sequence file to FASTA."
    SEARCH_ALIASES = [
        BIONODULO_BUILTIN_ALIAS,
        "UCSC Genome Browser Utilities",
        "ucsc-twobittofa",
        "twoBitToFa",
        "TwoBit",
        "2bit to FASTA",
        "sequence range",
        "seqList",
    ]
    RETURN_TYPES = ("FASTA",)
    RETURN_NAMES = ("fasta_output",)
    REQUIRED_EXECUTABLES = ["twoBitToFa"]
    DOCUMENTATION_URL = "https://genome.ucsc.edu/goldenpath/help/twoBit.html"
    CITATION_DOIS = [UCSC_UTILS_CITATION_DOI]
    CITATION_URLS = [f"{DOI_URL}{UCSC_UTILS_CITATION_DOI}"]
    CITATION_TEXT = UCSC_UTILS_CITATION_TEXT
    VERSION = "482"

    @classmethod
    def _output_path(cls, inputs: dict[str, Any]) -> str:
        return f"{_out(inputs)}/fasta_output.fa"

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> str:
        cmd = [
            "twoBitToFa",
            str(inputs.get("twobit_input", "")),
            cls._output_path(inputs),
        ]
        if str(inputs.get("seq", "")) != "":
            cmd.append(f"-seq={inputs.get('seq')}")
        if str(inputs.get("start", "")) != "":
            cmd.append(f"-start={inputs.get('start')}")
        if str(inputs.get("end", "")) != "":
            cmd.append(f"-end={inputs.get('end')}")
        if str(inputs.get("seqList", "")) != "":
            cmd.append(f"-seqList={inputs.get('seqList')}")
        if inputs.get("noMask"):
            cmd.append("-noMask")
        return _shell_join(cmd)

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        out = Path(output_dir) / cls.NODE_ID
        out.mkdir(parents=True, exist_ok=True)
        return [out / "fasta_output.fa"]

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        if not str(inputs.get("twobit_input", "")).strip():
            return "twobit_input is required"
        for name in ("start", "end"):
            value = inputs.get(name, "")
            if str(value) != "" and int(value) < 0:
                return f"{name} must be greater than or equal to 0"
        if str(inputs.get("start", "")) != "" and str(inputs.get("end", "")) != "":
            if int(inputs.get("end")) < int(inputs.get("start")):
                return "end must be greater than or equal to start"
        if str(inputs.get("seq", "")) != "" and str(inputs.get("seqList", "")) != "":
            return "seq and seqList cannot both be set"
        return True

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "twobit_input": ("FILE", {"description": "Input UCSC TwoBit sequence file"}),
            },
            "optional": {
                "seq": (
                    "STRING",
                    {"default": "", "description": "Restrict conversion to one sequence name"},
                ),
                "start": (
                    "INT",
                    {"default": "", "min": 0, "description": "Zero-based start position within the selected sequence"},
                ),
                "end": (
                    "INT",
                    {"default": "", "min": 0, "description": "Non-inclusive end position within the selected sequence"},
                ),
                "seqList": (
                    "FILE",
                    {"description": "Text file with sequence names or seqSpec:start-end ranges to extract"},
                ),
                "noMask": (
                    "BOOLEAN",
                    {"default": False, "description": "Convert masked sequence to uppercase"},
                ),
            },
            "hidden": {"output": ("STRING", {})},
        }

class UcscWigToBigWigNode(CommandNode):
    """Convert Wiggle or bedGraph data to bigWig."""

    NODE_ID = "ucsc_wigtobigwig"
    DISPLAY_NAME = "wigtobigwig"
    REQUIRED_CONDA_PACKAGES = ["ucsc-wigtobigwig", "grep"]
    CATEGORY = "genomics"
    DESCRIPTION = "Convert bedGraph or Wiggle data to an indexed bigWig track."
    SEARCH_ALIASES = [
        BIONODULO_BUILTIN_ALIAS,
        "UCSC Genome Browser Utilities",
        "ucsc_wigtobigwig",
        "wigtobigwig",
        "wigToBigWig",
        "bigWig",
        "bedGraph",
        "Wiggle",
        "genome browser track",
    ]
    RETURN_TYPES = ("BIGWIG",)
    RETURN_NAMES = ("out_file1",)
    REQUIRED_EXECUTABLES = ["grep", "wigToBigWig"]
    DOCUMENTATION_URL = "https://genome.ucsc.edu/goldenPath/help/bigWig.html"
    CITATION_DOIS = [BBG_TO_BIGWIG_CITATION_DOI]
    CITATION_URLS = [f"{DOI_URL}{BBG_TO_BIGWIG_CITATION_DOI}"]
    CITATION_TEXT = BBG_TO_BIGWIG_CITATION_TEXT
    VERSION = "482+galaxy0"

    GENOME_SOURCE_OPTIONS = ["indexed", "history"]
    SETTINGS_OPTIONS = ["preset", "full"]

    @classmethod
    def _output_path(cls, inputs: dict[str, Any]) -> str:
        return f"{_out(inputs)}/out_file1.bw"

    @classmethod
    def _trackless_path(cls, inputs: dict[str, Any]) -> str:
        return f"{_out(inputs)}/trackless"

    @classmethod
    def _genome_source(cls, inputs: dict[str, Any]) -> str:
        return str(inputs.get("genome_type_select", "indexed") or "indexed")

    @classmethod
    def _settings_type(cls, inputs: dict[str, Any]) -> str:
        return str(inputs.get("settingsType", "preset") or "preset")

    @classmethod
    def _chrom_sizes(cls, inputs: dict[str, Any]) -> str:
        if cls._genome_source(inputs) == "history":
            return str(inputs.get("chromfile", ""))
        return str(inputs.get("index_len_path", ""))

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> str:
        out_dir = _out(inputs)
        trackless = cls._trackless_path(inputs)
        setup = _shell_join(["mkdir", "-p", out_dir])
        strip = f"grep -v '^track' {shlex.quote(str(inputs.get('input1', '')))} > {shlex.quote(trackless)}"
        cmd = [
            "wigToBigWig",
            trackless,
            cls._chrom_sizes(inputs),
            cls._output_path(inputs),
        ]
        if cls._settings_type(inputs) == "full":
            cmd.append(f"-blockSize={inputs.get('blockSize', 256)}")
            cmd.append(f"-itemsPerSlot={inputs.get('itemsPerSlot', 1024)}")
            if inputs.get("clip", True):
                cmd.append("-clip")
            if inputs.get("unc"):
                cmd.append("-unc")
        else:
            cmd.append("-clip")
        return f"{setup} && {strip} && {_shell_join(cmd)}"

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        out = Path(output_dir) / cls.NODE_ID
        out.mkdir(parents=True, exist_ok=True)
        return [out / "out_file1.bw"]

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        if not str(inputs.get("input1", "")).strip():
            return "input1 is required"
        genome_source = cls._genome_source(inputs)
        if genome_source not in cls.GENOME_SOURCE_OPTIONS:
            return f"genome_type_select must be one of: {', '.join(cls.GENOME_SOURCE_OPTIONS)}"
        if not cls._chrom_sizes(inputs).strip():
            return "chromfile is required" if genome_source == "history" else "index_len_path is required"
        settings_type = cls._settings_type(inputs)
        if settings_type not in cls.SETTINGS_OPTIONS:
            return f"settingsType must be one of: {', '.join(cls.SETTINGS_OPTIONS)}"
        if settings_type == "full":
            for name, default in (("blockSize", 256), ("itemsPerSlot", 1024)):
                value = inputs.get(name, default)
                if int(value) < 1:
                    return f"{name} must be greater than or equal to 1"
        return True

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "input1": ("FILE", {"description": "Wiggle or bedGraph file to convert"}),
            },
            "optional": {
                "genome_type_select": (
                    "STRING",
                    {
                        "default": "indexed",
                        "options": cls.GENOME_SOURCE_OPTIONS,
                        "description": "Use built-in genome lengths or a chromosome length file from history",
                    },
                ),
                "index_len_path": (
                    "STRING",
                    {"default": "", "description": "Path to cached chromosome length file for the selected genome build"},
                ),
                "chromfile": (
                    "FILE",
                    {"description": "Chromosome length file for a history reference genome"},
                ),
                "settingsType": (
                    "STRING",
                    {
                        "default": "preset",
                        "options": cls.SETTINGS_OPTIONS,
                        "description": "Use default converter settings or expose the full parameter list",
                    },
                ),
                "blockSize": (
                    "INT",
                    {"default": 256, "min": 1, "description": "Items to bundle in the R-tree"},
                ),
                "itemsPerSlot": (
                    "INT",
                    {"default": 1024, "min": 1, "description": "Data points bundled at the lowest level"},
                ),
                "clip": (
                    "BOOLEAN",
                    {"default": True, "description": "Warn and clip items beyond chromosome ends instead of failing"},
                ),
                "unc": (
                    "BOOLEAN",
                    {"default": False, "description": "Write an uncompressed bigWig file"},
                ),
            },
            "hidden": {"output": ("STRING", {})},
        }

class UcscAxtToMafNode(CommandNode):
    """Convert UCSC AXT alignments to MAF."""

    NODE_ID = "ucsc_axtomaf"
    DISPLAY_NAME = "axtToMaf"
    REQUIRED_CONDA_PACKAGES = ["ucsc-axttomaf"]
    CATEGORY = "genomics"
    DESCRIPTION = "Convert UCSC AXT pairwise alignments to MAF format."
    SEARCH_ALIASES = [
        BIONODULO_BUILTIN_ALIAS,
        "UCSC Genome Browser Utilities",
        "ucsc_axtomaf",
        "axtToMaf",
        "AXT to MAF",
        "multiple alignment format",
        "pairwise alignment",
        "chrom sizes",
    ]
    RETURN_TYPES = ("FILE",)
    RETURN_NAMES = ("out",)
    REQUIRED_EXECUTABLES = ["axtToMaf"]
    DOCUMENTATION_URL = "https://genome.ucsc.edu/FAQ/FAQformat.html#format5"
    CITATION_DOIS = [UCSC_UTILS_CITATION_DOI]
    CITATION_URLS = [f"{DOI_URL}{UCSC_UTILS_CITATION_DOI}"]
    CITATION_TEXT = UCSC_UTILS_CITATION_TEXT
    VERSION = "482+galaxy1"

    REFERENCE_SOURCE_OPTIONS = ["cached", "history"]

    @classmethod
    def _output_path(cls, inputs: dict[str, Any]) -> str:
        return f"{_out(inputs)}/out.maf"

    @classmethod
    def _source(cls, inputs: dict[str, Any], prefix: str) -> str:
        return str(inputs.get(f"{prefix}_reference_index_source_selector", "history") or "history")

    @classmethod
    def _index_path(cls, inputs: dict[str, Any], prefix: str) -> str:
        source = cls._source(inputs, prefix)
        if prefix == "target":
            return str(inputs.get("tar_ref_index_path" if source == "cached" else "in_tar_ref_index", ""))
        return str(inputs.get("que_ref_index_path" if source == "cached" else "in_que_ref_index", ""))

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> str:
        cmd = [
            "axtToMaf",
            str(inputs.get("in_axt", "")),
            cls._index_path(inputs, "target"),
            cls._index_path(inputs, "query"),
        ]
        if str(inputs.get("t_prefix", "")) != "":
            cmd.append(f"-tPrefix={inputs.get('t_prefix')}")
        if str(inputs.get("q_prefix", "")) != "":
            cmd.append(f"-qPrefix={inputs.get('q_prefix')}")
        if inputs.get("score"):
            cmd.append("-score")
        if inputs.get("scoreZero"):
            cmd.append("-scoreZero")
        cmd.append(cls._output_path(inputs))
        return _shell_join(cmd)

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        out = Path(output_dir) / cls.NODE_ID
        out.mkdir(parents=True, exist_ok=True)
        return [out / "out.maf"]

    @classmethod
    def _validate_index(cls, inputs: dict[str, Any], prefix: str) -> bool | str:
        selector_name = f"{prefix}_reference_index_source_selector"
        source = cls._source(inputs, prefix)
        if source not in cls.REFERENCE_SOURCE_OPTIONS:
            return f"{selector_name} must be one of: {', '.join(cls.REFERENCE_SOURCE_OPTIONS)}"
        if prefix == "target":
            required_name = "tar_ref_index_path" if source == "cached" else "in_tar_ref_index"
        else:
            required_name = "que_ref_index_path" if source == "cached" else "in_que_ref_index"
        if not cls._index_path(inputs, prefix).strip():
            return f"{required_name} is required"
        return True

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        if not str(inputs.get("in_axt", "")).strip():
            return "in_axt is required"
        for prefix in ("target", "query"):
            index_validation = cls._validate_index(inputs, prefix)
            if index_validation is not True:
                return index_validation
        for name in ("t_prefix", "q_prefix"):
            if " " in str(inputs.get(name, "")):
                return f"{name} cannot contain spaces"
        return True

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "in_axt": ("FILE", {"description": "UCSC AXT pairwise alignment file"}),
            },
            "optional": {
                "target_reference_index_source_selector": (
                    "STRING",
                    {
                        "default": "history",
                        "options": cls.REFERENCE_SOURCE_OPTIONS,
                        "description": "Use a cached or history target genome index",
                    },
                ),
                "in_tar_ref_index": (
                    "FILE",
                    {"description": "History target chrom sizes or FASTA index file"},
                ),
                "tar_ref_index_path": (
                    "STRING",
                    {"default": "", "description": "Path to cached target chrom sizes or FASTA index file"},
                ),
                "query_reference_index_source_selector": (
                    "STRING",
                    {
                        "default": "history",
                        "options": cls.REFERENCE_SOURCE_OPTIONS,
                        "description": "Use a cached or history query genome index",
                    },
                ),
                "in_que_ref_index": (
                    "FILE",
                    {"description": "History query chrom sizes or FASTA index file"},
                ),
                "que_ref_index_path": (
                    "STRING",
                    {"default": "", "description": "Path to cached query chrom sizes or FASTA index file"},
                ),
                "t_prefix": (
                    "STRING",
                    {"default": "", "description": "Prefix added to target sequence names in the MAF output"},
                ),
                "q_prefix": (
                    "STRING",
                    {"default": "", "description": "Prefix added to query sequence names in the MAF output"},
                ),
                "score": (
                    "BOOLEAN",
                    {"default": False, "description": "Recalculate alignment scores"},
                ),
                "scoreZero": (
                    "BOOLEAN",
                    {"default": False, "description": "Recalculate scores only when the AXT score is zero"},
                ),
            },
            "hidden": {"output": ("STRING", {})},
        }

class UcscAxtChainNode(CommandNode):
    """Chain UCSC AXT or PSL pairwise alignments."""

    NODE_ID = "ucsc_axtchain"
    DISPLAY_NAME = "axtChain"
    REQUIRED_CONDA_PACKAGES = ["ucsc-axtchain"]
    CATEGORY = "genomics"
    DESCRIPTION = "Chain together UCSC AXT or PSL pairwise alignments into chain format."
    SEARCH_ALIASES = [
        BIONODULO_BUILTIN_ALIAS,
        "UCSC Genome Browser Utilities",
        "ucsc_axtchain",
        "axtChain",
        "chain together axt",
        "AXT chain",
        "PSL chain",
        "linear gap costs",
    ]
    RETURN_TYPES = ("FILE", "TXT")
    RETURN_NAMES = ("out", "out_details")
    REQUIRED_EXECUTABLES = ["axtChain", "gzip"]
    DOCUMENTATION_URL = "https://github.com/ucscGenomeBrowser/kent/blob/master/src/hg/mouseStuff/axtChain/axtChain.c"
    CITATION_DOIS = [UCSC_UTILS_CITATION_DOI]
    CITATION_URLS = [f"{DOI_URL}{UCSC_UTILS_CITATION_DOI}"]
    CITATION_TEXT = UCSC_UTILS_CITATION_TEXT
    VERSION = "482+galaxy2"
    SHELL = True

    ALIGNMENT_FORMATS = ["", "axt", "psl"]
    LINEAR_GAP_OPTIONS = ["loose", "medium", "linear_gap_file"]

    @classmethod
    def _output_path(cls, inputs: dict[str, Any]) -> str:
        return f"{_out(inputs)}/out.chain"

    @classmethod
    def _details_path(cls, inputs: dict[str, Any]) -> str:
        return f"{_out(inputs)}/out_details.txt"

    @classmethod
    def _alignment_format(cls, inputs: dict[str, Any]) -> str:
        selected = str(inputs.get("alignment_format", "") or "")
        if selected:
            return selected
        suffixes = [suffix.lower() for suffix in Path(str(inputs.get("in_aln", ""))).suffixes]
        if suffixes and suffixes[-1] == ".gz":
            suffixes = suffixes[:-1]
        if suffixes and suffixes[-1] in {".axt", ".psl"}:
            return suffixes[-1].lstrip(".")
        return ""

    @classmethod
    def _linear_gap(cls, inputs: dict[str, Any]) -> str:
        return str(inputs.get("linear_gap", "loose") or "loose")

    @classmethod
    def _linear_gap_value(cls, inputs: dict[str, Any]) -> str:
        if cls._linear_gap(inputs) == "linear_gap_file":
            return str(inputs.get("lineargap_input", ""))
        return cls._linear_gap(inputs)

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> str:
        cmd = ["axtChain", "-faQ", "-faT"]
        if cls._alignment_format(inputs) == "psl":
            cmd.append("-psl")
        if str(inputs.get("minScore", "")) != "":
            cmd.append(f"-minScore={inputs.get('minScore')}")
        if str(inputs.get("scoreScheme", "")) != "":
            cmd.append(f"-scoreScheme={inputs.get('scoreScheme')}")
        if inputs.get("details_output"):
            cmd.append(f"-details={cls._details_path(inputs)}")
        cmd.append(f"-linearGap={cls._linear_gap_value(inputs)}")
        command = _shell_join(cmd)
        aln = shlex.quote(str(inputs.get("in_aln", "")))
        tail = _shell_join(
            [
                str(inputs.get("in_target", "")),
                str(inputs.get("in_query", "")),
                cls._output_path(inputs),
            ]
        )
        return f"{command} <(gzip -cdfq {aln}) {tail}"

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        out = Path(output_dir) / cls.NODE_ID
        out.mkdir(parents=True, exist_ok=True)
        outputs = [out / "out.chain"]
        if inputs.get("details_output", False):
            outputs.append(out / "out_details.txt")
        return outputs

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        for name in ("in_aln", "in_target", "in_query"):
            if not str(inputs.get(name, "")).strip():
                return f"{name} is required"
        selected_format = str(inputs.get("alignment_format", "") or "")
        if selected_format not in cls.ALIGNMENT_FORMATS:
            return f"alignment_format must be one of: {', '.join(cls.ALIGNMENT_FORMATS)}"
        linear_gap = cls._linear_gap(inputs)
        if linear_gap not in cls.LINEAR_GAP_OPTIONS:
            return f"linear_gap must be one of: {', '.join(cls.LINEAR_GAP_OPTIONS)}"
        if linear_gap == "linear_gap_file" and not str(inputs.get("lineargap_input", "")).strip():
            return "lineargap_input is required when linear_gap is linear_gap_file"
        if str(inputs.get("minScore", "")) != "" and int(inputs.get("minScore")) < 0:
            return "minScore must be greater than or equal to 0"
        return True

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "in_aln": (
                    "FILE",
                    {"description": "Pairwise AXT or PSL alignments, optionally gzip-compressed"},
                ),
                "in_target": ("FASTA", {"description": "Target FASTA sequence file matching alignment target names"}),
                "in_query": ("FASTA", {"description": "Query FASTA sequence file matching alignment query names"}),
            },
            "optional": {
                "alignment_format": (
                    "STRING",
                    {
                        "default": "",
                        "options": cls.ALIGNMENT_FORMATS,
                        "description": "Alignment format override; otherwise inferred from .axt/.psl extension",
                    },
                ),
                "linear_gap": (
                    "STRING",
                    {
                        "default": "loose",
                        "options": cls.LINEAR_GAP_OPTIONS,
                        "description": "Use UCSC loose/medium linear gap costs or a custom cost file",
                    },
                ),
                "lineargap_input": (
                    "FILE",
                    {"description": "Custom tabular linear gap cost file used when linear_gap is linear_gap_file"},
                ),
                "minScore": (
                    "INT",
                    {"default": "", "min": 0, "description": "Minimum chain score to report"},
                ),
                "scoreScheme": (
                    "FILE",
                    {"description": "Optional BLASTZ-format scoring matrix"},
                ),
                "details_output": (
                    "BOOLEAN",
                    {"default": False, "description": "Write per-chain gap and scoring details"},
                ),
            },
            "hidden": {"output": ("STRING", {})},
        }

class UcscChainNetNode(CommandNode):
    """Create UCSC alignment net files from chains."""

    NODE_ID = "ucsc_chainnet"
    DISPLAY_NAME = "chainNet"
    REQUIRED_CONDA_PACKAGES = ["ucsc-chainnet"]
    CATEGORY = "genomics"
    DESCRIPTION = "Create target and query UCSC net alignment files from chain alignments."
    SEARCH_ALIASES = [
        BIONODULO_BUILTIN_ALIAS,
        "UCSC Genome Browser Utilities",
        "ucsc_chainnet",
        "chainNet",
        "UCSC chain",
        "UCSC net",
        "alignment nets",
        "target net",
        "query net",
    ]
    RETURN_TYPES = ("FILE", "FILE")
    RETURN_NAMES = ("targetNet", "queryNet")
    REQUIRED_EXECUTABLES = ["chainNet"]
    DOCUMENTATION_URL = "https://genome.ucsc.edu/goldenPath/help/net.html"
    CITATION_DOIS = [UCSC_UTILS_CITATION_DOI]
    CITATION_URLS = [f"{DOI_URL}{UCSC_UTILS_CITATION_DOI}"]
    CITATION_TEXT = UCSC_UTILS_CITATION_TEXT
    VERSION = "482+galaxy0"

    REFERENCE_SOURCE_OPTIONS = ["cached", "history"]
    NONNEGATIVE_OPTIONS = ("minSpace", "minFill", "verbose")

    @classmethod
    def _target_net_path(cls, inputs: dict[str, Any]) -> str:
        return f"{_out(inputs)}/target.net"

    @classmethod
    def _query_net_path(cls, inputs: dict[str, Any]) -> str:
        return f"{_out(inputs)}/query.net"

    @classmethod
    def _source(cls, inputs: dict[str, Any], prefix: str) -> str:
        return str(inputs.get(f"{prefix}_reference_index_source_selector", "history") or "history")

    @classmethod
    def _index_path(cls, inputs: dict[str, Any], prefix: str) -> str:
        source = cls._source(inputs, prefix)
        if prefix == "target":
            return str(inputs.get("tar_ref_index_path" if source == "cached" else "in_tar_ref_index", ""))
        return str(inputs.get("que_ref_index_path" if source == "cached" else "in_que_ref_index", ""))

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> str:
        cmd = [
            "chainNet",
            str(inputs.get("in_chain", "")),
            cls._index_path(inputs, "target"),
            cls._index_path(inputs, "query"),
            cls._target_net_path(inputs),
            cls._query_net_path(inputs),
        ]
        for name in ("minSpace", "minFill", "minScore"):
            if str(inputs.get(name, "")) != "":
                cmd.append(f"-{name}={inputs.get(name)}")
        if inputs.get("inclHap"):
            cmd.append("-inclHap")
        if str(inputs.get("verbose", "")) != "":
            cmd.append(f"-verbose={inputs.get('verbose')}")
        return _shell_join(cmd)

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        out = Path(output_dir) / cls.NODE_ID
        out.mkdir(parents=True, exist_ok=True)
        return [out / "target.net", out / "query.net"]

    @classmethod
    def _validate_index(cls, inputs: dict[str, Any], prefix: str) -> bool | str:
        selector_name = f"{prefix}_reference_index_source_selector"
        source = cls._source(inputs, prefix)
        if source not in cls.REFERENCE_SOURCE_OPTIONS:
            return f"{selector_name} must be one of: {', '.join(cls.REFERENCE_SOURCE_OPTIONS)}"
        if prefix == "target":
            required_name = "tar_ref_index_path" if source == "cached" else "in_tar_ref_index"
        else:
            required_name = "que_ref_index_path" if source == "cached" else "in_que_ref_index"
        if not cls._index_path(inputs, prefix).strip():
            return f"{required_name} is required"
        return True

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        if not str(inputs.get("in_chain", "")).strip():
            return "in_chain is required"
        for prefix in ("target", "query"):
            index_validation = cls._validate_index(inputs, prefix)
            if index_validation is not True:
                return index_validation
        for name in cls.NONNEGATIVE_OPTIONS:
            value = inputs.get(name, "")
            if str(value) != "" and int(value) < 0:
                return f"{name} must be greater than or equal to 0"
        return True

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "in_chain": ("FILE", {"description": "UCSC chain alignment file to net"}),
            },
            "optional": {
                "target_reference_index_source_selector": (
                    "STRING",
                    {
                        "default": "history",
                        "options": cls.REFERENCE_SOURCE_OPTIONS,
                        "description": "Use a cached or history target genome index",
                    },
                ),
                "in_tar_ref_index": (
                    "FILE",
                    {"description": "History target chrom sizes or FASTA index file"},
                ),
                "tar_ref_index_path": (
                    "STRING",
                    {"default": "", "description": "Path to cached target chrom sizes or FASTA index file"},
                ),
                "query_reference_index_source_selector": (
                    "STRING",
                    {
                        "default": "history",
                        "options": cls.REFERENCE_SOURCE_OPTIONS,
                        "description": "Use a cached or history query genome index",
                    },
                ),
                "in_que_ref_index": (
                    "FILE",
                    {"description": "History query chrom sizes or FASTA index file"},
                ),
                "que_ref_index_path": (
                    "STRING",
                    {"default": "", "description": "Path to cached query chrom sizes or FASTA index file"},
                ),
                "minSpace": (
                    "INT",
                    {"default": "", "min": 0, "description": "Minimum gap size to fill"},
                ),
                "minFill": (
                    "INT",
                    {"default": "", "min": 0, "description": "Minimum fill size to record"},
                ),
                "minScore": (
                    "INT",
                    {"default": "", "description": "Minimum chain score to consider"},
                ),
                "inclHap": (
                    "BOOLEAN",
                    {"default": False, "description": "Include query sequences named *_hap* or *_alt*"},
                ),
                "verbose": (
                    "INT",
                    {"default": "", "min": 0, "description": "Verbosity level"},
                ),
            },
            "hidden": {"output": ("STRING", {})},
        }

class FaSplitNode(CommandNode):
    """Split a FASTA file into multiple FASTA files."""

    NODE_ID = "fasplit"
    DISPLAY_NAME = "faSplit"
    REQUIRED_CONDA_PACKAGES = ["ucsc-fasplit"]
    CATEGORY = "genomics"
    DESCRIPTION = "Split a FASTA file into multiple FASTA files."
    SEARCH_ALIASES = [
        BIONODULO_BUILTIN_ALIAS,
        "UCSC Genome Browser Utilities",
        "fasplit",
        "faSplit",
        "split FASTA",
        "FASTA chunks",
        "by sequence name",
        "gap boundaries",
    ]
    RETURN_TYPES = ("DIRECTORY",)
    RETURN_NAMES = ("output_list",)
    REQUIRED_EXECUTABLES = ["faSplit"]
    DOCUMENTATION_URL = "https://github.com/ucscGenomeBrowser/kent/blob/master/src/utils/faSplit/faSplit.c"
    CITATION_DOIS = [UCSC_UTILS_CITATION_DOI]
    CITATION_URLS = [f"{DOI_URL}{UCSC_UTILS_CITATION_DOI}"]
    CITATION_TEXT = UCSC_UTILS_CITATION_TEXT
    VERSION = "482+galaxy0"

    SPLIT_TYPES = ["sequence", "base", "size", "byname", "about", "gap"]
    MODES_WITH_COUNT = {"sequence", "base", "size", "about", "gap"}

    @classmethod
    def _split_type(cls, inputs: dict[str, Any]) -> str:
        return str(inputs.get("split_type", "sequence") or "sequence")

    @classmethod
    def _output_dir(cls, inputs: dict[str, Any]) -> str:
        return f"{_out(inputs)}/output_list"

    @classmethod
    def _lift_path(cls, inputs: dict[str, Any]) -> str:
        return f"{_out(inputs)}/fasplit.lft"

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> str:
        split_type = cls._split_type(inputs)
        out_dir = cls._output_dir(inputs)
        cmd = ["faSplit"]
        if str(inputs.get("maxN", "")) != "" and split_type in {"size", "gap"}:
            cmd.append(f"-maxN={inputs.get('maxN')}")
        if inputs.get("oneFile") and split_type in {"size", "gap"}:
            cmd.append("-oneFile")
        if str(inputs.get("extra", "")) != "" and split_type == "size":
            cmd.append(f"-extra={inputs.get('extra')}")
        if inputs.get("lift") and split_type in {"size", "gap"}:
            cmd.append(f"-lift={cls._lift_path(inputs)}")
        if str(inputs.get("minGapSize", "")) != "" and split_type == "gap":
            cmd.append(f"-minGapSize={inputs.get('minGapSize')}")
        if inputs.get("noGapDrops") and split_type == "gap":
            cmd.append("-noGapDrops")
        if str(inputs.get("outDirDepth", "")) != "":
            cmd.append(f"-outDirDepth={inputs.get('outDirDepth')}")
        if str(inputs.get("prefixLength", "")) != "" and split_type == "byname":
            cmd.append(f"-prefixLength={inputs.get('prefixLength')}")
        cmd.extend([split_type, str(inputs.get("input", ""))])
        if split_type in cls.MODES_WITH_COUNT:
            cmd.append(str(inputs.get("count", 10)))
        cmd.append(f"{out_dir}/")
        return f"mkdir -p {shlex.quote(out_dir)} && {_shell_join(cmd)}"

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        out = Path(output_dir) / cls.NODE_ID / "output_list"
        out.mkdir(parents=True, exist_ok=True)
        return [out]

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        if not str(inputs.get("input", "")).strip():
            return "input is required"
        split_type = cls._split_type(inputs)
        if split_type not in cls.SPLIT_TYPES:
            return f"split_type must be one of: {', '.join(cls.SPLIT_TYPES)}"
        if split_type in cls.MODES_WITH_COUNT and int(inputs.get("count", 10)) < 1:
            return "count must be greater than or equal to 1"
        minimums = {
            "maxN": 0,
            "extra": 0,
            "minGapSize": 1,
            "outDirDepth": 0,
            "prefixLength": 1,
        }
        for name, minimum in minimums.items():
            value = inputs.get(name, "")
            if str(value) != "" and int(value) < minimum:
                return f"{name} must be greater than or equal to {minimum}"
        return True

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "input": ("FASTA", {"description": "FASTA file to split"}),
            },
            "optional": {
                "split_type": (
                    "STRING",
                    {
                        "default": "sequence",
                        "options": cls.SPLIT_TYPES,
                        "description": "Split by sequence records, bases, chunk size, sequence name, approximate bytes, or gap boundaries",
                    },
                ),
                "count": (
                    "INT",
                    {"default": 10, "min": 1, "description": "Number of chunks or chunk size, depending on split type"},
                ),
                "maxN": (
                    "INT",
                    {"default": "", "min": 0, "description": "Suppress size/gap pieces with more than this many Ns"},
                ),
                "oneFile": (
                    "BOOLEAN",
                    {"default": False, "description": "Write size/gap pieces into one FASTA file"},
                ),
                "extra": (
                    "INT",
                    {"default": "", "min": 0, "description": "Add overlapping bases to size-mode pieces"},
                ),
                "lift": (
                    "BOOLEAN",
                    {"default": False, "description": "Write a lift file describing how pieces reconstruct the input"},
                ),
                "minGapSize": (
                    "INT",
                    {"default": "", "min": 1, "description": "Minimum N run length considered a gap in gap mode"},
                ),
                "noGapDrops": (
                    "BOOLEAN",
                    {"default": False, "description": "Keep gap-only pieces when splitting by gap"},
                ),
                "outDirDepth": (
                    "INT",
                    {"default": "", "min": 0, "description": "Create nested numeric output directories"},
                ),
                "prefixLength": (
                    "INT",
                    {"default": "", "min": 1, "description": "Group byname output by sequence-name prefix length"},
                ),
            },
            "hidden": {"output": ("STRING", {})},
        }

class FaToVcfNode(CommandNode):
    """Convert FASTA alignments to VCF single-nucleotide differences."""

    NODE_ID = "fatovcf"
    DISPLAY_NAME = "faToVcf"
    REQUIRED_CONDA_PACKAGES = ["ucsc-fatovcf"]
    CATEGORY = "variant"
    DESCRIPTION = "Convert a FASTA alignment file to Variant Call Format single-nucleotide differences."
    SEARCH_ALIASES = [
        BIONODULO_BUILTIN_ALIAS,
        "UCSC Genome Browser Utilities",
        "fatovcf",
        "faToVcf",
        "FASTA alignment to VCF",
        "single-nucleotide diffs",
        "ambiguous bases",
        "mask sites",
    ]
    RETURN_TYPES = ("VCF",)
    RETURN_NAMES = ("out",)
    REQUIRED_EXECUTABLES = ["faToVcf"]
    DOCUMENTATION_URL = "https://github.com/ucscGenomeBrowser/kent/blob/master/src/hg/utils/faToVcf/faToVcf.c"
    CITATION_DOIS = [UCSC_UTILS_CITATION_DOI]
    CITATION_URLS = [f"{DOI_URL}{UCSC_UTILS_CITATION_DOI}"]
    CITATION_TEXT = UCSC_UTILS_CITATION_TEXT
    VERSION = "482+galaxy0"

    REFERENCE_MODES = ["", "customRef"]
    AMBIGUOUS_MODES = ["", "-ambiguousToN", "-resolveAmbiguous"]

    @classmethod
    def _reference_mode(cls, inputs: dict[str, Any]) -> str:
        return str(inputs.get("refSeq", "") or "")

    @classmethod
    def _ambiguous_mode(cls, inputs: dict[str, Any]) -> str:
        return str(inputs.get("ambiguous", "") or "")

    @classmethod
    def _staged_input_path(cls, inputs: dict[str, Any]) -> str:
        return f"{_out(inputs)}/in.fa"

    @classmethod
    def _output_path(cls, inputs: dict[str, Any]) -> str:
        return f"{_out(inputs)}/out.vcf"

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> str:
        staged_input = cls._staged_input_path(inputs)
        setup = _shell_join(["ln", "-s", str(inputs.get("in_fasta", "")), staged_input])
        cmd = ["faToVcf", staged_input, cls._output_path(inputs)]
        if cls._reference_mode(inputs) == "customRef":
            cmd.append(f"-ref={inputs.get('ref', '')}")
        if ambiguous := cls._ambiguous_mode(inputs):
            cmd.append(ambiguous)
        if str(inputs.get("excludeFile", "")) != "":
            cmd.append(f"-excludeFile={inputs.get('excludeFile')}")
        cmd.append(f"-maxDiff={inputs.get('maxDiff', 0)}")
        if str(inputs.get("maskSites", "")) != "":
            cmd.append(f"-maskSites={inputs.get('maskSites')}")
        if int(inputs.get("windowSize", 0) or 0) > 0:
            cmd.append(f"-windowSize={inputs.get('windowSize')}")
            cmd.append(f"-minAmbigInWindow={inputs.get('minAmbigInWindow', 2)}")
        if inputs.get("includeNoAltN"):
            cmd.append("-includeNoAltN")
        cmd.append(f"-minAc={inputs.get('minAc', 0)}")
        cmd.append(f"-minAf={inputs.get('minAf', 0.0)}")
        if int(inputs.get("startOffset", 0) or 0) > 0:
            cmd.append(f"-startOffset={inputs.get('startOffset')}")
        if inputs.get("includeRef"):
            cmd.append("-includeRef")
        if inputs.get("noGenotypes"):
            cmd.append("-noGenotypes")
        if str(inputs.get("vcfChrom", "")) != "":
            cmd.append(f"-vcfChrom={inputs.get('vcfChrom')}")
        return f"{setup} && {_shell_join(cmd)}"

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        out = Path(output_dir) / cls.NODE_ID
        out.mkdir(parents=True, exist_ok=True)
        return [out / "out.vcf"]

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        if not str(inputs.get("in_fasta", "")).strip():
            return "in_fasta is required"
        reference_mode = cls._reference_mode(inputs)
        if reference_mode not in cls.REFERENCE_MODES:
            return f"refSeq must be one of: {', '.join(cls.REFERENCE_MODES)}"
        if reference_mode == "customRef" and not str(inputs.get("ref", "")).strip():
            return "ref is required when refSeq is customRef"
        ambiguous = cls._ambiguous_mode(inputs)
        if ambiguous not in cls.AMBIGUOUS_MODES:
            return f"ambiguous must be one of: {', '.join(cls.AMBIGUOUS_MODES)}"
        minimums = {
            "maxDiff": 0,
            "windowSize": 0,
            "minAmbigInWindow": 1,
            "minAc": 0,
            "startOffset": 0,
        }
        for name, minimum in minimums.items():
            value = inputs.get(name, "")
            if str(value) != "" and int(value) < minimum:
                return f"{name} must be greater than or equal to {minimum}"
        min_af = inputs.get("minAf", "")
        if str(min_af) != "" and not 0.0 <= float(min_af) <= 1.0:
            return "minAf must be between 0.0 and 1.0"
        return True

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "in_fasta": ("FASTA", {"description": "FASTA alignment with same-length sequences"}),
            },
            "optional": {
                "refSeq": (
                    "STRING",
                    {
                        "default": "",
                        "options": cls.REFERENCE_MODES,
                        "description": "Use the first sequence or a custom sequence as the reference",
                    },
                ),
                "ref": (
                    "STRING",
                    {"default": "", "description": "Reference sequence name used when refSeq is customRef"},
                ),
                "ambiguous": (
                    "STRING",
                    {
                        "default": "",
                        "options": cls.AMBIGUOUS_MODES,
                        "description": "Treat IUPAC ambiguous bases as no-calls or resolve compatible ambiguous calls",
                    },
                ),
                "excludeFile": (
                    "FILE",
                    {"description": "Optional file listing sequence names to exclude"},
                ),
                "maxDiff": (
                    "INT",
                    {"default": 0, "min": 0, "description": "Exclude sequences with more than this many mismatches"},
                ),
                "maskSites": (
                    "VCF",
                    {"description": "Optional VCF of positions to mask"},
                ),
                "windowSize": (
                    "INT",
                    {"default": 0, "min": 0, "description": "Window radius used for ambiguity masking"},
                ),
                "minAmbigInWindow": (
                    "INT",
                    {"default": 2, "min": 1, "description": "Minimum ambiguous bases in a window before masking"},
                ),
                "includeNoAltN": (
                    "BOOLEAN",
                    {"default": False, "description": "Include no-alternate positions with missing calls"},
                ),
                "minAc": (
                    "INT",
                    {"default": 0, "min": 0, "description": "Minimum alternate allele count"},
                ),
                "minAf": (
                    "FLOAT",
                    {"default": 0.0, "min": 0.0, "max": 1.0, "description": "Minimum alternate allele frequency"},
                ),
                "startOffset": (
                    "INT",
                    {"default": 0, "min": 0, "description": "Offset added to each VCF position"},
                ),
                "includeRef": (
                    "BOOLEAN",
                    {"default": False, "description": "Include the reference sequence in genotype columns"},
                ),
                "noGenotypes": (
                    "BOOLEAN",
                    {"default": False, "description": "Output an 8-column VCF without genotype columns"},
                ),
                "vcfChrom": (
                    "STRING",
                    {"default": "", "description": "Sequence name to use in the VCF CHROM column"},
                ),
            },
            "hidden": {"output": ("STRING", {})},
        }

class UcscMafFilterNode(CommandNode):
    """Filter UCSC MAF alignment blocks."""

    NODE_ID = "ucsc_maffilter"
    DISPLAY_NAME = "mafFilter"
    REQUIRED_CONDA_PACKAGES = ["ucsc-maffilter"]
    CATEGORY = "genomics"
    DESCRIPTION = "Filter UCSC MAF alignment blocks by size, score, species, and component criteria."
    SEARCH_ALIASES = [
        BIONODULO_BUILTIN_ALIAS,
        "UCSC Genome Browser Utilities",
        "ucsc_mafFilter",
        "ucsc_maffilter",
        "mafFilter",
        "MAF block filter",
        "multiple alignment format",
        "species filter",
        "component filter",
        "rejected MAF blocks",
    ]
    RETURN_TYPES = ("FILE", "FILE")
    RETURN_NAMES = ("output_maf", "rejected_maf")
    REQUIRED_EXECUTABLES = ["mafFilter"]
    DOCUMENTATION_URL = "https://github.com/ucscGenomeBrowser/kent/blob/master/src/hg/ratStuff/mafFilter/mafFilter.c"
    CITATION_DOIS = [UCSC_UTILS_CITATION_DOI]
    CITATION_URLS = [f"{DOI_URL}{UCSC_UTILS_CITATION_DOI}"]
    CITATION_TEXT = UCSC_UTILS_CITATION_TEXT
    VERSION = "482+galaxy0"

    FACTOR_OPTIONS = ["no", "yes"]

    @classmethod
    def _output_path(cls, inputs: dict[str, Any]) -> str:
        return f"{_out(inputs)}/output.maf"

    @classmethod
    def _reject_path(cls, inputs: dict[str, Any]) -> str:
        return f"{_out(inputs)}/rejected.maf"

    @classmethod
    def _factor_enabled(cls, inputs: dict[str, Any]) -> str:
        return str(inputs.get("factor_enabled", "no") or "no")

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> str:
        cmd = ["mafFilter"]
        if inputs.get("tolerate"):
            cmd.append("-tolerate")
        for name, default in (("minCol", 1), ("minRow", 2), ("maxRow", 100)):
            cmd.append(f"-{name}={inputs.get(name, default)}")
        if cls._factor_enabled(inputs) == "yes":
            cmd.append("-factor")
            cmd.append(f"-minFactor={inputs.get('minFactor', 5)}")
        elif str(inputs.get("minScore", "")) != "":
            cmd.append(f"-minScore={inputs.get('minScore')}")
        if inputs.get("reject"):
            cmd.append(f"-reject={cls._reject_path(inputs)}")
        if str(inputs.get("needComp", "")) != "":
            cmd.append(f"-needComp={inputs.get('needComp')}")
        if inputs.get("overlap"):
            cmd.append("-overlap")
        if str(inputs.get("componentFilter", "")) != "":
            cmd.append(f"-componentFilter={inputs.get('componentFilter')}")
        if str(inputs.get("speciesFilter", "")) != "":
            cmd.append(f"-speciesFilter={inputs.get('speciesFilter')}")
        cmd.append(str(inputs.get("input_maf", "")))
        return f"{_shell_join(cmd)} > {shlex.quote(cls._output_path(inputs))}"

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        out = Path(output_dir) / cls.NODE_ID
        out.mkdir(parents=True, exist_ok=True)
        outputs = [out / "output.maf"]
        if inputs.get("reject", False):
            outputs.append(out / "rejected.maf")
        return outputs

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        if not str(inputs.get("input_maf", "")).strip():
            return "input_maf is required"
        for name, minimum in (("minCol", 1), ("minRow", 1), ("maxRow", 1)):
            value = inputs.get(name, "")
            if str(value) != "" and int(value) < minimum:
                return f"{name} must be greater than or equal to {minimum}"
        factor_enabled = cls._factor_enabled(inputs)
        if factor_enabled not in cls.FACTOR_OPTIONS:
            return f"factor_enabled must be one of: {', '.join(cls.FACTOR_OPTIONS)}"
        if factor_enabled == "yes":
            if str(inputs.get("minFactor", "")) != "" and int(inputs.get("minFactor")) < 0:
                return "minFactor must be greater than or equal to 0"
            if str(inputs.get("minScore", "")) != "":
                return "minScore cannot be used when factor_enabled is yes"
        if str(inputs.get("minScore", "")) != "" and float(inputs.get("minScore")) < 0:
            return "minScore must be greater than or equal to 0"
        return True

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "input_maf": ("FILE", {"description": "UCSC MAF multiple-alignment file to filter"}),
            },
            "optional": {
                "tolerate": (
                    "BOOLEAN",
                    {"default": False, "description": "Ignore bad input instead of aborting"},
                ),
                "minCol": (
                    "INT",
                    {"default": 1, "min": 1, "description": "Filter out blocks with fewer columns"},
                ),
                "minRow": (
                    "INT",
                    {"default": 2, "min": 1, "description": "Filter out blocks with fewer rows"},
                ),
                "maxRow": (
                    "INT",
                    {"default": 100, "min": 1, "description": "Filter out blocks with at least this many rows"},
                ),
                "factor_enabled": (
                    "STRING",
                    {
                        "default": "no",
                        "options": cls.FACTOR_OPTIONS,
                        "description": "Enable factor-based score filtering instead of minimum score filtering",
                    },
                ),
                "minFactor": (
                    "INT",
                    {"default": 5, "min": 0, "description": "Factor used with factor-based score filtering"},
                ),
                "minScore": (
                    "FLOAT",
                    {"default": "", "min": 0, "description": "Minimum allowed MAF block score"},
                ),
                "reject": (
                    "BOOLEAN",
                    {"default": False, "description": "Write rejected MAF blocks to a second output"},
                ),
                "needComp": (
                    "STRING",
                    {"default": "", "description": "Require this species component in every alignment block"},
                ),
                "overlap": (
                    "BOOLEAN",
                    {"default": False, "description": "Reject overlapping reference blocks in ordered input"},
                ),
                "componentFilter": (
                    "FILE",
                    {"description": "File listing components required for a block to pass"},
                ),
                "speciesFilter": (
                    "FILE",
                    {"description": "File listing species required for a block to pass"},
                ),
            },
            "hidden": {"output": ("STRING", {})},
        }

class UcscMafFetchNode(CommandNode):
    """Fetch UCSC MAF records overlapping BED intervals."""

    NODE_ID = "ucsc_maffetch"
    DISPLAY_NAME = "mafFetch"
    REQUIRED_CONDA_PACKAGES = ["ucsc-maffetch"]
    CATEGORY = "genomics"
    DESCRIPTION = "Fetch UCSC MAF records overlapping BED regions from an indexed UCSC table."
    SEARCH_ALIASES = [
        BIONODULO_BUILTIN_ALIAS,
        "UCSC Genome Browser Utilities",
        "ucsc_mafFetch",
        "ucsc_maffetch",
        "mafFetch",
        "MAF indexed lookup",
        "multiple alignment format",
        "BED overlap",
        "UCSC MAF table",
    ]
    RETURN_TYPES = ("FILE",)
    RETURN_NAMES = ("output",)
    REQUIRED_EXECUTABLES = ["mafFetch"]
    DOCUMENTATION_URL = "https://github.com/ucscGenomeBrowser/kent/blob/master/src/hg/mouseStuff/mafFetch/mafFetch.c"
    CITATION_DOIS = [UCSC_UTILS_CITATION_DOI]
    CITATION_URLS = [f"{DOI_URL}{UCSC_UTILS_CITATION_DOI}"]
    CITATION_TEXT = UCSC_UTILS_CITATION_TEXT
    VERSION = "482+galaxy0"
    SHELL = True

    @classmethod
    def _output_path(cls, inputs: dict[str, Any]) -> str:
        return f"{_out(inputs)}/out.maf"

    @classmethod
    def _ucsc_db_connection(cls, inputs: dict[str, Any]) -> str:
        return str(inputs.get("ucsc_db_connection", "ucsc_db_connection.conf") or "ucsc_db_connection.conf")

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> str:
        setup = (
            f"cp {shlex.quote(cls._ucsc_db_connection(inputs))} ${{HOME}}/.hg.conf && "
            "chmod 600 ${HOME}/.hg.conf"
        )
        cmd = [
            "mafFetch",
            str(inputs.get("genome", "")),
            str(inputs.get("track", "")),
            str(inputs.get("bed_file", "")),
            cls._output_path(inputs),
        ]
        return f"{setup} && {_shell_join(cmd)}"

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        out = Path(output_dir) / cls.NODE_ID
        out.mkdir(parents=True, exist_ok=True)
        return [out / "out.maf"]

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        for name in ("bed_file", "genome", "track"):
            if not str(inputs.get(name, "")).strip():
                return f"{name} is required"
        return True

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "bed_file": ("BED", {"description": "BED6 or BED12 intervals used to fetch overlapping MAF records"}),
                "genome": ("STRING", {"description": "UCSC genome database name"}),
                "track": ("STRING", {"description": "UCSC MAF table name, such as multiz46way"}),
            },
            "optional": {
                "ucsc_db_connection": (
                    "FILE",
                    {"description": "UCSC database connection configuration copied to ~/.hg.conf"},
                ),
            },
            "hidden": {"output": ("STRING", {})},
        }

class UcscMafAddIRowsNode(CommandNode):
    """Add i rows to UCSC MAF alignments."""

    NODE_ID = "ucsc_mafaddirows"
    DISPLAY_NAME = "mafAddIRows"
    REQUIRED_CONDA_PACKAGES = ["ucsc-mafaddirows"]
    CATEGORY = "genomics"
    DESCRIPTION = "Add UCSC MAF i rows or N/dash sequence rows using a twoBit reference."
    SEARCH_ALIASES = [
        BIONODULO_BUILTIN_ALIAS,
        "UCSC Genome Browser Utilities",
        "ucsc_mafAddIRows",
        "ucsc_mafaddirows",
        "mafAddIRows",
        "MAF i rows",
        "multiple alignment format",
        "twoBit reference",
        "N BED files",
    ]
    RETURN_TYPES = ("FILE",)
    RETURN_NAMES = ("output_maf",)
    REQUIRED_EXECUTABLES = ["mafAddIRows"]
    DOCUMENTATION_URL = "https://github.com/ucscGenomeBrowser/kent/blob/master/src/hg/ratStuff/mafAddIRows/mafAddIRows.c"
    CITATION_DOIS = [UCSC_UTILS_CITATION_DOI]
    CITATION_URLS = [f"{DOI_URL}{UCSC_UTILS_CITATION_DOI}"]
    CITATION_TEXT = UCSC_UTILS_CITATION_TEXT
    VERSION = "482+galaxy0"
    SHELL = True

    @classmethod
    def _output_path(cls, inputs: dict[str, Any]) -> str:
        return f"{_out(inputs)}/output.maf"

    @classmethod
    def _nbed_links(cls, inputs: dict[str, Any]) -> list[str]:
        commands = []
        for bed in _as_list(inputs.get("nBeds")):
            identifier = _safe_label(Path(bed).name)
            commands.append(_shell_join(["ln", "-s", bed, identifier]))
            commands.append(f"echo {shlex.quote(identifier)} >> bed.txt")
        return commands

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> str:
        cmd = [
            "mafAddIRows",
            str(inputs.get("input_maf", "")),
            str(inputs.get("twoBitFile", "")),
            cls._output_path(inputs),
        ]
        if _as_list(inputs.get("nBeds")):
            cmd.append("-nBeds=bed.txt")
        if inputs.get("addN"):
            cmd.append("-addN")
        if inputs.get("addDash"):
            cmd.append("-addDash")
        parts = cls._nbed_links(inputs) + [_shell_join(cmd)]
        return " && ".join(parts)

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        out = Path(output_dir) / cls.NODE_ID
        out.mkdir(parents=True, exist_ok=True)
        return [out / "output.maf"]

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        if not str(inputs.get("input_maf", "")).strip():
            return "input_maf is required"
        if not str(inputs.get("twoBitFile", "")).strip():
            return "twoBitFile is required"
        if inputs.get("addN") and inputs.get("addDash"):
            return "addN and addDash cannot both be enabled"
        return True

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "input_maf": ("FILE", {"description": "MAF file with a single target sequence"}),
                "twoBitFile": ("FILE", {"description": "twoBit reference genome file"}),
            },
            "optional": {
                "nBeds": (
                    "BED",
                    {"multiple": True, "default": [], "description": "BED files, one per species, containing N locations"},
                ),
                "addN": ("BOOLEAN", {"default": False, "description": "Add rows of Ns into MAF blocks"}),
                "addDash": ("BOOLEAN", {"default": False, "description": "Add rows of dashes into MAF blocks"}),
            },
            "hidden": {"output": ("STRING", {})},
        }

class UcscMafFragNode(CommandNode):
    """Extract one UCSC MAF alignment region from a database track."""

    NODE_ID = "ucsc_maffrag"
    DISPLAY_NAME = "mafFrag"
    REQUIRED_CONDA_PACKAGES = ["ucsc-maffrag"]
    CATEGORY = "genomics"
    DESCRIPTION = "Extract UCSC MAF sequences for one genomic region from a database track."
    SEARCH_ALIASES = [
        BIONODULO_BUILTIN_ALIAS,
        "UCSC Genome Browser Utilities",
        "ucsc_mafFrag",
        "ucsc_maffrag",
        "mafFrag",
        "MAF region extract",
        "multiple alignment format",
        "UCSC MAF track",
        "single region",
    ]
    RETURN_TYPES = ("FILE",)
    RETURN_NAMES = ("output",)
    REQUIRED_EXECUTABLES = ["mafFrag"]
    DOCUMENTATION_URL = "https://github.com/ucscGenomeBrowser/kent/blob/master/src/hg/ratStuff/mafFrag/mafFrag.c"
    CITATION_DOIS = [UCSC_UTILS_CITATION_DOI]
    CITATION_URLS = [f"{DOI_URL}{UCSC_UTILS_CITATION_DOI}"]
    CITATION_TEXT = UCSC_UTILS_CITATION_TEXT
    VERSION = "482+galaxy0"
    SHELL = True

    STRAND_OPTIONS = [".", "+", "-"]

    @classmethod
    def _output_path(cls, inputs: dict[str, Any]) -> str:
        return f"{_out(inputs)}/out.maf"

    @classmethod
    def _strand(cls, inputs: dict[str, Any]) -> str:
        return str(inputs.get("strand", ".") or ".")

    @classmethod
    def _ucsc_db_connection(cls, inputs: dict[str, Any]) -> str:
        return str(inputs.get("ucsc_db_connection", "ucsc_db_connection.conf") or "ucsc_db_connection.conf")

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> str:
        setup = (
            f"cp {shlex.quote(cls._ucsc_db_connection(inputs))} ${{HOME}}/.hg.conf && "
            "chmod 600 ${HOME}/.hg.conf"
        )
        cmd = [
            "mafFrag",
            str(inputs.get("genome", "")),
            str(inputs.get("track", "")),
            str(inputs.get("chrom", "")),
            str(inputs.get("start", "")),
            str(inputs.get("end", "")),
            cls._strand(inputs),
            cls._output_path(inputs),
        ]
        if str(inputs.get("outName", "")) != "":
            cmd.append(f"-outName={inputs.get('outName')}")
        return f"{setup} && {_shell_join(cmd)}"

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        out = Path(output_dir) / cls.NODE_ID
        out.mkdir(parents=True, exist_ok=True)
        return [out / "out.maf"]

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        for name in ("genome", "track", "chrom"):
            if not str(inputs.get(name, "")).strip():
                return f"{name} is required"
        if str(inputs.get("start", "")) == "":
            return "start is required"
        if str(inputs.get("end", "")) == "":
            return "end is required"
        strand = cls._strand(inputs)
        if strand not in cls.STRAND_OPTIONS:
            return f"strand must be one of: {', '.join(cls.STRAND_OPTIONS)}"
        try:
            start = int(inputs.get("start"))
        except (TypeError, ValueError):
            return "start must be an integer"
        try:
            end = int(inputs.get("end"))
        except (TypeError, ValueError):
            return "end must be an integer"
        if start < 0:
            return "start must be greater than or equal to 0"
        if end <= start:
            return "end must be greater than start"
        return True

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "genome": ("STRING", {"description": "UCSC genome database name, such as hg19 or hg38"}),
                "track": ("STRING", {"description": "UCSC MAF table name, such as multiz46way"}),
                "chrom": ("STRING", {"description": "Chromosome or sequence name to extract"}),
                "start": ("INT", {"min": 0, "description": "0-based start coordinate"}),
                "end": ("INT", {"min": 1, "description": "0-based end coordinate"}),
                "strand": (
                    "STRING",
                    {
                        "default": ".",
                        "options": cls.STRAND_OPTIONS,
                        "description": "Region strand: no strand, forward, or reverse",
                    },
                ),
            },
            "optional": {
                "ucsc_db_connection": (
                    "FILE",
                    {"description": "UCSC database connection configuration copied to ~/.hg.conf"},
                ),
                "outName": (
                    "STRING",
                    {"default": "", "description": "Override the database.chrom sequence name in the output MAF"},
                ),
            },
            "hidden": {"output": ("STRING", {})},
        }

class UcscMafFragsNode(CommandNode):
    """Extract UCSC MAF alignments for BED regions from a database track."""

    NODE_ID = "ucsc_maffrags"
    DISPLAY_NAME = "mafFrags"
    REQUIRED_CONDA_PACKAGES = ["ucsc-maffrags"]
    CATEGORY = "genomics"
    DESCRIPTION = "Extract UCSC MAF alignments for multiple BED regions from a database track."
    SEARCH_ALIASES = [
        BIONODULO_BUILTIN_ALIAS,
        "UCSC Genome Browser Utilities",
        "ucsc_mafFrags",
        "ucsc_maffrags",
        "mafFrags",
        "BED region MAF extraction",
        "multiple alignment format",
        "BED12 exons",
        "UCSC MAF track",
    ]
    RETURN_TYPES = ("FILE",)
    RETURN_NAMES = ("output",)
    REQUIRED_EXECUTABLES = ["mafFrags"]
    DOCUMENTATION_URL = "https://github.com/ucscGenomeBrowser/kent/blob/master/src/hg/ratStuff/mafFrags/mafFrags.c"
    CITATION_DOIS = [UCSC_UTILS_CITATION_DOI]
    CITATION_URLS = [f"{DOI_URL}{UCSC_UTILS_CITATION_DOI}"]
    CITATION_TEXT = UCSC_UTILS_CITATION_TEXT
    VERSION = "482+galaxy0"
    SHELL = True

    @classmethod
    def _output_path(cls, inputs: dict[str, Any]) -> str:
        return f"{_out(inputs)}/out.maf"

    @classmethod
    def _ucsc_db_connection(cls, inputs: dict[str, Any]) -> str:
        return str(inputs.get("ucsc_db_connection", "ucsc_db_connection.conf") or "ucsc_db_connection.conf")

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> str:
        setup = (
            f"cp {shlex.quote(cls._ucsc_db_connection(inputs))} ${{HOME}}/.hg.conf && "
            "chmod 600 ${HOME}/.hg.conf"
        )
        cmd = [
            "mafFrags",
            str(inputs.get("genome", "")),
            str(inputs.get("track", "")),
            str(inputs.get("bed_file", "")),
        ]
        for flag in ("bed12", "thickOnly", "meFirst", "txStarts", "refCoords"):
            if inputs.get(flag):
                cmd.append(f"-{flag}")
        if str(inputs.get("orgs", "")) != "":
            cmd.append(f"-orgs={inputs.get('orgs')}")
        cmd.append(cls._output_path(inputs))
        return f"{setup} && {_shell_join(cmd)}"

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        out = Path(output_dir) / cls.NODE_ID
        out.mkdir(parents=True, exist_ok=True)
        return [out / "out.maf"]

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        for name in ("bed_file", "genome", "track"):
            if not str(inputs.get(name, "")).strip():
                return f"{name} is required"
        if inputs.get("bed12") and (inputs.get("txStarts") or inputs.get("refCoords")):
            return "bed12 cannot be combined with txStarts or refCoords"
        return True

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "bed_file": ("BED", {"description": "BED6 or BED12 regions to extract from the UCSC MAF track"}),
                "genome": ("STRING", {"description": "UCSC genome database name, such as hg19 or hg38"}),
                "track": ("STRING", {"description": "UCSC MAF table name, such as multiz46way"}),
            },
            "optional": {
                "bed12": ("BOOLEAN", {"default": False, "description": "Treat the input BED as BED12 exon blocks"}),
                "thickOnly": (
                    "BOOLEAN",
                    {"default": False, "description": "When using BED12, extract only thickStart to thickEnd regions"},
                ),
                "meFirst": (
                    "BOOLEAN",
                    {"default": False, "description": "Place the reference genome sequence first in each MAF block"},
                ),
                "txStarts": (
                    "BOOLEAN",
                    {"default": False, "description": "Add txstart r-lines using BED names and reference coordinates"},
                ),
                "refCoords": (
                    "BOOLEAN",
                    {"default": False, "description": "Use actual reference genome coordinates in the output MAF"},
                ),
                "orgs": (
                    "TXT",
                    {"description": "Optional organism order file used with the UCSC -orgs option"},
                ),
                "ucsc_db_connection": (
                    "FILE",
                    {"description": "UCSC database connection configuration copied to ~/.hg.conf"},
                ),
            },
            "hidden": {"output": ("STRING", {})},
        }

class UcscMafGeneNode(CommandNode):
    """Extract FASTA gene alignments from UCSC MAF and genePred inputs."""

    NODE_ID = "ucsc_mafgene"
    DISPLAY_NAME = "mafGene"
    REQUIRED_CONDA_PACKAGES = ["ucsc-mafgene"]
    CATEGORY = "genomics"
    DESCRIPTION = "Extract FASTA protein or nucleotide alignments from UCSC MAF and genePred inputs."
    SEARCH_ALIASES = [
        BIONODULO_BUILTIN_ALIAS,
        "UCSC Genome Browser Utilities",
        "ucsc_mafGene",
        "ucsc_mafgene",
        "mafGene",
        "genePred protein alignments",
        "multiple alignment format",
        "species list",
        "UTR alignment",
    ]
    RETURN_TYPES = ("FASTA",)
    RETURN_NAMES = ("output",)
    REQUIRED_EXECUTABLES = ["mafGene"]
    DOCUMENTATION_URL = "https://github.com/ucscGenomeBrowser/kent/blob/master/src/hg/ratStuff/mafGene/mafGene.c"
    CITATION_DOIS = [UCSC_UTILS_CITATION_DOI]
    CITATION_URLS = [f"{DOI_URL}{UCSC_UTILS_CITATION_DOI}"]
    CITATION_TEXT = UCSC_UTILS_CITATION_TEXT
    VERSION = "490+galaxy0"
    SHELL = True

    SELECTION_TYPES = ["all", "single", "list", "bed", "chrom"]

    @classmethod
    def _output_path(cls, inputs: dict[str, Any]) -> str:
        return f"{_out(inputs)}/output.fasta"

    @classmethod
    def _selection_type(cls, inputs: dict[str, Any]) -> str:
        return str(inputs.get("selection_type", "all") or "all")

    @classmethod
    def _ucsc_db_connection(cls, inputs: dict[str, Any]) -> str:
        return str(inputs.get("ucsc_db_connection", "ucsc_db_connection.conf") or "ucsc_db_connection.conf")

    @staticmethod
    def _linked_name(path_value: Any) -> str:
        return _safe_label(Path(str(path_value)).name)

    @classmethod
    def _should_use_file(cls, inputs: dict[str, Any], genepred_name: str) -> bool:
        return bool(inputs.get("useFile")) or genepred_name.endswith(".gp")

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> str:
        maf_name = cls._linked_name(inputs.get("maf_file", ""))
        genepred_name = cls._linked_name(inputs.get("genepred_file", ""))
        setup = [
            f"cp {shlex.quote(cls._ucsc_db_connection(inputs))} ${{HOME}}/.hg.conf",
            "chmod 600 ${HOME}/.hg.conf",
            _shell_join(["ln", "-s", str(inputs.get("twoBitFile", "")), "input.2bit"]),
            _shell_join(["ln", "-s", str(inputs.get("maf_file", "")), maf_name]),
            _shell_join(["ln", "-s", str(inputs.get("genepred_file", "")), genepred_name]),
        ]
        cmd = [
            "mafGene",
            "-twoBit=input.2bit",
            str(inputs.get("db_name", "")),
            maf_name,
            genepred_name,
            str(inputs.get("species_list", "")),
            cls._output_path(inputs),
        ]
        selection_type = cls._selection_type(inputs)
        if selection_type == "single":
            cmd.append(f"-geneName={inputs.get('gene_name')}")
        elif selection_type == "list":
            cmd.append(f"-geneList={inputs.get('gene_list')}")
        elif selection_type == "bed":
            cmd.append(f"-geneBeds={inputs.get('gene_beds')}")
        elif selection_type == "chrom":
            cmd.append(f"-chrom={inputs.get('chrom')}")
        for flag in ("exons", "noTrans", "uniqAA", "includeUtr", "noDash"):
            if inputs.get(flag):
                cmd.append(f"-{flag}")
        if cls._should_use_file(inputs, genepred_name):
            cmd.append("-useFile")
        if str(inputs.get("delay", "")) != "":
            cmd.append(f"-delay={inputs.get('delay')}")
        return " && ".join(setup + [_shell_join(cmd)])

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        out = Path(output_dir) / cls.NODE_ID
        out.mkdir(parents=True, exist_ok=True)
        return [out / "output.fasta"]

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        for name in ("twoBitFile", "db_name", "maf_file", "genepred_file", "species_list"):
            if not str(inputs.get(name, "")).strip():
                return f"{name} is required"
        selection_type = cls._selection_type(inputs)
        if selection_type not in cls.SELECTION_TYPES:
            return f"selection_type must be one of: {', '.join(cls.SELECTION_TYPES)}"
        required_for_mode = {
            "single": "gene_name",
            "list": "gene_list",
            "bed": "gene_beds",
            "chrom": "chrom",
        }
        required_name = required_for_mode.get(selection_type)
        if required_name and not str(inputs.get(required_name, "")).strip():
            return f"{required_name} is required when selection_type is {selection_type}"
        if inputs.get("includeUtr") and not inputs.get("noTrans"):
            return "includeUtr requires noTrans"
        delay = inputs.get("delay", "")
        if str(delay) != "":
            try:
                delay_value = int(delay)
            except (TypeError, ValueError):
                return "delay must be an integer"
            if delay_value < 0:
                return "delay must be greater than or equal to 0"
        return True

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "twoBitFile": ("FILE", {"description": "twoBit reference genome used to fill alignment gaps"}),
                "db_name": ("STRING", {"description": "UCSC genome database name, such as hg38 or sacCer3"}),
                "maf_file": ("FILE", {"description": "MAF, bigMaf, or UCSC MAF table to extract alignments from"}),
                "genepred_file": ("FILE", {"description": "genePred table or .gp file containing gene predictions"}),
                "species_list": (
                    "STRING",
                    {"description": "Species list file with one species name per line"},
                ),
            },
            "optional": {
                "selection_type": (
                    "STRING",
                    {
                        "default": "all",
                        "options": cls.SELECTION_TYPES,
                        "description": "Select all genes, one gene, a gene list, BED-defined genes, or one chromosome",
                    },
                ),
                "gene_name": ("STRING", {"default": "", "description": "Gene name used when selection_type is single"}),
                "gene_list": (
                    "STRING",
                    {"default": "", "description": "File containing gene names used when selection_type is list"},
                ),
                "gene_beds": ("BED", {"description": "BED4 file of genes used when selection_type is bed"}),
                "chrom": ("STRING", {"default": "", "description": "Chromosome name used when selection_type is chrom"}),
                "exons": ("BOOLEAN", {"default": False, "description": "Output exon alignments instead of full genes"}),
                "noTrans": (
                    "BOOLEAN",
                    {"default": False, "description": "Keep nucleotide alignments instead of translating to amino acids"},
                ),
                "uniqAA": (
                    "BOOLEAN",
                    {"default": False, "description": "Emit a unique pseudo-amino-acid code for every codon"},
                ),
                "includeUtr": (
                    "BOOLEAN",
                    {"default": False, "description": "Include untranslated regions; requires noTrans"},
                ),
                "noDash": ("BOOLEAN", {"default": False, "description": "Skip output rows containing only dashes"}),
                "useFile": (
                    "BOOLEAN",
                    {"default": False, "description": "Treat the genePred input as a file instead of a database table"},
                ),
                "delay": (
                    "INT",
                    {"default": "", "min": 0, "description": "Optional delay in seconds between genes"},
                ),
                "ucsc_db_connection": (
                    "FILE",
                    {"description": "UCSC database connection configuration copied to ~/.hg.conf"},
                ),
            },
            "hidden": {"output": ("STRING", {})},
        }

class GtfToBed12Node(CommandNode):
    """Convert GTF gene annotations to BED12."""

    NODE_ID = "gtftobed12"
    DISPLAY_NAME = "Convert GTF to BED12"
    REQUIRED_CONDA_PACKAGES = ["ucsc-gtftogenepred", "ucsc-genepredtobed"]
    CATEGORY = "genomics"
    DESCRIPTION = "Convert a GTF gene annotation to blocked BED12 using UCSC gtfToGenePred and genePredToBed."
    SEARCH_ALIASES = [
        BIONODULO_BUILTIN_ALIAS,
        "UCSC Genome Browser Utilities",
        "gtfToBed12",
        "gtftobed12",
        "GTF to BED12",
        "gtfToGenePred",
        "genePredToBed",
        "gene annotation conversion",
        "transcript info",
    ]
    RETURN_TYPES = ("BED", "TSV")
    RETURN_NAMES = ("bed_file", "transcript_info_file")
    REQUIRED_EXECUTABLES = ["gtfToGenePred", "genePredToBed"]
    DOCUMENTATION_URL = "https://github.com/ucscGenomeBrowser/kent/blob/master/src/hg/utils/gtfToGenePred/gtfToGenePred.c"
    CITATION_DOIS = [UCSC_GENOME_BROWSER_CITATION_DOI]
    CITATION_URLS = [f"{DOI_URL}{UCSC_GENOME_BROWSER_CITATION_DOI}"]
    CITATION_TEXT = UCSC_GENOME_BROWSER_CITATION_TEXT
    VERSION = "357"
    SHELL = True

    ADVANCED_OPTIONS = ["default", "advanced"]
    FLAG_INPUTS = (
        ("ignoreGroupsWithoutExons", "-ignoreGroupsWithoutExons"),
        ("simple", "-simple"),
        ("allErrors", "-allErrors"),
        ("impliedStopAfterCds", "-impliedStopAfterCds"),
        ("includeVersion", "-includeVersion"),
    )

    @classmethod
    def _advanced_options_selector(cls, inputs: dict[str, Any]) -> str:
        return str(inputs.get("advanced_options_selector", "default") or "default")

    @classmethod
    def _bed_path(cls, inputs: dict[str, Any]) -> str:
        return f"{_out(inputs)}/converted.bed"

    @classmethod
    def _genepred_path(cls, inputs: dict[str, Any]) -> str:
        return f"{_out(inputs)}/temp.genePred"

    @classmethod
    def _transcript_info_path(cls, inputs: dict[str, Any]) -> str:
        return f"{_out(inputs)}/transcript_info.tsv"

    @classmethod
    def _writes_transcript_info(cls, inputs: dict[str, Any]) -> bool:
        return cls._advanced_options_selector(inputs) == "advanced" and bool(inputs.get("infoOut", False))

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> str:
        gtf_cmd = ["gtfToGenePred"]
        if cls._advanced_options_selector(inputs) == "advanced":
            for name, flag in cls.FLAG_INPUTS:
                if inputs.get(name):
                    gtf_cmd.append(flag)
            if inputs.get("infoOut"):
                gtf_cmd.append(f"-infoOut={cls._transcript_info_path(inputs)}")
            for prefix in _as_list(inputs.get("sourcePrefixes")):
                gtf_cmd.append(f"-sourcePrefix={prefix}")
        gtf_cmd.extend([str(inputs.get("gtf_file", "")), cls._genepred_path(inputs)])
        bed_cmd = ["genePredToBed", cls._genepred_path(inputs), cls._bed_path(inputs)]
        return f"{_shell_join(gtf_cmd)} && {_shell_join(bed_cmd)}"

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        out = Path(output_dir) / cls.NODE_ID
        out.mkdir(parents=True, exist_ok=True)
        outputs = [out / "converted.bed"]
        if cls._writes_transcript_info(inputs):
            outputs.append(out / "transcript_info.tsv")
        return outputs

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        if not str(inputs.get("gtf_file", "")).strip():
            return "gtf_file is required"
        selector = cls._advanced_options_selector(inputs)
        if selector not in cls.ADVANCED_OPTIONS:
            return f"advanced_options_selector must be one of: {', '.join(cls.ADVANCED_OPTIONS)}"
        prefixes = _as_list(inputs.get("sourcePrefixes"))
        if selector != "advanced" and prefixes:
            return "sourcePrefixes can only be used when advanced_options_selector is advanced"
        if any(not prefix.strip() for prefix in prefixes):
            return "sourcePrefixes cannot contain blank values"
        return True

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "gtf_file": ("GTF", {"description": "GTF gene annotation file to convert to BED12"}),
            },
            "optional": {
                "advanced_options_selector": (
                    "STRING",
                    {
                        "default": "default",
                        "options": cls.ADVANCED_OPTIONS,
                        "description": "Use default conversion settings or expose gtfToGenePred advanced options",
                    },
                ),
                "sourcePrefixes": (
                    "STRING",
                    {
                        "default": [],
                        "multiple": True,
                        "description": "Only process GTF entries whose source field starts with one of these prefixes",
                    },
                ),
                "ignoreGroupsWithoutExons": (
                    "BOOLEAN",
                    {"default": False, "description": "Skip transcript groups that do not contain exons"},
                ),
                "simple": (
                    "BOOLEAN",
                    {"default": False, "description": "Check only column validity instead of the full GTF hierarchy"},
                ),
                "allErrors": (
                    "BOOLEAN",
                    {"default": False, "description": "Skip groups with errors rather than aborting at the first error"},
                ),
                "impliedStopAfterCds": (
                    "BOOLEAN",
                    {"default": False, "description": "Assume an implied stop codon after the CDS"},
                ),
                "includeVersion": (
                    "BOOLEAN",
                    {
                        "default": False,
                        "description": "Include gene_version and transcript_version attributes in output identifiers",
                    },
                ),
                "infoOut": (
                    "BOOLEAN",
                    {"default": False, "description": "Write a transcript information table from gtfToGenePred"},
                ),
            },
            "hidden": {"output": ("STRING", {})},
        }

class GffReadNode(CommandNode):
    """Filter, convert, and extract sequence from GFF/GTF/BED annotations."""

    NODE_ID = "gffread"
    DISPLAY_NAME = "gffread"
    REQUIRED_CONDA_PACKAGES = ["gffread"]
    CATEGORY = "annotation"
    DESCRIPTION = "Filter, convert, cluster, and extract sequences from GFF3, GTF, or BED annotations."
    SEARCH_ALIASES = [
        BIONODULO_BUILTIN_ALIAS,
        "gffread",
        "GffRead",
        "GFF Utilities",
        "GTF to GFF3",
        "GFF3 to GTF",
        "GFF to BED",
        "annotation conversion",
        "extract transcript FASTA",
        "transcript clustering",
    ]
    RETURN_TYPES = ("GFF3", "GTF", "BED", "FASTA", "FASTA", "FASTA", "TXT")
    RETURN_NAMES = (
        "output_gff",
        "output_gtf",
        "output_bed",
        "output_exons",
        "output_cds",
        "output_pep",
        "output_dupinfo",
    )
    REQUIRED_EXECUTABLES = ["gffread"]
    DOCUMENTATION_URL = "https://github.com/gpertea/gffread"
    CITATION_DOIS = [GFFREAD_CITATION_DOI]
    CITATION_URLS = [f"{DOI_URL}{GFFREAD_CITATION_DOI}"]
    CITATION_TEXT = GFFREAD_CITATION_TEXT
    VERSION = "0.12.7"
    SHELL = True

    GFF_FORMATS = ["none", "gff", "gtf", "bed"]
    FILTERING_OPTIONS = ["-U", "-C", "-G", "-O", "--no-pseudo"]
    REFERENCE_SOURCES = ["none", "cached", "history"]
    REF_FILTERING_OPTIONS = ["-N", "-J", "-V", "-H"]
    FA_OUTPUTS = ["exons", "cds", "pep", "project_coords", "stop_star"]
    MERGE_SELS = ["none", "merge", "cluster"]
    MERGE_OPTIONS = ["force_exons", "merge_close_exons", "collapse_contained", "relaxed_containment", "dupinfo"]
    DUPINFO_TOKEN = "__GFFREAD_DUPINFO__"
    MERGE_OPTION_FLAGS = {
        "force_exons": "--force-exons",
        "merge_close_exons": "-Z",
        "collapse_contained": "-K",
        "relaxed_containment": "-Q",
    }
    RANGE_PATTERN = re.compile(r"^([+-]?[\w.-]+:)?\d+\.\.\d+$")

    @classmethod
    def _gff_fmt(cls, inputs: dict[str, Any]) -> str:
        return str(inputs.get("gff_fmt", "none") or "none")

    @classmethod
    def _output_format(cls, inputs: dict[str, Any]) -> str:
        fmt = cls._gff_fmt(inputs)
        return "gff" if fmt == "none" else fmt

    @classmethod
    def _output_filename(cls, inputs: dict[str, Any]) -> str:
        return f"output.{cls._output_format(inputs)}"

    @classmethod
    def _output_path(cls, inputs: dict[str, Any]) -> str:
        return f"{_out(inputs)}/{cls._output_filename(inputs)}"

    @classmethod
    def _reference_source(cls, inputs: dict[str, Any]) -> str:
        return str(inputs.get("reference_genome_source", "none") or "none")

    @classmethod
    def _dupinfo_path(cls, inputs: dict[str, Any]) -> str:
        return f"{_out(inputs)}/dupinfo.txt"

    @classmethod
    def _quoted_dupinfo_option(cls, inputs: dict[str, Any]) -> str:
        return "'" + f"-d={cls._dupinfo_path(inputs)}".replace("'", "'\"'\"'") + "'"

    @classmethod
    def _selected_fa_outputs(cls, inputs: dict[str, Any]) -> list[str]:
        return _as_list(inputs.get("fa_outputs"))

    @classmethod
    def _selected_merge_options(cls, inputs: dict[str, Any]) -> list[str]:
        return _as_list(inputs.get("merge_options"))

    @classmethod
    def _add_reference(cls, cmd: list[str], inputs: dict[str, Any]) -> None:
        source = cls._reference_source(inputs)
        if source == "history":
            cmd.extend(["-g", "genomeref.fa"])
        elif source == "cached":
            cmd.extend(["-g", str(inputs.get("fasta_index_path", inputs.get("fasta_index", "")))])
        if source != "none":
            cmd.extend(_as_list(inputs.get("ref_filtering")))

    @classmethod
    def _add_merge_options(cls, cmd: list[str], inputs: dict[str, Any]) -> None:
        merge_sel = str(inputs.get("merge_sel", "none") or "none")
        if merge_sel == "merge":
            cmd.append("--merge")
        elif merge_sel == "cluster":
            cmd.append("--cluster-only")
        if merge_sel == "none":
            return
        for option in cls._selected_merge_options(inputs):
            if option == "dupinfo":
                cmd.append(cls.DUPINFO_TOKEN)
            else:
                cmd.append(cls.MERGE_OPTION_FLAGS[option])

    @classmethod
    def _add_fasta_outputs(cls, cmd: list[str], inputs: dict[str, Any]) -> None:
        out = _out(inputs)
        for value in cls._selected_fa_outputs(inputs):
            if value == "exons":
                cmd.extend(["-w", f"{out}/exons.fa"])
            elif value == "cds":
                cmd.extend(["-x", f"{out}/cds.fa"])
            elif value == "pep":
                cmd.extend(["-y", f"{out}/pep.fa"])
            elif value == "project_coords":
                cmd.append("-W")
            elif value == "stop_star":
                cmd.append("-S")

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> str:
        cmd = ["gffread", str(inputs.get("input", ""))]
        if str(inputs.get("input_format", "")).lower() == "bed" or str(inputs.get("input", "")).lower().endswith(".bed"):
            cmd.append("--in-bed")
        cls._add_reference(cmd, inputs)
        cmd.extend(_as_list(inputs.get("filtering")))
        if str(inputs.get("maxintron", "")) not in {"", "0"}:
            cmd.extend(["-i", str(inputs.get("maxintron"))])
        if str(inputs.get("region_filter", "none") or "none") == "filter":
            cmd.extend(["-r", str(inputs.get("range", ""))])
            if inputs.get("discard_partial"):
                cmd.append("-R")
        cls._add_merge_options(cmd, inputs)
        if inputs.get("chr_replace"):
            cmd.append(f"-m={inputs.get('chr_replace')}")
        if inputs.get("full_gff_attribute_preservation"):
            cmd.append("-F")
        if inputs.get("decode_url"):
            cmd.append("-D")
        if inputs.get("expose"):
            cmd.append("-E")
        cls._add_fasta_outputs(cmd, inputs)
        gff_fmt = cls._gff_fmt(inputs)
        if gff_fmt != "none":
            if gff_fmt != "bed" and inputs.get("tname"):
                cmd.extend(["-t", str(inputs.get("tname"))])
            if gff_fmt == "gtf":
                cmd.append("-T")
            elif gff_fmt == "bed":
                cmd.append("--bed")
            cmd.extend(["-o", cls._output_path(inputs)])
        elif not cls._selected_fa_outputs(inputs):
            cmd.extend(["-o", cls._output_path(inputs)])

        command = _shell_join(cmd).replace(cls.DUPINFO_TOKEN, cls._quoted_dupinfo_option(inputs))
        if cls._reference_source(inputs) == "history":
            setup = _shell_join(["ln", "-s", str(inputs.get("genome_fasta", "")), "genomeref.fa"])
            return f"{setup} && {command}"
        return command

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        out = Path(output_dir) / cls.NODE_ID
        out.mkdir(parents=True, exist_ok=True)
        outputs: list[Path] = [out / cls._output_filename(inputs)]
        fa_outputs = cls._selected_fa_outputs(inputs)
        if "exons" in fa_outputs:
            outputs.append(out / "exons.fa")
        if "cds" in fa_outputs:
            outputs.append(out / "cds.fa")
        if "pep" in fa_outputs:
            outputs.append(out / "pep.fa")
        if str(inputs.get("merge_sel", "none") or "none") != "none" and "dupinfo" in cls._selected_merge_options(inputs):
            outputs.append(out / "dupinfo.txt")
        return outputs

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        if not str(inputs.get("input", "")).strip():
            return "input is required"
        gff_fmt = cls._gff_fmt(inputs)
        if gff_fmt not in cls.GFF_FORMATS:
            return f"gff_fmt must be one of: {', '.join(cls.GFF_FORMATS)}"
        filtering = _as_list(inputs.get("filtering"))
        if any(value not in cls.FILTERING_OPTIONS for value in filtering):
            return f"filtering values must be one of: {', '.join(cls.FILTERING_OPTIONS)}"
        ref_filtering = _as_list(inputs.get("ref_filtering"))
        if any(value not in cls.REF_FILTERING_OPTIONS for value in ref_filtering):
            return f"ref_filtering values must be one of: {', '.join(cls.REF_FILTERING_OPTIONS)}"
        source = cls._reference_source(inputs)
        if source not in cls.REFERENCE_SOURCES:
            return f"reference_genome_source must be one of: {', '.join(cls.REFERENCE_SOURCES)}"
        if source == "history" and not str(inputs.get("genome_fasta", "")).strip():
            return "genome_fasta is required when reference_genome_source is history"
        if source == "cached" and not str(inputs.get("fasta_index_path", inputs.get("fasta_index", ""))).strip():
            return "fasta_index_path is required when reference_genome_source is cached"
        fa_outputs = cls._selected_fa_outputs(inputs)
        if any(value not in cls.FA_OUTPUTS for value in fa_outputs):
            return f"fa_outputs values must be one of: {', '.join(cls.FA_OUTPUTS)}"
        if fa_outputs and source == "none":
            return "reference_genome_source cannot be none when FASTA outputs are requested"
        if ref_filtering and source == "none":
            return "reference_genome_source cannot be none when reference filters are requested"
        if str(inputs.get("region_filter", "none") or "none") == "filter":
            region = str(inputs.get("range", "") or "")
            if not region:
                return "range is required when region_filter is filter"
            if not cls.RANGE_PATTERN.match(region):
                return "range must use gffread coordinate syntax like chr1:100..200"
        maxintron = inputs.get("maxintron", "")
        if str(maxintron) != "":
            try:
                maxintron_value = int(maxintron)
            except (TypeError, ValueError):
                return "maxintron must be an integer"
            if maxintron_value < 0:
                return "maxintron must be greater than or equal to 0"
        merge_sel = str(inputs.get("merge_sel", "none") or "none")
        if merge_sel not in cls.MERGE_SELS:
            return f"merge_sel must be one of: {', '.join(cls.MERGE_SELS)}"
        merge_options = cls._selected_merge_options(inputs)
        if any(value not in cls.MERGE_OPTIONS for value in merge_options):
            return f"merge_options values must be one of: {', '.join(cls.MERGE_OPTIONS)}"
        if merge_sel == "none" and merge_options:
            return "merge_options can only be used when merge_sel is merge or cluster"
        if merge_sel == "cluster":
            unsupported = [value for value in merge_options if value in {"collapse_contained", "relaxed_containment", "dupinfo"}]
            if unsupported:
                return "cluster merge_options only supports force_exons and merge_close_exons"
        tname = str(inputs.get("tname", "") or "")
        if tname and not re.fullmatch(r"\w+", tname):
            return "tname must contain only letters, digits, and underscores"
        return True

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "input": ("GFF_GTF", {"description": "Input BED, GFF3, or GTF feature annotation file"}),
            },
            "optional": {
                "gff_fmt": (
                    "STRING",
                    {"default": "none", "options": cls.GFF_FORMATS, "description": "Annotation output format"},
                ),
                "input_format": (
                    "STRING",
                    {"default": "auto", "options": ["auto", "bed", "gff", "gtf"], "description": "Input format override"},
                ),
                "filtering": (
                    "STRING",
                    {
                        "default": [],
                        "options": cls.FILTERING_OPTIONS,
                        "multiple": True,
                        "description": "Transcript and feature filters",
                    },
                ),
                "region_filter": (
                    "STRING",
                    {"default": "none", "options": ["none", "filter"], "description": "Restrict output to a coordinate range"},
                ),
                "range": (
                    "STRING",
                    {"default": "", "description": "Coordinate range using gffread syntax such as chr1:100..200"},
                ),
                "discard_partial": (
                    "BOOLEAN",
                    {"default": False, "description": "Discard transcripts not fully contained in the coordinate range"},
                ),
                "maxintron": (
                    "INT",
                    {"default": "", "min": 0, "description": "Discard transcripts with introns larger than this length"},
                ),
                "chr_replace": (
                    "TSV",
                    {"description": "Two-column reference sequence replacement table"},
                ),
                "reference_genome_source": (
                    "STRING",
                    {
                        "default": "none",
                        "options": cls.REFERENCE_SOURCES,
                        "description": "Reference genome source for FASTA outputs or reference-based filters",
                    },
                ),
                "genome_fasta": ("FASTA", {"description": "Reference FASTA selected from history"}),
                "fasta_index_path": ("FASTA", {"description": "Cached reference FASTA path"}),
                "ref_filtering": (
                    "STRING",
                    {
                        "default": [],
                        "options": cls.REF_FILTERING_OPTIONS,
                        "multiple": True,
                        "description": "Reference-based CDS and splice-site filters",
                    },
                ),
                "fa_outputs": (
                    "STRING",
                    {
                        "default": [],
                        "options": cls.FA_OUTPUTS,
                        "multiple": True,
                        "description": "FASTA sequence outputs and FASTA formatting flags",
                    },
                ),
                "merge_sel": (
                    "STRING",
                    {"default": "none", "options": cls.MERGE_SELS, "description": "Transcript merge or cluster mode"},
                ),
                "merge_options": (
                    "STRING",
                    {
                        "default": [],
                        "options": cls.MERGE_OPTIONS,
                        "multiple": True,
                        "description": "Merge and cluster handling options",
                    },
                ),
                "full_gff_attribute_preservation": (
                    "BOOLEAN",
                    {"default": False, "description": "Preserve all GFF attributes when possible"},
                ),
                "decode_url": ("BOOLEAN", {"default": False, "description": "Decode URL-encoded characters"}),
                "expose": ("BOOLEAN", {"default": False, "description": "Expose warning diagnostics from gffread"}),
                "tname": (
                    "STRING",
                    {"default": "", "description": "Track name to use in the second column of GFF output"},
                ),
            },
            "hidden": {"output": ("STRING", {})},
        }

class GffCompareNode(CommandNode):
    """Compare and track GFF/GTF transcript annotations."""

    NODE_ID = "gffcompare"
    DISPLAY_NAME = "GffCompare"
    REQUIRED_CONDA_PACKAGES = ["gffcompare", "samtools"]
    CATEGORY = "annotation"
    DESCRIPTION = "Compare, classify, merge, and track GFF/GTF transcript annotations."
    SEARCH_ALIASES = [
        BIONODULO_BUILTIN_ALIAS,
        "gffcompare",
        "GffCompare",
        "GFF Utilities",
        "CuffCompare",
        "transcript tracking",
        "transcript classification",
        "GTF comparison",
        "GFF comparison",
        "annotation mode",
        "RefMap",
        "TMAP",
    ]
    RETURN_TYPES = ("GTF", "GTF", "TXT", "TSV", "TSV", "TSV", "TSV")
    RETURN_NAMES = (
        "transcripts_annotated",
        "transcripts_combined",
        "transcripts_stats",
        "transcripts_loci",
        "transcripts_tracking",
        "tmap_output",
        "refmap_output",
    )
    REQUIRED_EXECUTABLES = ["gffcompare", "samtools"]
    DOCUMENTATION_URL = "https://github.com/gpertea/gffcompare"
    CITATION_DOIS = [GFFREAD_CITATION_DOI]
    CITATION_URLS = [f"{DOI_URL}{GFFREAD_CITATION_DOI}"]
    CITATION_TEXT = GFFREAD_CITATION_TEXT
    VERSION = "0.12.10"
    SHELL = True

    YES_NO_OPTIONS = ["no", "yes"]
    SOURCES = ["history", "cached"]
    DISCARD_SINGLE_EXON_OPTIONS = ["", "-M", "-N"]
    DUPLICATION_OPTIONS = ["", "-D"]

    @classmethod
    def _gffinputs(cls, inputs: dict[str, Any]) -> list[str]:
        return _as_list(inputs.get("gffinputs"))

    @classmethod
    def _staged_input_names(cls, inputs: dict[str, Any]) -> list[str]:
        labels = _as_list(inputs.get("element_identifiers"))
        names: list[str] = []
        seen: dict[str, int] = {}
        for index, input_path in enumerate(cls._gffinputs(inputs)):
            label = labels[index] if index < len(labels) and labels[index] else input_path
            name = _safe_element_identifier(label).replace(".", "_")
            if not name:
                name = f"input_{index + 1}"
            count = seen.get(name, 0)
            seen[name] = count + 1
            if count:
                name = f"{name}_{count}"
            names.append(name)
        return names

    @classmethod
    def _annotation_selector(cls, inputs: dict[str, Any]) -> str:
        return str(inputs.get("annotation_selector", "no") or "no")

    @classmethod
    def _ref_source(cls, inputs: dict[str, Any]) -> str:
        return str(inputs.get("ref_source", "history") or "history")

    @classmethod
    def _seq_selector(cls, inputs: dict[str, Any]) -> str:
        return str(inputs.get("seq_selector", "no") or "no")

    @classmethod
    def _seq_source(cls, inputs: dict[str, Any]) -> str:
        return str(inputs.get("seq_source", "history") or "history")

    @classmethod
    def _out_prefix(cls, inputs: dict[str, Any]) -> str:
        return f"{_out(inputs)}/gffcmp"

    @classmethod
    def _uses_annotation_mode(cls, inputs: dict[str, Any]) -> bool:
        return (
            len(cls._gffinputs(inputs)) == 1
            and cls._annotation_selector(inputs) == "yes"
            and not inputs.get("A")
            and not inputs.get("C")
            and not inputs.get("X")
            and cls._duplication_selector(inputs) == ""
            and not inputs.get("S")
        )

    @classmethod
    def _duplication_selector(cls, inputs: dict[str, Any]) -> str:
        return str(inputs.get("duplication_selector", "") or "")

    @classmethod
    def _refmap_tmap(cls, inputs: dict[str, Any]) -> bool:
        return bool(inputs.get("refmap_tmap", True))

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> str:
        out = _out(inputs)
        setup = [_shell_join(["mkdir", "-p", out])]
        staged_names = cls._staged_input_names(inputs)
        for source, staged_name in zip(cls._gffinputs(inputs), staged_names, strict=False):
            setup.append(_shell_join(["ln", "-s", source, staged_name]))
        if cls._annotation_selector(inputs) == "yes":
            ref = (
                inputs.get("reference_annotation")
                if cls._ref_source(inputs) == "history"
                else inputs.get("reference_index_path", inputs.get("reference_index"))
            )
            setup.append(_shell_join(["ln", "-s", str(ref or ""), "reference_annotation"]))
        if cls._seq_selector(inputs) == "yes":
            seq = (
                inputs.get("ref_genome")
                if cls._seq_source(inputs) == "history"
                else inputs.get("seq_index_path", inputs.get("seq_index"))
            )
            setup.append(_shell_join(["ln", "-s", str(seq or ""), "ref_seq.fa"]))
            if cls._seq_source(inputs) == "history":
                setup.append(_shell_join(["samtools", "faidx", "ref_seq.fa"]))

        cmd = ["gffcompare", "-V", "-o", cls._out_prefix(inputs)]
        if cls._annotation_selector(inputs) == "yes":
            cmd.extend(["-r", "reference_annotation"])
            if inputs.get("R"):
                cmd.append("-R")
            if inputs.get("Q"):
                cmd.append("-Q")
            if inputs.get("strict_match"):
                cmd.extend(["--strict-match", "-e", str(inputs.get("e", 100))])
            discard_single_exon = str(inputs.get("discard_single_exon", "") or "")
            if discard_single_exon:
                cmd.append(discard_single_exon)
            duplication_selector = cls._duplication_selector(inputs)
            if duplication_selector:
                cmd.append(duplication_selector)
                if inputs.get("S"):
                    cmd.append("-S")
            if inputs.get("no_merge"):
                cmd.append("--no-merge")
        if not cls._refmap_tmap(inputs):
            cmd.append("-T")
        if cls._seq_selector(inputs) == "yes":
            cmd.extend(["-s", "ref_seq.fa"])
        cmd.extend(["-d", str(inputs.get("max_dist_group", 100))])
        if inputs.get("chr_stats"):
            cmd.append("--chr-stats")
        cmd.extend(["-p", str(inputs.get("p", "TCONS") or "TCONS")])
        for flag in ("A", "C", "X", "K"):
            if inputs.get(flag):
                cmd.append(f"-{flag}")
        cmd.extend(staged_names)
        return " && ".join([*setup, _shell_join(cmd)])

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        out = Path(output_dir) / cls.NODE_ID
        out.mkdir(parents=True, exist_ok=True)
        outputs = [
            out / ("gffcmp.annotated.gtf" if cls._uses_annotation_mode(inputs) else "gffcmp.combined.gtf"),
            out / "gffcmp.stats",
            out / "gffcmp.loci",
            out / "gffcmp.tracking",
        ]
        if cls._refmap_tmap(inputs):
            staged_names = cls._staged_input_names(inputs)
            if len(staged_names) == 1:
                outputs.append(out / "output.tmap")
                if cls._annotation_selector(inputs) == "yes":
                    outputs.append(out / "output.refmap")
            else:
                for staged_name in staged_names:
                    outputs.append(out / f"gffcmp.{staged_name}.tmap")
                if cls._annotation_selector(inputs) == "yes":
                    for staged_name in staged_names:
                        outputs.append(out / f"gffcmp.{staged_name}.refmap")
        return outputs

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        if not cls._gffinputs(inputs):
            return "at least one gffinputs value is required"
        annotation_selector = cls._annotation_selector(inputs)
        if annotation_selector not in cls.YES_NO_OPTIONS:
            return f"annotation_selector must be one of: {', '.join(cls.YES_NO_OPTIONS)}"
        ref_source = cls._ref_source(inputs)
        if ref_source not in cls.SOURCES:
            return f"ref_source must be one of: {', '.join(cls.SOURCES)}"
        if annotation_selector == "yes":
            if ref_source == "history" and not str(inputs.get("reference_annotation", "")).strip():
                return "reference_annotation is required when ref_source is history"
            reference_index = str(inputs.get("reference_index_path", inputs.get("reference_index", ""))).strip()
            if ref_source == "cached" and not reference_index:
                return "reference_index_path is required when ref_source is cached"
        seq_selector = cls._seq_selector(inputs)
        if seq_selector not in cls.YES_NO_OPTIONS:
            return f"seq_selector must be one of: {', '.join(cls.YES_NO_OPTIONS)}"
        seq_source = cls._seq_source(inputs)
        if seq_source not in cls.SOURCES:
            return f"seq_source must be one of: {', '.join(cls.SOURCES)}"
        if seq_selector == "yes":
            if seq_source == "history" and not str(inputs.get("ref_genome", "")).strip():
                return "ref_genome is required when seq_source is history"
            seq_index = str(inputs.get("seq_index_path", inputs.get("seq_index", ""))).strip()
            if seq_source == "cached" and not seq_index:
                return "seq_index_path is required when seq_source is cached"
        discard_single_exon = str(inputs.get("discard_single_exon", "") or "")
        if discard_single_exon not in cls.DISCARD_SINGLE_EXON_OPTIONS:
            return f"discard_single_exon must be one of: {', '.join(cls.DISCARD_SINGLE_EXON_OPTIONS)}"
        duplication_selector = cls._duplication_selector(inputs)
        if duplication_selector not in cls.DUPLICATION_OPTIONS:
            return f"duplication_selector must be one of: {', '.join(cls.DUPLICATION_OPTIONS)}"
        for name in ("e", "max_dist_group"):
            value = inputs.get(name, "")
            if str(value) == "":
                continue
            try:
                number = int(value)
            except (TypeError, ValueError):
                return f"{name} must be an integer"
            if number < 0:
                return f"{name} must be greater than or equal to 0"
        prefix = str(inputs.get("p", "TCONS") or "TCONS")
        if not re.fullmatch(r"[0-9A-Za-z_-]+", prefix):
            return "p must contain only letters, digits, underscores, and hyphens"
        return True

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "gffinputs": ("GFF_GTF", {"multiple": True, "description": "One or more GTF/GFF3 transcript annotations to compare"}),
            },
            "optional": {
                "element_identifiers": (
                    "STRING",
                    {"default": [], "multiple": True, "description": "Optional Galaxy collection labels for stable query filenames"},
                ),
                "annotation_selector": (
                    "STRING",
                    {"default": "no", "options": cls.YES_NO_OPTIONS, "description": "Use a reference annotation for classification"},
                ),
                "ref_source": (
                    "STRING",
                    {"default": "history", "options": cls.SOURCES, "description": "Reference annotation source"},
                ),
                "reference_annotation": ("GFF_GTF", {"description": "Reference annotation from history"}),
                "reference_index_path": ("GFF_GTF", {"description": "Cached reference annotation path"}),
                "R": ("BOOLEAN", {"default": False, "description": "Apply Sn correction using only overlapped reference transcripts"}),
                "Q": ("BOOLEAN", {"default": False, "description": "Apply Sp correction using only query transcripts overlapping references"}),
                "strict_match": ("BOOLEAN", {"default": False, "description": "Require stricter transcript-level matching"}),
                "e": ("INT", {"default": 100, "min": 0, "description": "Allowed terminal exon end variation for strict matching"}),
                "discard_single_exon": (
                    "STRING",
                    {"default": "", "options": cls.DISCARD_SINGLE_EXON_OPTIONS, "description": "Discard single-exon transfrags or reference transcripts"},
                ),
                "duplication_selector": (
                    "STRING",
                    {"default": "", "options": cls.DUPLICATION_OPTIONS, "description": "Discard duplicate query transfrags"},
                ),
                "S": ("BOOLEAN", {"default": False, "description": "Use strict duplicate checking when duplicate filtering is enabled"}),
                "no_merge": ("BOOLEAN", {"default": False, "description": "Disable close-exon merging"}),
                "seq_selector": (
                    "STRING",
                    {"default": "no", "options": cls.YES_NO_OPTIONS, "description": "Use genomic sequence data for repeat classification"},
                ),
                "seq_source": ("STRING", {"default": "history", "options": cls.SOURCES, "description": "Reference sequence source"}),
                "ref_genome": ("FASTA", {"description": "Reference genome FASTA from history"}),
                "seq_index_path": ("FASTA", {"description": "Cached reference genome FASTA path"}),
                "max_dist_group": ("INT", {"default": 100, "min": 0, "description": "Maximum distance for grouping transcript start sites"}),
                "chr_stats": ("BOOLEAN", {"default": False, "description": "Report stats per reference contig or chromosome"}),
                "refmap_tmap": ("BOOLEAN", {"default": True, "description": "Generate TMAP and RefMap files for each input"}),
                "p": ("STRING", {"default": "TCONS", "description": "Name prefix for consensus transcripts"}),
                "A": ("BOOLEAN", {"default": False, "description": "Discard contained transfrags except alternate TSS cases"}),
                "C": ("BOOLEAN", {"default": False, "description": "Discard matching and contained transfrags"}),
                "X": ("BOOLEAN", {"default": False, "description": "Discard contained transfrags with ends inside container introns"}),
                "K": ("BOOLEAN", {"default": False, "description": "Keep redundant transfrags matching a reference when using -C/-A/-X"}),
            },
            "hidden": {"output": ("STRING", {})},
        }

class UcscMafCoverageNode(CommandNode):
    """Measure genome coverage from UCSC MAF alignments."""

    NODE_ID = "ucsc_mafcoverage"
    DISPLAY_NAME = "mafCoverage"
    REQUIRED_CONDA_PACKAGES = ["ucsc-mafcoverage"]
    CATEGORY = "genomics"
    DESCRIPTION = "Analyse chromosome and genome-wide coverage from sorted UCSC MAF alignments."
    SEARCH_ALIASES = [
        BIONODULO_BUILTIN_ALIAS,
        "UCSC Genome Browser Utilities",
        "ucsc_mafCoverage",
        "ucsc_mafcoverage",
        "mafCoverage",
        "MAF coverage",
        "multiple alignment format",
        "genome-wide coverage",
        "restricted coverage",
    ]
    RETURN_TYPES = ("TXT",)
    RETURN_NAMES = ("output",)
    REQUIRED_EXECUTABLES = ["mafCoverage"]
    DOCUMENTATION_URL = "https://github.com/ucscGenomeBrowser/kent/blob/master/src/hg/mouseStuff/mafCoverage/mafCoverage.c"
    CITATION_DOIS = [UCSC_UTILS_CITATION_DOI]
    CITATION_URLS = [f"{DOI_URL}{UCSC_UTILS_CITATION_DOI}"]
    CITATION_TEXT = UCSC_UTILS_CITATION_TEXT
    VERSION = "482+galaxy0"
    SHELL = True

    RESTRICT_OPTIONS = ["no", "yes"]

    @classmethod
    def _output_path(cls, inputs: dict[str, Any]) -> str:
        return f"{_out(inputs)}/coverage.txt"

    @classmethod
    def _restrict_select(cls, inputs: dict[str, Any]) -> str:
        return str(inputs.get("restrict_select", "no") or "no")

    @classmethod
    def _ucsc_db_connection(cls, inputs: dict[str, Any]) -> str:
        return str(inputs.get("ucsc_db_connection", "ucsc_db_connection.conf") or "ucsc_db_connection.conf")

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> str:
        setup = (
            f"cp {shlex.quote(cls._ucsc_db_connection(inputs))} ${{HOME}}/.hg.conf && "
            "chmod 600 ${HOME}/.hg.conf"
        )
        cmd = [
            "mafCoverage",
            str(inputs.get("genome", "")),
            str(inputs.get("maf_file", "")),
        ]
        if cls._restrict_select(inputs) == "yes":
            cmd.append(f"-restrict={inputs.get('restrict_bed', '')}")
        if str(inputs.get("count", "")) != "":
            cmd.append(f"-count={inputs.get('count')}")
        return f"{setup} && {_shell_join(cmd)} > {shlex.quote(cls._output_path(inputs))}"

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        out = Path(output_dir) / cls.NODE_ID
        out.mkdir(parents=True, exist_ok=True)
        return [out / "coverage.txt"]

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        if not str(inputs.get("maf_file", "")).strip():
            return "maf_file is required"
        if not str(inputs.get("genome", "")).strip():
            return "genome is required"
        restrict_select = cls._restrict_select(inputs)
        if restrict_select not in cls.RESTRICT_OPTIONS:
            return f"restrict_select must be one of: {', '.join(cls.RESTRICT_OPTIONS)}"
        if restrict_select == "yes" and not str(inputs.get("restrict_bed", "")).strip():
            return "restrict_bed is required when restrict_select is yes"
        count = inputs.get("count", "")
        if str(count) != "":
            try:
                count_value = int(count)
            except (TypeError, ValueError):
                return "count must be an integer"
            if count_value < 1:
                return "count must be greater than or equal to 1"
        return True

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "maf_file": ("FILE", {"description": "Sorted UCSC MAF alignment file"}),
                "genome": ("STRING", {"description": "UCSC genome database name"}),
            },
            "optional": {
                "restrict_select": (
                    "STRING",
                    {
                        "default": "no",
                        "options": cls.RESTRICT_OPTIONS,
                        "description": "Restrict coverage calculation to regions in a BED file",
                    },
                ),
                "restrict_bed": (
                    "BED",
                    {"description": "BED intervals used when restricted coverage is enabled"},
                ),
                "count": (
                    "INT",
                    {"default": "", "min": 1, "description": "Threshold for bases covered by at least this many species"},
                ),
                "ucsc_db_connection": (
                    "FILE",
                    {"description": "UCSC database connection configuration copied to ~/.hg.conf"},
                ),
            },
            "hidden": {"output": ("STRING", {})},
        }

class MafToAxtNode(CommandNode):
    """Convert UCSC MAF alignments to AXT format."""

    NODE_ID = "maftoaxt"
    DISPLAY_NAME = "mafToAxt"
    REQUIRED_CONDA_PACKAGES = ["ucsc-maftoaxt"]
    CATEGORY = "genomics"
    DESCRIPTION = "Convert a UCSC MAF multiple-alignment file to AXT pairwise alignment format."
    SEARCH_ALIASES = [
        BIONODULO_BUILTIN_ALIAS,
        "UCSC Genome Browser Utilities",
        "maftoaxt",
        "mafToAxt",
        "MAF to AXT",
        "multiple alignment format",
        "pairwise alignment",
    ]
    RETURN_TYPES = ("FILE",)
    RETURN_NAMES = ("out",)
    REQUIRED_EXECUTABLES = ["mafToAxt"]
    DOCUMENTATION_URL = "https://genome.ucsc.edu/goldenPath/help/axt.html"
    CITATION_DOIS = [UCSC_UTILS_CITATION_DOI]
    CITATION_URLS = [f"{DOI_URL}{UCSC_UTILS_CITATION_DOI}"]
    CITATION_TEXT = UCSC_UTILS_CITATION_TEXT
    VERSION = "482+galaxy0"

    TARGET_MODES = ["", "customTar"]

    @classmethod
    def _target_mode(cls, inputs: dict[str, Any]) -> str:
        return str(inputs.get("tarSeq", "") or "")

    @classmethod
    def _target_sequence(cls, inputs: dict[str, Any]) -> str:
        if cls._target_mode(inputs) == "customTar":
            return str(inputs.get("targetSeq", ""))
        return "first"

    @classmethod
    def _output_path(cls, inputs: dict[str, Any]) -> str:
        return f"{_out(inputs)}/out.axt"

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> str:
        cmd = [
            "mafToAxt",
            str(inputs.get("in_maf", "")),
            cls._target_sequence(inputs),
            str(inputs.get("querySeq", "")),
            cls._output_path(inputs),
        ]
        if inputs.get("stripDb"):
            cmd.append("-stripDb")
        return _shell_join(cmd)

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        out = Path(output_dir) / cls.NODE_ID
        out.mkdir(parents=True, exist_ok=True)
        return [out / "out.axt"]

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        if not str(inputs.get("in_maf", "")).strip():
            return "in_maf is required"
        if not str(inputs.get("querySeq", "")).strip():
            return "querySeq is required"
        target_mode = cls._target_mode(inputs)
        if target_mode not in cls.TARGET_MODES:
            return f"tarSeq must be one of: {', '.join(cls.TARGET_MODES)}"
        if target_mode == "customTar" and not str(inputs.get("targetSeq", "")).strip():
            return "targetSeq is required when tarSeq is customTar"
        return True

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "in_maf": ("FILE", {"description": "UCSC MAF multiple-alignment file to convert"}),
                "querySeq": ("STRING", {"description": "Sequence name to use as the query sequence"}),
            },
            "optional": {
                "tarSeq": (
                    "STRING",
                    {
                        "default": "",
                        "options": cls.TARGET_MODES,
                        "description": "Use the first MAF block sequence or a custom target sequence name",
                    },
                ),
                "targetSeq": (
                    "STRING",
                    {"default": "", "description": "Target sequence name used when tarSeq is customTar"},
                ),
                "stripDb": (
                    "BOOLEAN",
                    {"default": False, "description": "Strip database prefixes up to the first period in sequence names"},
                ),
            },
            "hidden": {"output": ("STRING", {})},
        }

class UcscChainAntiRepeatNode(CommandNode):
    """Remove repeat-dominated UCSC chains."""

    NODE_ID = "ucsc_chainantirepeat"
    DISPLAY_NAME = "chainAntiRepeat"
    REQUIRED_CONDA_PACKAGES = ["ucsc-chainantirepeat"]
    CATEGORY = "genomics"
    DESCRIPTION = "Remove UCSC chains that primarily represent repeats or degenerate DNA."
    SEARCH_ALIASES = [
        BIONODULO_BUILTIN_ALIAS,
        "UCSC Genome Browser Utilities",
        "ucsc_chainantirepeat",
        "chainAntiRepeat",
        "UCSC chain",
        "twoBit",
        "repeat chains",
        "degenerate DNA",
    ]
    RETURN_TYPES = ("FILE",)
    RETURN_NAMES = ("out",)
    REQUIRED_EXECUTABLES = ["chainAntiRepeat"]
    DOCUMENTATION_URL = "https://genome.ucsc.edu/goldenPath/help/chain.html"
    CITATION_DOIS = [UCSC_UTILS_CITATION_DOI]
    CITATION_URLS = [f"{DOI_URL}{UCSC_UTILS_CITATION_DOI}"]
    CITATION_TEXT = UCSC_UTILS_CITATION_TEXT
    VERSION = "482+galaxy0"

    @classmethod
    def _output_path(cls, inputs: dict[str, Any]) -> str:
        return f"{_out(inputs)}/out.chain"

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> str:
        cmd = [
            "chainAntiRepeat",
            str(inputs.get("in_target", "")),
            str(inputs.get("in_query", "")),
            str(inputs.get("in_chain", "")),
            cls._output_path(inputs),
        ]
        if str(inputs.get("minScore", "")) != "":
            cmd.append(f"-minScore={inputs.get('minScore')}")
        if str(inputs.get("noCheckScore", "")) != "":
            cmd.append(f"-noCheckScore={inputs.get('noCheckScore')}")
        return _shell_join(cmd)

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        out = Path(output_dir) / cls.NODE_ID
        out.mkdir(parents=True, exist_ok=True)
        return [out / "out.chain"]

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        for name in ("in_target", "in_query", "in_chain"):
            if not str(inputs.get(name, "")).strip():
                return f"{name} is required"
        for name in ("minScore", "noCheckScore"):
            value = inputs.get(name, "")
            if str(value) != "" and int(value) < 0:
                return f"{name} must be greater than or equal to 0"
        return True

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "in_target": ("FILE", {"description": "TwoBit file containing the target sequence"}),
                "in_query": ("FILE", {"description": "TwoBit file containing the query sequence"}),
                "in_chain": ("FILE", {"description": "UCSC chain file to filter"}),
            },
            "optional": {
                "minScore": (
                    "INT",
                    {"default": "", "min": 0, "description": "Minimum post-repeat score required to pass"},
                ),
                "noCheckScore": (
                    "INT",
                    {"default": "", "min": 0, "description": "Score threshold that passes chains without repeat checks"},
                ),
            },
            "hidden": {"output": ("STRING", {})},
        }
