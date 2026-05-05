from __future__ import annotations

from typing import Any, ClassVar


class BaseNode:
    NODE_ID: ClassVar[str] = ""
    DISPLAY_NAME: ClassVar[str] = ""
    CATEGORY: ClassVar[str] = "Other"
    DESCRIPTION: ClassVar[str] = ""
    SEARCH_ALIASES: ClassVar[list[str]] = []
    RETURN_TYPES: ClassVar[tuple[str, ...]] = ()
    RETURN_NAMES: ClassVar[tuple[str, ...]] = ()
    FUNCTION: ClassVar[str] = "run"
    OUTPUT_NODE: ClassVar[bool] = False
    EXPERIMENTAL: ClassVar[bool] = False
    REQUIRES_EXTERNAL_TOOLS: ClassVar[bool] = False
    REQUIRED_EXECUTABLES: ClassVar[list[str]] = []
    DOCUMENTATION_URL: ClassVar[str | None] = None
    VERSION: ClassVar[str] = "0.1.0"
    ENVIRONMENT: ClassVar[dict[str, Any] | None] = None

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, tuple[str, dict[str, Any]]]]:
        return {"required": {}, "optional": {}, "hidden": {}}

    @classmethod
    def VALIDATE_INPUTS(cls, **kwargs: Any) -> bool | str:
        return True

    @classmethod
    def IS_CHANGED(cls, **kwargs: Any) -> dict[str, Any]:
        return kwargs

    @classmethod
    def PLAN_OUTPUTS(cls, node_dir: Any, params: dict[str, Any], inputs: dict[str, Any]) -> dict[str, Any]:
        outputs: dict[str, Any] = {}
        for name, typ in zip(cls.RETURN_NAMES, cls.RETURN_TYPES, strict=False):
            outputs[name] = str(node_dir / _default_output_name(name, typ))
        return outputs

    @classmethod
    def metadata(cls) -> dict[str, Any]:
        inputs = cls.INPUT_TYPES()
        outputs = [
            {"name": name, "type": typ}
            for name, typ in zip(cls.RETURN_NAMES, cls.RETURN_TYPES, strict=False)
        ]
        return {
            "id": cls.NODE_ID,
            "display_name": cls.DISPLAY_NAME or cls.NODE_ID,
            "category": cls.CATEGORY,
            "description": cls.DESCRIPTION,
            "inputs": _serialize_inputs(inputs),
            "outputs": outputs,
            "search_aliases": cls.SEARCH_ALIASES,
            "experimental": cls.EXPERIMENTAL,
            "output_node": cls.OUTPUT_NODE,
            "requires_external_tools": cls.REQUIRES_EXTERNAL_TOOLS,
            "required_executables": cls.REQUIRED_EXECUTABLES,
            "documentation_url": cls.DOCUMENTATION_URL,
            "environment": cls.ENVIRONMENT,
            "version": cls.VERSION,
        }

    def run(self, context: Any = None, **kwargs: Any) -> dict[str, Any]:
        raise NotImplementedError


def _serialize_inputs(inputs: dict[str, dict[str, tuple[str, dict[str, Any]]]]) -> dict[str, dict[str, dict[str, Any]]]:
    serialized: dict[str, dict[str, dict[str, Any]]] = {}
    for section, fields in inputs.items():
        serialized[section] = {}
        for name, spec in fields.items():
            typ, options = spec
            serialized[section][name] = {"type": typ, **options}
    return serialized


def _default_output_name(name: str, typ: str) -> str:
    if typ.endswith("_DIR") or typ in {"DIRECTORY", "INDEX_DIR", "QC_REPORT_DIR"}:
        return name
    extensions = {
        "HTML_REPORT": ".html",
        "JSON_REPORT": ".json",
        "MULTIQC_REPORT": ".html",
        "FASTQ": ".fastq.gz",
        "FASTQ_LIST": ".fastq.gz",
        "BAM": ".bam",
        "BAI": ".bai",
        "FASTA": ".fa",
        "FILE": ".txt",
        "STRING": ".txt",
    }
    return f"{name}{extensions.get(typ, '.txt')}"
