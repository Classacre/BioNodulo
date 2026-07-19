"""pySBOL3 1.1 design import and summary."""

from __future__ import annotations

import textwrap
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from .adapter import SyntheticBiologyCommandNode, path_value, validate_bool, validate_choice


class SBOLDesignImportNode(SyntheticBiologyCommandNode):
    """Read, optionally validate, normalize, and summarize an SBOL document."""

    NODE_ID = "sbol_design_import"
    DISPLAY_NAME = "SBOL Design Import"
    DESCRIPTION = "Import, normalize, and summarize SBOL designs with pySBOL3 1.1."
    SEARCH_ALIASES = ["BioNodulo builtin", "SBOL", "pySBOL3", "synthetic biology", "biocad"]
    RETURN_TYPES = ("SBOL", "JSON")
    RETURN_NAMES = ("normalized_sbol", "summary")
    REQUIRED_EXECUTABLES = ["python"]
    REQUIRED_CONDA_PACKAGES = ["pysbol3"]
    CONDA_PACKAGE_CONSTRAINTS = {"pysbol3": "1.1"}
    PACKAGE_CONSTRAINT = "pysbol3 = 1.1"
    REQUIRED_PATH_INPUTS = ("sbol_file",)
    VERSION = "1.1"
    GIT_COMMIT = "c84ccd16028821f8668473758031e1b6dcdcd628"
    GIT_URL = "https://github.com/SynBioDex/pySBOL3.git"
    SOURCE_URL = f"https://github.com/SynBioDex/pySBOL3/tree/{GIT_COMMIT}"
    RELEASE_TAG_URL = "https://github.com/SynBioDex/pySBOL3/tree/v1.1"
    DOCUMENTATION_URL = "https://pysbol3.readthedocs.io/en/v1.1/"
    LICENSE = "MIT"
    LICENSE_URL = f"https://github.com/SynBioDex/pySBOL3/blob/{GIT_COMMIT}/LICENSE.txt"
    UPSTREAM_SOURCE = "setup.py; sbol3/constants.py; sbol3/config.py; sbol3/document.py; sbol3/validation.py"
    SOURCE_AUTHORITIES = {
        "version_and_dependencies": "setup.py",
        "format_constants": "sbol3/constants.py",
        "namespace_validation": "sbol3/config.py:set_namespace",
        "read_write_validation": "sbol3/document.py:Document.read,Document.write,Document.validate",
        "validation_report": "sbol3/validation.py:ValidationReport",
        "manual": DOCUMENTATION_URL,
        "license": LICENSE_URL,
    }
    AUDIT_STATUS = "contract-checked-no-runtime-execution"
    QUARANTINE_STATUS = "evidence-only-no-runtime-execution"
    VALIDATION_SEMANTICS = (
        "Document.validate returns a ValidationReport; findings are serialized into summary.json "
        "and do not themselves raise or make the process exit non-zero."
    )
    EXIT_SEMANTICS = (
        "Invalid namespaces, unreadable or unparseable RDF, unsupported formats, serialization "
        "errors, and summary I/O errors raise and make Python exit non-zero. Validation findings "
        "are reported in summary.json rather than treated as process failures."
    )
    FORMATS = ("xml", "nt11", "sorted nt", "ttl", "json-ld")
    FORMAT_EXTENSIONS = {
        "xml": ".xml",
        "nt11": ".nt",
        "sorted nt": ".nt",
        "ttl": ".ttl",
        "json-ld": ".json",
    }
    SCRIPT = textwrap.dedent(
        """\
        import json
        import sys
        from pathlib import Path

        import sbol3

        input_path, output_path, summary_path, output_format, namespace, validate = sys.argv[1:]
        if namespace:
            sbol3.set_namespace(namespace)

        document = sbol3.Document()
        document.read(input_path)
        report = document.validate() if validate == "true" else None
        document.write(output_path, file_format=output_format)

        def identity(obj):
            return str(getattr(obj, "identity", obj))

        components = [obj for obj in document.objects if isinstance(obj, sbol3.Component)]
        sequences = [obj for obj in document.objects if isinstance(obj, sbol3.Sequence)]
        interactions = [
            interaction
            for component in components
            for interaction in (getattr(component, "interactions", None) or [])
        ]
        summary = {
            "input_file": input_path,
            "normalized_sbol": output_path,
            "output_format": output_format,
            "object_count": len(document.objects),
            "components": [identity(obj) for obj in components],
            "sequences": [identity(obj) for obj in sequences],
            "interactions": [identity(obj) for obj in interactions],
            "validation_errors": [str(item) for item in getattr(report, "errors", [])],
            "validation_warnings": [str(item) for item in getattr(report, "warnings", [])],
        }
        Path(summary_path).write_text(
            json.dumps(summary, indent=2, sort_keys=True) + "\\n",
            encoding="utf-8",
        )
        """
    )

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "sbol_file": ("FILE", {"description": "SBOL RDF document"}),
            },
            "optional": {
                "namespace": (
                    "STRING",
                    {"default": "", "description": "Default namespace for generated identities"},
                ),
                "validate": ("BOOLEAN", {"default": True}),
                "output_format": (
                    "STRING",
                    {"default": "xml", "options": list(cls.FORMATS)},
                ),
            },
            "hidden": {"output": ("STRING", {})},
        }

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        validation = super().VALIDATE_INPUTS(inputs)
        if validation is not True:
            return validation
        validation = validate_bool(inputs.get("validate", True), "validate")
        if validation is not True:
            return validation
        validation = validate_choice(inputs.get("output_format", "xml"), "output_format", cls.FORMATS)
        if validation is not True:
            return validation
        namespace = str(inputs.get("namespace", "") or "")
        if namespace:
            parsed = urlparse(namespace)
            if not (parsed.scheme and parsed.netloc):
                return "Input 'namespace' must be an absolute URL when provided"
        return True

    @classmethod
    def _output_paths(cls, inputs: dict[str, Any], node_dir: Path) -> tuple[Path, Path]:
        output_format = str(inputs.get("output_format", "xml"))
        return node_dir / f"normalized{cls.FORMAT_EXTENSIONS[output_format]}", node_dir / "summary.json"

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        return list(cls._output_paths(inputs, cls.node_output_dir(output_dir)))

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        cls.require_valid_inputs(inputs)
        normalized, summary = cls._output_paths(inputs, Path(str(inputs.get("output", "."))))
        return [
            "python",
            "-c",
            cls.SCRIPT,
            path_value(inputs["sbol_file"]),
            str(normalized),
            str(summary),
            str(inputs.get("output_format", "xml")),
            str(inputs.get("namespace", "") or ""),
            str(inputs.get("validate", True)).lower(),
        ]
