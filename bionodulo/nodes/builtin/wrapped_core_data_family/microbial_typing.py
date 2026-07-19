"""Focused microbial typing node contracts."""
# ruff: noqa: F403,F405
from __future__ import annotations

from bionodulo.nodes.builtin._wrapped_tool_utils import *

from .evidence import pin_contract

class AutoBIGSCliNode(CommandNode):
    """Perform MLST typing or list schemes from BIGSdb sequence definition databases."""

    NODE_ID = "autobigs-cli"
    DISPLAY_NAME = "autoBIGS.cli"
    REQUIRED_CONDA_PACKAGES = ["autobigs-cli"]
    CATEGORY = "typing"
    DESCRIPTION = "Automated MLST typing with BIGSdb sequence definition databases."
    SEARCH_ALIASES = [
        BIONODULO_BUILTIN_ALIAS,
        "autobigs",
        "autobigs-cli",
        "autoBIGS",
        "autoBIGS.cli",
        "MLST",
        "BIGSdb",
        "PubMLST",
        "Institut Pasteur",
        "sequence typing",
        "scheme",
    ]
    RETURN_TYPES = ("CSV", "CSV")
    RETURN_NAMES = ("mlst_profiles_output", "info_schemes_out")
    REQUIRED_EXECUTABLES = ["autoBIGS"]
    DOCUMENTATION_URL = AUTOBIGS_CLI_CITATION_URL
    CITATION_DOIS: list[str] = []
    CITATION_URLS = [AUTOBIGS_CLI_CITATION_URL]
    CITATION_TEXT = AUTOBIGS_CLI_CITATION_TEXT
    VERSION = "0.6.2+galaxy0"
    SHELL = True

    OPERATIONS = ["st", "info"]
    DATABASE_ORIGINS = ["pubmlst", "institutpasteur"]

    @classmethod
    def _operation(cls, inputs: dict[str, Any]) -> str:
        return str(inputs.get("operation", "st") or "st")

    @classmethod
    def _database_origin(cls, inputs: dict[str, Any]) -> str:
        return str(inputs.get("database_origin", "pubmlst") or "pubmlst")

    @classmethod
    def _mlst_output_path(cls, inputs: dict[str, Any]) -> str:
        return f"{_out(inputs)}/mlst_profiles_output.csv"

    @classmethod
    def _info_output_path(cls, inputs: dict[str, Any]) -> str:
        return f"{_out(inputs)}/info_schemes_out.csv"

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> str:
        bigsdb = str(inputs.get("bigsdb", ""))
        if cls._operation(inputs) == "info":
            return _shell_join(
                [
                    "autoBIGS",
                    "info",
                    "--retrieve-bigsdb-schemes",
                    bigsdb,
                    "--csv",
                    cls._info_output_path(inputs),
                ]
            )

        cmd = [
            "autoBIGS",
            "st",
            "--scheme-name",
            str(inputs.get("scheme", "MLST") or "MLST"),
        ]
        cmd.extend(_as_list(inputs.get("fasta")))
        cmd.extend([bigsdb, cls._mlst_output_path(inputs)])
        return _shell_join(cmd)

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        out = Path(output_dir) / cls.NODE_ID
        out.mkdir(parents=True, exist_ok=True)
        return [out / "mlst_profiles_output.csv", out / "info_schemes_out.csv"]

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        if not str(inputs.get("bigsdb", "")).strip():
            return "bigsdb is required"
        operation = cls._operation(inputs)
        if operation not in cls.OPERATIONS:
            return f"operation must be one of: {', '.join(cls.OPERATIONS)}"
        database_origin = cls._database_origin(inputs)
        if database_origin not in cls.DATABASE_ORIGINS:
            return f"database_origin must be one of: {', '.join(cls.DATABASE_ORIGINS)}"
        if operation == "st":
            if not _as_list(inputs.get("fasta")):
                return "fasta is required for st operation"
            if not str(inputs.get("scheme", "MLST")).strip():
                return "scheme is required for st operation"
        return True

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "bigsdb": (
                    "STRING",
                    {"description": "BIGSdb sequence definition database name, for example pubmlst_bordetella_seqdef"},
                ),
            },
            "optional": {
                "database_origin": (
                    "STRING",
                    {
                        "default": "pubmlst",
                        "options": cls.DATABASE_ORIGINS,
                        "description": "Remote BIGSdb source used to choose the sequence definition database",
                    },
                ),
                "operation": (
                    "STRING",
                    {"default": "st", "options": cls.OPERATIONS, "description": "Run sequence typing or list supported schemes"},
                ),
                "fasta": (
                    "FASTA",
                    {"default": [], "is_list": True, "description": "FASTA file or files to type in st mode"},
                ),
                "scheme": (
                    "STRING",
                    {"default": "MLST", "description": "BIGSdb SeqDef scheme name used for sequence typing"},
                ),
            },
            "hidden": {"output": ("STRING", {})},
        }

