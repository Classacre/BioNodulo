"""Explicit standard CWL File object workflow input."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Mapping
from urllib.parse import unquote, urlsplit

from .adapter import CopyInputNode


_MAX_FORMAT_URI_BYTES = 2048
_MAX_SECONDARY_FILES = 256
_MAX_LOCATION_BYTES = 8192


def _format_uri(value: object, *, field: str) -> str | None:
    if value in (None, ""):
        return None
    if type(value) is not str or not 1 <= len(value.encode("utf-8")) <= _MAX_FORMAT_URI_BYTES:
        raise ValueError(f"{field} must be an absolute URI of at most {_MAX_FORMAT_URI_BYTES} bytes")
    if any(character.isspace() or not character.isprintable() for character in value):
        raise ValueError(f"{field} must be one absolute printable URI")
    try:
        parsed = urlsplit(value)
    except ValueError as error:
        raise ValueError(f"{field} must be one absolute printable URI") from error
    if not parsed.scheme or parsed.username is not None or parsed.password is not None:
        raise ValueError(f"{field} must be one credential-free absolute URI")
    return value


def _secondary_objects(value: object) -> tuple[dict[str, object], ...]:
    if value in (None, ""):
        return ()
    if isinstance(value, str):
        try:
            value = json.loads(value)
        except json.JSONDecodeError as error:
            raise ValueError(f"secondary_files is not valid JSON: {error.msg}") from error
    if not isinstance(value, list) or len(value) > _MAX_SECONDARY_FILES:
        raise ValueError(f"secondary_files must be a JSON array of at most {_MAX_SECONDARY_FILES} File objects")
    selected: list[dict[str, object]] = []
    for index, raw in enumerate(value):
        if not isinstance(raw, Mapping) or raw.get("class") != "File":
            raise ValueError(f"secondary_files[{index}] must be a CWL File object")
        if "secondaryFiles" in raw:
            raise ValueError(f"secondary_files[{index}] cannot contain nested secondaryFiles")
        path_keys = [key for key in ("location", "path") if key in raw]
        if len(path_keys) != 1:
            raise ValueError(f"secondary_files[{index}] requires exactly one location or path")
        location = raw[path_keys[0]]
        if (
            type(location) is not str
            or not location
            or len(location.encode("utf-8")) > _MAX_LOCATION_BYTES
            or "\x00" in location
        ):
            raise ValueError(f"secondary_files[{index}] has an invalid location")
        basename = raw.get("basename")
        if basename is not None and (
            type(basename) is not str
            or basename in ("", ".", "..")
            or Path(basename).name != basename
            or "\x00" in basename
            or len(basename.encode("utf-8")) > 255
        ):
            raise ValueError(f"secondary_files[{index}] has an unsafe basename")
        secondary_format = _format_uri(raw.get("format"), field=f"secondary_files[{index}].format")
        normalized: dict[str, object] = {
            "class": "File",
            path_keys[0]: location,
        }
        if basename is not None:
            normalized["basename"] = basename
        if secondary_format is not None:
            normalized["format"] = secondary_format
        selected.append(normalized)
    return tuple(selected)


def _local_or_download_location(value: str) -> str:
    if not value.startswith("file://"):
        return value
    parsed = urlsplit(value)
    if parsed.netloc not in ("", "localhost"):
        raise ValueError("secondary File location must be local or use a supported download URL")
    return unquote(parsed.path)


class CwlFileInputNode(CopyInputNode):
    """Stage a file and explicitly declare standard CWL File metadata."""

    NODE_ID = "cwl_file_input"
    DISPLAY_NAME = "CWL File Input"
    CATEGORY = "input"
    DESCRIPTION = (
        "Stage a file and declare optional CWL format URI and secondary File metadata. "
        "The format is a user assertion checked for compatibility by cwltool; it does not prove file contents."
    )
    SEARCH_ALIASES = ["CWL File", "format URI", "secondaryFiles", "formatted file input"]
    RETURN_TYPES = ("FILE",)
    RETURN_NAMES = ("file",)
    REQUIRES_EXTERNAL_TOOLS = False
    DOCUMENTATION_URL = "https://www.commonwl.org/v1.2/CommandLineTool.html#File"
    GIT_COMMIT = None
    SOURCE_URL = ""
    UPSTREAM_SOURCE = "bionodulo/nodes/builtin/input_family/cwl_file.py:CwlFileInputNode"
    SOURCE_AUTHORITIES = {
        "cwl_file_standard": DOCUMENTATION_URL,
        "python_copy_runtime": CopyInputNode.SOURCE_AUTHORITIES["python_copy_runtime"],
        "python_url_runtime": CopyInputNode.SOURCE_AUTHORITIES["python_url_runtime"],
    }
    AUDIT_STATUS = "standards-bridge-format-is-user-declaration"
    SOURCE_KEYS = ("file",)
    OUTPUT_KEYS = ("file",)
    MISSING_INPUT_MESSAGE = "No file provided"
    EXPECTED_KIND = "file"
    VERSION = "1.0.0"

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "file": (
                    "FILE",
                    {
                        "description": (
                            "Local path or supported URL. The file is copied into the run before a CWL File object "
                            "is emitted."
                        )
                    },
                ),
            },
            "optional": {
                "format_uri": (
                    "STRING",
                    {
                        "description": (
                            "Credential-free absolute CWL format URI, for example "
                            "http://edamontology.org/format_1929. This declares compatibility; it does not inspect "
                            "or validate the file's scientific format."
                        )
                    },
                ),
                "secondary_files": (
                    "JSON",
                    {
                        "multiline": True,
                        "description": (
                            "Optional JSON array of CWL File objects with class and exactly one location or path; "
                            "basename and format are supported. Every file is copied into the run."
                        ),
                    },
                ),
                "source": (
                    "STRING",
                    {
                        "default": "auto",
                        "options": ["auto", "local", "url"],
                        "description": "How to interpret the primary file: auto, local path, or URL.",
                    },
                ),
            },
            "hidden": {},
        }

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        validation = super().VALIDATE_INPUTS(inputs)
        if validation is not True:
            return validation
        try:
            _format_uri(inputs.get("format_uri"), field="format_uri")
            _secondary_objects(inputs.get("secondary_files"))
        except (TypeError, ValueError) as error:
            return str(error)
        return True

    async def run(self, **kwargs: Any) -> dict[str, Any]:
        validation = self.__class__.VALIDATE_INPUTS(kwargs)
        if validation is not True:
            raise ValueError(str(validation))
        result = await super().run(**kwargs)
        primary_path = Path(result["outputs"]["file"])
        context = kwargs.get("context")
        secondary_values = _secondary_objects(kwargs.get("secondary_files"))
        prepared: list[tuple[Path, str, str | None]] = []
        names = {primary_path.name.casefold()}
        for index, item in enumerate(secondary_values):
            raw_location = str(item.get("location", item.get("path")))
            source = self.__class__._resolve_source(
                _local_or_download_location(raw_location),
                context,
                "auto",
            )
            self.__class__._validate_resolved_source(source)
            basename = str(item.get("basename", source.name))
            folded = basename.casefold()
            if folded in names:
                raise ValueError(f"secondary_files[{index}] collides with another staged basename: {basename}")
            names.add(folded)
            prepared.append((source, basename, item.get("format") if isinstance(item.get("format"), str) else None))

        secondary_files: list[dict[str, object]] = []
        for source, basename, secondary_format in prepared:
            staged = self.__class__._stage_resolved_source(
                source,
                primary_path.parent,
                destination_name=basename,
            )
            staged_object: dict[str, object] = {
                "class": "File",
                "location": str(staged),
                "basename": basename,
            }
            if secondary_format is not None:
                staged_object["format"] = secondary_format
            secondary_files.append(staged_object)

        cwl_file: dict[str, object] = {
            "class": "File",
            "location": str(primary_path.resolve()),
            "basename": primary_path.name,
        }
        declared_format = _format_uri(kwargs.get("format_uri"), field="format_uri")
        if declared_format is not None:
            cwl_file["format"] = declared_format
        if secondary_files:
            cwl_file["secondaryFiles"] = secondary_files

        if context is not None:
            run_metadata = getattr(context, "run_metadata", None)
            if isinstance(run_metadata, dict):
                records = run_metadata.setdefault("cwl_file_inputs", {})
                if isinstance(records, dict):
                    records[str(getattr(context, "node_id", self.NODE_ID))] = {
                        "format_uri": declared_format,
                        "format_semantics": "user_declaration_not_content_validation",
                        "secondary_file_count": len(secondary_files),
                    }
        return {"outputs": {"file": cwl_file}}


__all__ = ["CwlFileInputNode"]
