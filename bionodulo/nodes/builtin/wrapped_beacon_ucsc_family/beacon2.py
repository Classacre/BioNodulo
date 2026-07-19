"""Beacon2 import and conversion nodes."""
# ruff: noqa: F403,F405
from __future__ import annotations

from bionodulo.nodes.builtin._wrapped_tool_utils import *
from bionodulo.core.credentials import resolve_secret_value
from bionodulo.nodes.builtin.wrapped_beacon_ucsc_family.adapter import (
    BEACON2_IMPORT_SDIST_SHA256,
    BEACON2_RI_GIT_COMMIT,
    BEACON2_RI_GIT_URL,
    asset_path,
    pin_contract,
)

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
        return f"{_out(inputs)}/.beacon2_db_auth.json"

    @classmethod
    def _credentials_json(cls, inputs: dict[str, Any]) -> str:
        credentials = {
            "db_auth_source": str(inputs.get("db_auth_source", "")),
            "db_user": str(inputs.get("db_user", "")),
            "db_password": str(inputs.get("db_password", "")),
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
        cleanup = shlex.quote(_shell_join(["rm", "-f", credentials_path]))
        config = (
            f"umask 077 && trap {cleanup} EXIT && "
            f"cat > {shlex.quote(credentials_path)} <<'JSON'\n{cls._credentials_json(inputs)}\nJSON\n"
        )
        return " && ".join(
            [
                f"mkdir -p {shlex.quote(out)}",
                _shell_join(["ln", "-s", input_json, staged_input]),
                f"{config}{_shell_join(cls._import_cmd(inputs, credentials_path))}",
            ]
        )

    async def run(self, **kwargs: Any) -> Any:
        context = kwargs.get("context")
        kwargs["db_auth_source"] = resolve_secret_value(
            kwargs.get("db_auth_source"), context, "beacon2_db_auth_source"
        )
        kwargs["db_user"] = resolve_secret_value(kwargs.get("db_user"), context, "beacon2_db_user")
        kwargs["db_password"] = resolve_secret_value(
            kwargs.get("db_password"), context, "beacon2_db_password"
        )
        return await super().run(**kwargs)

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
        for name in ("db_auth_source", "db_user", "db_password"):
            if not str(inputs.get(name, "")).strip():
                return f"{name} is required directly or through a configured credential"
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
                    {
                        "default": "",
                        "advanced": True,
                        "description": "MongoDB auth source or credential:// reference",
                    },
                ),
                "db_user": (
                    "STRING",
                    {"default": "", "advanced": True, "description": "MongoDB username or credential:// reference"},
                ),
                "db_password": (
                    "STRING",
                    {
                        "default": "",
                        "advanced": True,
                        "password": True,
                        "description": "MongoDB password or credential:// reference",
                    },
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
    RUN_IN_NODE_OUTPUT_DIR = True

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
    REQUIRED_EXECUTABLES = ["vcf2bff.pl", "python"]
    DOCUMENTATION_URL = "https://github.com/galaxyproject/tools-iuc/tree/main/tools/beacon2"
    CITATION_DOIS = [BEACON2_DOI]
    CITATION_URLS = [f"{DOI_URL}{BEACON2_DOI}"]
    CITATION_TEXT = BEACON2_CITATION_TEXT
    VERSION = "2.0.0+galaxy0"
    SHELL = True
    RUN_IN_NODE_OUTPUT_DIR = True

    FORMATS = ["bff"]

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
            ".",
            "--dataset-id",
            str(inputs.get("dataset_id", "")),
            "--genome",
            str(inputs.get("genome", "")),
        ]
        canonicalizer = asset_path("canonicalize_vcf2bff.py")
        generated = f"{out}/genomicVariationsVcf.json.gz"
        normalize = ["python", canonicalizer, generated, f"{out}/genomicVariationsVcf.json"]
        return f"{setup} && {_shell_join(cmd)} && {_shell_join(normalize)}"

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
            return "format must be bff because hash/json modes do not produce the declared JSON artifact"
        if not str(inputs.get("dataset_id", "")).strip():
            return "dataset_id is required"
        if not str(inputs.get("genome", "")).strip():
            return "genome is required"
        return True

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "input": ("FILE", {"description": "Annotated compressed VCF produced by bcftools, SnpEff, or SnpSift"}),
                "dataset_id": ("STRING", {"description": "Dataset ID assigned to generated genomic variations records"}),
                "genome": (
                    "STRING",
                    {"description": "Reference genome label used to annotate the VCF, such as hs37 or hg38"},
                ),
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
            },
            "hidden": {"output": ("STRING", {})},
        }


pin_contract(
    [Beacon2ImportNode],
    runtime_version="2.2.4",
    package_constraint="beacon2-import==2.2.4",
    source_archive_sha256=BEACON2_IMPORT_SDIST_SHA256,
)
Beacon2ImportNode.UPSTREAM_VCS_STATUS = "No upstream VCS URL is published by the 2.2.4 PyPI sdist."
pin_contract(
    [Beacon2Csv2XlsxNode, Beacon2Pxf2BffNode, Beacon2Vcf2BffNode],
    runtime_version="2.0.0",
    runtime_git_url=BEACON2_RI_GIT_URL,
    runtime_git_commit=BEACON2_RI_GIT_COMMIT,
    package_constraint="beacon2-ri-tools==2.0.0",
)