class MLSTNode(CommandNode):
    """Scan assemblies against PubMLST typing schemes with mlst."""

    NODE_ID = "mlst"
    DISPLAY_NAME = "MLST"
    REQUIRED_CONDA_PACKAGES = ["mlst"]
    CATEGORY = "typing"
    DESCRIPTION = "Scan genome assemblies against PubMLST schemes with Torsten Seemann's MLST."
    SEARCH_ALIASES = [
        BIONODULO_BUILTIN_ALIAS,
        "MLST",
        "mlst",
        "PubMLST",
        "sequence typing",
        "scheme typing",
        "allele profile",
        "novel alleles",
    ]
    RETURN_TYPES = ("TSV", "FASTA")
    RETURN_NAMES = ("report", "novel_alleles")
    REQUIRED_EXECUTABLES = ["mlst"]
    DOCUMENTATION_URL = MLST_CITATION_URL
    CITATION_DOIS: list[str] = []
    CITATION_URLS = [MLST_CITATION_URL]
    CITATION_TEXT = MLST_CITATION_TEXT
    VERSION = "2.22.0"
    SHELL = True

    ADVANCED_OPTIONS = ["simple", "advanced"]
    SET_SCHEME_OPTIONS = ["auto", "list", "manual"]

    @staticmethod
    def _label_for(path: str, label: str | None = None) -> str:
        return str(label or Path(path).name or "input.fasta")

    @classmethod
    def _staged_inputs(cls, inputs: dict[str, Any]) -> list[tuple[str, str]]:
        paths = _as_list(inputs.get("input_files"))
        labels = _as_list(inputs.get("input_labels"))
        return [
            (path, cls._label_for(path, labels[index] if index < len(labels) else None))
            for index, path in enumerate(paths)
        ]

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> str:
        staged_inputs = cls._staged_inputs(inputs)
        parts = [_shell_join(["ln", "-s", path, label]) for path, label in staged_inputs]
        cmd = ["mlst", "--nopath", "--threads", "${GALAXY_SLOTS:-1}"]
        if str(inputs.get("advanced", "simple")) == "advanced":
            if inputs.get("minid") not in (None, ""):
                cmd.append(f"--minid={inputs['minid']}")
            if inputs.get("mincov") not in (None, ""):
                cmd.append(f"--mincov={inputs['mincov']}")
            if inputs.get("novel"):
                cmd.extend(["--novel", f"{_out(inputs)}/novel_alleles.fasta"])
            set_scheme = str(inputs.get("set_scheme", "auto"))
            if set_scheme == "auto":
                if inputs.get("minscore") not in (None, ""):
                    cmd.append(f"--minscore={inputs['minscore']}")
                if str(inputs.get("exclude", "")).strip():
                    cmd.extend(["--exclude", str(inputs.get("exclude"))])
            elif set_scheme in {"list", "manual"}:
                if str(inputs.get("scheme", "")).strip():
                    cmd.append(f"--scheme={inputs['scheme']}")
                if inputs.get("legacy", True):
                    cmd.append("--legacy")
        cmd.extend(label for _, label in staged_inputs)
        cmd.extend([">", f"{_out(inputs)}/report.tsv"])
        parts.append(_shell_join(cmd).replace("'${GALAXY_SLOTS:-1}'", "${GALAXY_SLOTS:-1}"))
        return " && ".join(parts)

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        out = Path(output_dir) / cls.NODE_ID
        out.mkdir(parents=True, exist_ok=True)
        outputs = [out / "report.tsv"]
        if inputs.get("novel"):
            outputs.append(out / "novel_alleles.fasta")
        return outputs

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        if not _as_list(inputs.get("input_files")):
            return "at least one input_files value is required"
        advanced = str(inputs.get("advanced", "simple"))
        if advanced not in cls.ADVANCED_OPTIONS:
            return f"advanced must be one of: {', '.join(cls.ADVANCED_OPTIONS)}"
        if advanced == "advanced":
            for key in ("minid", "mincov", "minscore"):
                if inputs.get(key) in (None, ""):
                    continue
                value = int(inputs[key])
                if value < 0 or value > 100:
                    return f"{key} must be between 0 and 100"
            set_scheme = str(inputs.get("set_scheme", "auto"))
            if set_scheme not in cls.SET_SCHEME_OPTIONS:
                return f"set_scheme must be one of: {', '.join(cls.SET_SCHEME_OPTIONS)}"
            if set_scheme in {"list", "manual"} and not str(inputs.get("scheme", "")).strip():
                return "scheme is required when set_scheme is list or manual"
        return True

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "input_files": (
                    "FASTA",
                    {
                        "multiple": True,
                        "description": "FASTA or GenBank genome assembly files to scan with mlst",
                    },
                ),
            },
            "optional": {
                "advanced": (
                    "STRING",
                    {"default": "simple", "options": cls.ADVANCED_OPTIONS, "description": "Use default or advanced mlst parameters"},
                ),
                "minid": ("INT", {"default": 95, "min": 0, "max": 100, "advanced": True}),
                "mincov": ("INT", {"default": 10, "min": 0, "max": 100, "advanced": True}),
                "novel": ("BOOLEAN", {"default": False, "description": "Write novel alleles to FASTA", "advanced": True}),
                "set_scheme": (
                    "STRING",
                    {"default": "auto", "options": cls.SET_SCHEME_OPTIONS, "description": "Auto-detect, select, or manually set scheme"},
                ),
                "minscore": ("INT", {"default": 50, "min": 0, "max": 100, "advanced": True}),
                "exclude": ("STRING", {"default": "", "description": "Comma-separated schemes to ignore in auto mode", "advanced": True}),
                "scheme": ("STRING", {"default": "", "description": "PubMLST scheme for list/manual modes"}),
                "legacy": ("BOOLEAN", {"default": True, "description": "Include allele header row when scheme is set"}),
                "input_labels": (
                    "STRING",
                    {
                        "default": [],
                        "is_list": True,
                        "description": "Optional Galaxy element identifiers used as readable output names",
                        "advanced": True,
                    },
                ),
            },
            "hidden": {"output": ("STRING", {})},
        }

class MLSTListNode(CommandNode):
    """List MLST schemes and optional allele details."""

    NODE_ID = "mlst_list"
    DISPLAY_NAME = "MLST List"
    REQUIRED_CONDA_PACKAGES = ["mlst"]
    CATEGORY = "typing"
    DESCRIPTION = "List available PubMLST schemes and optional allele details from the MLST database."
    SEARCH_ALIASES = [
        BIONODULO_BUILTIN_ALIAS,
        "MLST List",
        "mlst --list",
        "mlst --longlist",
        "PubMLST schemes",
        "allele list",
    ]
    RETURN_TYPES = ("TXT",)
    RETURN_NAMES = ("report",)
    REQUIRED_EXECUTABLES = ["mlst"]
    DOCUMENTATION_URL = MLST_CITATION_URL
    CITATION_DOIS: list[str] = []
    CITATION_URLS = [MLST_CITATION_URL]
    CITATION_TEXT = MLST_CITATION_TEXT
    VERSION = "2.22.0"
    SHELL = True

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> str:
        return _shell_join([
            "mlst",
            "--longlist" if inputs.get("list_type") else "--list",
            ">",
            f"{_out(inputs)}/report.txt",
        ])

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        out = Path(output_dir) / cls.NODE_ID
        out.mkdir(parents=True, exist_ok=True)
        return [out / "report.txt"]

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "optional": {
                "list_type": ("BOOLEAN", {"default": False, "description": "Include allele columns with mlst --longlist"}),
            },
            "hidden": {"output": ("STRING", {})},
        }

class SeqSero2Node(CommandNode):
    """Predict Salmonella serotypes with SeqSero2."""

    NODE_ID = "seqsero2"
    DISPLAY_NAME = "SeqSero2"
    REQUIRED_CONDA_PACKAGES = ["seqsero2"]
    CATEGORY = "typing"
    DESCRIPTION = "Predict Salmonella serotypes from raw sequencing reads or genome assemblies."
    SEARCH_ALIASES = [
        BIONODULO_BUILTIN_ALIAS,
        "SeqSero2",
        "seqsero2",
        "Salmonella serotype",
        "Salmonella typing",
        "serotype prediction",
        "allele micro-assembly",
        "k-mer serotyping",
    ]
    RETURN_TYPES = ("TSV", "TXT")
    RETURN_NAMES = ("results", "log")
    REQUIRED_EXECUTABLES = ["SeqSero2_package.py"]
    DOCUMENTATION_URL = "https://github.com/denglab/SeqSero2"
    CITATION_DOIS = ["10.1128/AEM.01746-19"]
    CITATION_URLS = [f"{DOI_URL}10.1128/AEM.01746-19"]
    CITATION_TEXT = "SeqSero2: rapid and improved Salmonella serotype determination using whole-genome sequencing data."
    VERSION = "1.3.2+galaxy0"
    SHELL = True

    INPUT_TYPES_OPTIONS = ("paired", "collection", "assembly", "single", "nanopore")
    WORKFLOW_OPTIONS = ("a", "k")
    TYPE_VALUES = {
        "paired": "2",
        "collection": "2",
        "single": "3",
        "assembly": "4",
        "nanopore": "5",
    }

    @classmethod
    def _input_type(cls, inputs: dict[str, Any]) -> str:
        return str(inputs.get("input_type", "") or "")

    @classmethod
    def _workflow(cls, inputs: dict[str, Any]) -> str:
        input_type = cls._input_type(inputs)
        if input_type in {"assembly", "nanopore"}:
            return "k"
        return str(inputs.get("workflow", "a") or "a")

    @staticmethod
    def _extension(path: str, input_type: str) -> str:
        suffixes = "".join(Path(path).suffixes).lower()
        gz = suffixes.endswith(".gz")
        base = ".fasta" if input_type in {"assembly", "nanopore"} else ".fastq"
        return f"{base}.gz" if gz else base

    @classmethod
    def _stage_name(cls, path: str, input_type: str, label: str = "", suffix: str = "") -> str:
        stem = _safe_identifier(label or Path(path).stem or "input")
        if suffix:
            stem = f"{stem}_{suffix}"
        return f"{stem}{cls._extension(path, input_type)}"

    @classmethod
    def _collection_reads(cls, inputs: dict[str, Any]) -> tuple[str, str, str]:
        collection = inputs.get("input_collection")
        if isinstance(collection, dict):
            forward = str(collection.get("forward", collection.get("read1", collection.get("reads_1", ""))))
            reverse = str(collection.get("reverse", collection.get("read2", collection.get("reads_2", ""))))
            label = str(collection.get("name", collection.get("element_identifier", forward or "collection")))
            return forward, reverse, label
        reads = _as_list(collection)
        return (reads[0] if reads else "", reads[1] if len(reads) > 1 else "", reads[0] if reads else "collection")

    @classmethod
    def _staged_inputs(cls, inputs: dict[str, Any]) -> list[tuple[str, str]]:
        input_type = cls._input_type(inputs)
        if input_type == "collection":
            read1, read2, label = cls._collection_reads(inputs)
            return [
                (read1, cls._stage_name(read1, input_type, label, "forward")),
                (read2, cls._stage_name(read2, input_type, label, "reverse")),
            ]
        read1 = str(inputs.get("read1", ""))
        label1 = str(inputs.get("read1_label", "") or Path(read1).stem or "input")
        if input_type == "paired":
            read2 = str(inputs.get("read2", ""))
            label2 = str(inputs.get("read2_label", "") or label1)
            return [
                (read1, cls._stage_name(read1, input_type, label1, "forward")),
                (read2, cls._stage_name(read2, input_type, label2, "reverse")),
            ]
        return [(read1, cls._stage_name(read1, input_type, label1))]

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> str:
        out = _out(inputs)
        commands = [_shell_join(["mkdir", "-p", out])]
        staged = cls._staged_inputs(inputs)
        commands.extend(_shell_join(["ln", "-s", source, staged_name]) for source, staged_name in staged)
        cmd = [
            "SeqSero2_package.py",
            "-m",
            cls._workflow(inputs),
            "-t",
            cls.TYPE_VALUES[cls._input_type(inputs)],
            "-i",
            staged[0][1],
        ]
        if cls._input_type(inputs) in {"paired", "collection"}:
            cmd.append(staged[1][1])
        cmd.extend(["-p", "${GALAXY_SLOTS:-4}", "-d", f"{out}/output"])
        commands.append(_shell_join(cmd).replace("'${GALAXY_SLOTS:-4}'", "${GALAXY_SLOTS:-4}"))
        return " && ".join(commands)

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        out = Path(output_dir) / cls.NODE_ID
        out.mkdir(parents=True, exist_ok=True)
        outputs = [out / "SeqSero_result.tsv"]
        if inputs.get("logfile"):
            outputs.append(out / "SeqSero_log.txt")
        return outputs

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        input_type = cls._input_type(inputs)
        if input_type not in cls.INPUT_TYPES_OPTIONS:
            return f"input_type must be one of: {', '.join(cls.INPUT_TYPES_OPTIONS)}"
        if input_type == "collection":
            read1, read2, _ = cls._collection_reads(inputs)
            if not read1 or not read2:
                return "input_collection with forward and reverse reads is required for collection input"
        else:
            if not str(inputs.get("read1", "")).strip():
                return f"read1 is required for {input_type} input"
            if input_type == "paired" and not str(inputs.get("read2", "")).strip():
                return "read2 is required for paired input"
        workflow = cls._workflow(inputs)
        if workflow not in cls.WORKFLOW_OPTIONS:
            return f"workflow must be one of: {', '.join(cls.WORKFLOW_OPTIONS)}"
        return True

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "input_type": (
                    "STRING",
                    {
                        "default": "paired",
                        "options": list(cls.INPUT_TYPES_OPTIONS),
                        "description": "Galaxy SeqSero2 input layout",
                    },
                ),
                "read1": ("FILE", {"description": "Forward, single/interleaved, assembly, or nanopore input"}),
                "read2": ("FASTQ", {"description": "Reverse reads for paired input"}),
            },
            "optional": {
                "input_collection": (
                    "JSON",
                    {"default": {}, "description": "Paired collection with forward and reverse reads"},
                ),
                "workflow": (
                    "STRING",
                    {
                        "default": "a",
                        "options": list(cls.WORKFLOW_OPTIONS),
                        "description": "SeqSero2 workflow for raw reads: allele micro-assembly or k-mer",
                    },
                ),
                "logfile": (
                    "BOOLEAN",
                    {"default": False, "description": "Return SeqSero2 log output"},
                ),
                "read1_label": (
                    "STRING",
                    {"default": "", "description": "Optional Galaxy element identifier for read1", "advanced": True},
                ),
                "read2_label": (
                    "STRING",
                    {"default": "", "description": "Optional Galaxy element identifier for read2", "advanced": True},
                ),
            },
            "hidden": {"output": ("STRING", {})},
        }

pin_contract(AutoBIGSCliNode)
pin_contract(MLSTNode)
pin_contract(MLSTListNode)
pin_contract(SeqSero2Node)

__all__ = ['AutoBIGSCliNode', 'MLSTNode', 'MLSTListNode', 'SeqSero2Node']
