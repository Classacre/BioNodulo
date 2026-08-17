"""Shared contracts for focused file, path, JSON, and YAML utility nodes."""
from __future__ import annotations

import codecs
import csv
from datetime import datetime, timezone
import hashlib
import json
import math
from pathlib import Path
from typing import Any

from bionodulo.nodes.base import BaseNode


BIO_NODULO_BASELINE_COMMIT = "a32a426c03ce4c925bf7dcdbd2cf08fbdedd55e9"
CPYTHON_VERSION = "3.12.3"
CPYTHON_GIT_COMMIT = "f6650f9ad73359051f3e558c2431a109bc016664"
PYYAML_VERSION = "6.0.3"
PYYAML_GIT_COMMIT = "49790e73684bebad1df05ef8d828fa12f685bffb"
CPYTHON_CODECS_SOURCE_URL = f"https://github.com/python/cpython/blob/{CPYTHON_GIT_COMMIT}/Lib/codecs.py"
CPYTHON_CSV_SOURCE_URL = f"https://github.com/python/cpython/blob/{CPYTHON_GIT_COMMIT}/Lib/csv.py"
CPYTHON_JSON_SOURCE_URL = f"https://github.com/python/cpython/blob/{CPYTHON_GIT_COMMIT}/Lib/json/__init__.py"
CPYTHON_PATHLIB_SOURCE_URL = f"https://github.com/python/cpython/blob/{CPYTHON_GIT_COMMIT}/Lib/pathlib.py"
PYYAML_SOURCE_URL = f"https://github.com/yaml/pyyaml/tree/{PYYAML_GIT_COMMIT}"


class UtilityFileFormatNode(BaseNode):
    """Pinned Python and PyYAML semantics shared by file-format utilities."""

    CATEGORY = "utils/format"
    REQUIRES_EXTERNAL_TOOLS = False
    VERSION = "1.0.0"
    GIT_URL = "https://github.com/Classacre/BioNodulo.git"
    GIT_COMMIT = BIO_NODULO_BASELINE_COMMIT
    DOCUMENTATION_URL = (
        "https://github.com/Classacre/BioNodulo/blob/"
        f"{BIO_NODULO_BASELINE_COMMIT}/bionodulo/nodes/builtin/utility_file_format.py"
    )
    SOURCE_URL = DOCUMENTATION_URL
    UPSTREAM_SOURCE = "bionodulo/nodes/builtin/utility_file_format.py"
    RUNTIME_VERSION = CPYTHON_VERSION
    RUNTIME_GIT_COMMIT = CPYTHON_GIT_COMMIT
    RUNTIME_SOURCE_URLS = (
        CPYTHON_CODECS_SOURCE_URL,
        CPYTHON_CSV_SOURCE_URL,
        CPYTHON_JSON_SOURCE_URL,
        CPYTHON_PATHLIB_SOURCE_URL,
    )
    YAML_RUNTIME_VERSION = PYYAML_VERSION
    YAML_RUNTIME_GIT_COMMIT = PYYAML_GIT_COMMIT
    YAML_RUNTIME_SOURCE_URL = PYYAML_SOURCE_URL
    YAML_PACKAGE_CONSTRAINT = f"pyyaml=={PYYAML_VERSION}"
    EXIT_SEMANTICS = "Missing paths, invalid encodings or formats, and malformed structured data raise before success."

    @classmethod
    def _validate_inputs(
        cls,
        inputs: dict[str, Any],
        *,
        skip_choices: frozenset[str] = frozenset(),
        allow_missing_required: bool = False,
    ) -> bool | str:
        for section in ("required", "optional"):
            for name, spec in cls.INPUT_TYPES().get(section, {}).items():
                config = spec[1] if len(spec) > 1 and isinstance(spec[1], dict) else {}
                if name not in inputs or inputs[name] is None:
                    if section == "required" and "default" not in config and not allow_missing_required:
                        return f"Required input '{name}' is missing"
                    continue

                value = inputs[name]
                type_spec = spec[0]
                if isinstance(type_spec, list):
                    if name not in skip_choices and str(value) not in type_spec:
                        return f"Input '{name}' must be one of: {', '.join(type_spec)}"
                elif type_spec == "STRING" and not isinstance(value, str):
                    return f"Input '{name}' must be a string"
                elif type_spec == "BOOLEAN" and not isinstance(value, bool):
                    return f"Input '{name}' must be a boolean"
                elif type_spec == "INT":
                    if isinstance(value, bool):
                        return f"Input '{name}' must be an integer"
                    try:
                        value = int(value)
                    except (TypeError, ValueError):
                        return f"Input '{name}' must be an integer"
                    if isinstance(inputs[name], float) and not inputs[name].is_integer():
                        return f"Input '{name}' must be an integer"
                elif type_spec == "FLOAT":
                    if isinstance(value, bool):
                        return f"Input '{name}' must be a number"
                    try:
                        value = float(value)
                    except (TypeError, ValueError):
                        return f"Input '{name}' must be a number"
                    if not math.isfinite(value):
                        return f"Input '{name}' must be finite"
                elif type_spec == "FILE" and not str(value).strip():
                    return f"Input '{name}' must be a non-empty path"

                choices = config.get("options")
                if choices and name not in skip_choices and str(value) not in choices:
                    return f"Input '{name}' must be one of: {', '.join(str(choice) for choice in choices)}"
                if isinstance(value, (int, float)) and not isinstance(value, bool):
                    if "min" in config and value < config["min"]:
                        return f"Input '{name}' must be at least {config['min']}"
                    if "max" in config and value > config["max"]:
                        return f"Input '{name}' must be at most {config['max']}"
        return True

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        return cls._validate_inputs(inputs)

    @classmethod
    def require_valid_inputs(
        cls,
        inputs: dict[str, Any],
        *,
        skip_choices: frozenset[str] = frozenset(),
    ) -> None:
        validation = cls._validate_inputs(
            inputs,
            skip_choices=skip_choices,
            allow_missing_required=True,
        )
        if validation is not True:
            raise ValueError(str(validation))


def _safe_filename_stem(value: str) -> str:
    stem = Path(value).stem.strip()
    safe = "".join(char if char.isalnum() or char in {"-", "_", "."} else "_" for char in stem)
    return safe.strip("._") or "output"


def _validate_encoding(value: Any) -> str:
    encoding = str(value or "utf-8")
    try:
        codecs.lookup(encoding)
    except LookupError as exc:
        raise ValueError(f"Unknown text encoding: {encoding}") from exc
    return encoding


def _read_text_or_literal(value: Any, *, label: str) -> str:
    text = str(value or "")
    if not text:
        raise ValueError(f"{label} is required")
    path = Path(text)
    if path.exists():
        if not path.is_file():
            raise ValueError(f"{label} path is not a file: {text}")
        return path.read_text(encoding="utf-8")
    return text


def _parse_scalar(value: str) -> Any:
    stripped = value.strip()
    lowered = stripped.lower()
    if lowered in {"true", "yes", "on"}:
        return True
    if lowered in {"false", "no", "off"}:
        return False
    if lowered in {"null", "none", "~"}:
        return None
    if (stripped.startswith('"') and stripped.endswith('"')) or (stripped.startswith("'") and stripped.endswith("'")):
        return stripped[1:-1]
    try:
        return int(stripped)
    except ValueError:
        pass
    try:
        return float(stripped)
    except ValueError:
        return stripped


def _parse_structured_or_scalar(value: str) -> Any:
    stripped = value.strip()
    if not stripped:
        return _parse_scalar(value)

    try:
        return json.loads(stripped)
    except json.JSONDecodeError:
        pass

    if stripped[0] in {"[", "{"} or "\n" in stripped:
        try:
            return _load_yaml(stripped)
        except ValueError:
            pass

    return _parse_scalar(value)


def _get_path(data: Any, key_path: str) -> Any:
    current = data
    for key in key_path.split("."):
        if isinstance(current, dict):
            if key not in current:
                raise KeyError(key_path)
            current = current[key]
        elif isinstance(current, list):
            try:
                current = current[int(key)]
            except (ValueError, IndexError) as exc:
                raise KeyError(key_path) from exc
        else:
            raise KeyError(key_path)
    return current


def _set_path(data: Any, key_path: str, value: Any) -> Any:
    if not isinstance(data, (dict, list)):
        raise ValueError("set operation requires a JSON/YAML object or list")
    keys = key_path.split(".")
    current = data
    for index, key in enumerate(keys[:-1]):
        next_key = keys[index + 1]
        if isinstance(current, dict):
            if key not in current or not isinstance(current[key], (dict, list)):
                current[key] = [] if next_key.isdigit() else {}
            current = current[key]
        elif isinstance(current, list):
            if not key.isdigit():
                raise ValueError(f"List path segment must be an integer: {key}")
            list_index = int(key)
            while len(current) <= list_index:
                current.append({} if not next_key.isdigit() else [])
            current = current[list_index]
        else:
            raise ValueError(f"Cannot set nested key under scalar path segment: {key}")

    last_key = keys[-1]
    if isinstance(current, dict):
        current[last_key] = value
    elif isinstance(current, list):
        if not last_key.isdigit():
            raise ValueError(f"List path segment must be an integer: {last_key}")
        list_index = int(last_key)
        while len(current) <= list_index:
            current.append(None)
        current[list_index] = value
    else:
        raise ValueError(f"Cannot set key on scalar path segment: {last_key}")
    return data


def _delete_path(data: Any, key_path: str) -> None:
    keys = key_path.split(".")
    parent = _get_path(data, ".".join(keys[:-1])) if len(keys) > 1 else data
    last_key = keys[-1]
    if isinstance(parent, dict):
        if last_key not in parent:
            raise KeyError(key_path)
        del parent[last_key]
    elif isinstance(parent, list):
        try:
            del parent[int(last_key)]
        except (ValueError, IndexError) as exc:
            raise KeyError(key_path) from exc
    else:
        raise KeyError(key_path)


def _value_to_string(value: Any, *, as_yaml: bool = False) -> str:
    if isinstance(value, (dict, list)):
        if as_yaml:
            return _dump_yaml(value)
        return json.dumps(value, sort_keys=True)
    return str(value)


def _load_yaml(text: str) -> Any:
    try:
        import yaml  # type: ignore[import-untyped]
    except ImportError as exc:
        raise RuntimeError(f"YAML operations require PyYAML {PYYAML_VERSION}") from exc
    try:
        return yaml.safe_load(text)
    except Exception as exc:  # pragma: no cover - exact exception type depends on PyYAML.
        raise ValueError(f"Invalid YAML: {exc}") from exc


def _dump_yaml(data: Any) -> str:
    try:
        import yaml  # type: ignore[import-untyped]
    except ImportError as exc:
        raise RuntimeError(f"YAML operations require PyYAML {PYYAML_VERSION}") from exc
    return str(yaml.safe_dump(data, sort_keys=False, default_flow_style=False))


def _bool_input(value: Any, *, default: bool) -> bool:
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    text = str(value).strip().lower()
    if not text:
        return default
    return text in {"1", "true", "yes", "on"}


def _csv_delimiter(path: Path, delimiter: str) -> str:
    normalized = delimiter.strip().lower()
    if normalized in {"", "auto"}:
        first_line = path.read_text(encoding="utf-8").splitlines()[0] if path.stat().st_size else ""
        if path.suffix.lower() == ".tsv" or "\t" in first_line:
            return "\t"
        return ","
    if normalized == "csv":
        return ","
    if normalized == "tsv":
        return "\t"
    if normalized == "pipe":
        return "|"
    if normalized == "semicolon":
        return ";"
    if delimiter == r"\t":
        return "\t"
    if len(delimiter) == 1:
        return delimiter
    raise ValueError(f"Unsupported delimiter: {delimiter}")


def _nested_row(row: dict[str, str], separator: str) -> dict[str, Any]:
    if not separator:
        return dict(row)

    nested: dict[str, Any] = {}
    for key, value in row.items():
        parts = [part for part in key.split(separator) if part]
        if not parts:
            continue
        current = nested
        for part in parts[:-1]:
            existing = current.setdefault(part, {})
            if not isinstance(existing, dict):
                raise ValueError(f"Cannot nest CSV column under scalar key: {key}")
            current = existing
        current[parts[-1]] = value
    return nested


class _FileInfoContract(UtilityFileFormatNode):
    """Return filesystem metadata for a path."""

    LEGACY_NODE_ID = "file_info"
    DISPLAY_NAME = "File Info"
    CATEGORY = "utils"
    DESCRIPTION = "Get file metadata including path, name, extension, size, line count, checksum, and existence"
    SEARCH_ALIASES = ["file info", "metadata", "file size", "path", "stat", "exists", "checksum", "md5", "lines"]
    RETURN_TYPES = ("STRING", "INT", "FLOAT", "BOOLEAN")
    RETURN_NAMES = ("info_json", "size_bytes", "size_mb", "exists")
    REQUIRES_EXTERNAL_TOOLS = False

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "file": ("FILE", {"description": "File or directory path to inspect"}),
            },
            "optional": {
                "checksum_algo": (
                    ["md5", "sha1", "sha256"],
                    {"default": "md5", "description": "Hash algorithm for file checksum"},
                ),
            },
            "hidden": {},
        }

    async def run(self, **kwargs: Any) -> tuple[str, int, float, bool]:
        self.require_valid_inputs(kwargs, skip_choices=frozenset({"checksum_algo"}))
        file_value = str(kwargs.get("file", "") or "")
        if not file_value:
            raise ValueError("file is required")
        checksum_algo = str(kwargs.get("checksum_algo", "md5") or "md5").lower()
        if checksum_algo not in {"md5", "sha1", "sha256"}:
            raise ValueError(f"Unsupported checksum algorithm: {checksum_algo}")

        path = Path(file_value)
        exists = path.exists()
        is_file = path.is_file()
        is_dir = path.is_dir()
        stat = path.stat() if exists else None
        size_bytes = stat.st_size if stat else 0
        size_mb = size_bytes / (1024 * 1024)
        resolved = path.resolve() if exists else path.absolute()
        modified_time = (
            datetime.fromtimestamp(stat.st_mtime, tz=timezone.utc).isoformat()
            if stat is not None
            else ""
        )
        line_count = 0
        checksum = ""
        if is_file:
            with path.open("rb") as handle:
                line_count = sum(1 for _ in handle)
            hasher = hashlib.new(checksum_algo)
            with path.open("rb") as handle:
                for chunk in iter(lambda: handle.read(1024 * 1024), b""):
                    hasher.update(chunk)
            checksum = hasher.hexdigest()
        info = {
            "path": str(resolved),
            "name": path.name,
            "extension": path.suffix,
            "size_bytes": size_bytes,
            "size_mb": size_mb,
            "exists": exists,
            "is_file": is_file,
            "is_dir": is_dir,
            "line_count": line_count,
            "checksum_algo": checksum_algo,
            "checksum": checksum,
            "modified_time": modified_time,
        }
        return (json.dumps(info, sort_keys=True), size_bytes, size_mb, exists)


class _PathOperationsContract(UtilityFileFormatNode):
    """Perform common path manipulations."""

    LEGACY_NODE_ID = "path_operations"
    DISPLAY_NAME = "Path Operations"
    CATEGORY = "utils"
    DESCRIPTION = "Path manipulation: basename, dirname, extension, stem, join, exists, absolute, relative"
    SEARCH_ALIASES = ["path", "filepath", "basename", "dirname", "extension", "join", "absolute", "relative"]
    RETURN_TYPES = ("STRING", "BOOLEAN")
    RETURN_NAMES = ("result", "exists")
    REQUIRES_EXTERNAL_TOOLS = False

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "operation": (
                    [
                        "basename",
                        "dirname",
                        "extension",
                        "stem",
                        "join",
                        "exists",
                        "absolute",
                        "relative",
                        "is_file",
                        "is_dir",
                        "with_suffix",
                        "with_name",
                    ],
                    {"default": "basename", "description": "Path operation"},
                ),
                "path": ("STRING", {"default": "", "description": "File or directory path"}),
            },
            "optional": {
                "path_b": ("STRING", {"default": "", "description": "Second path component for join or base path for relative"}),
                "suffix": ("STRING", {"default": "", "description": "Replacement suffix for with_suffix"}),
                "name": ("STRING", {"default": "", "description": "Replacement filename for with_name"}),
            },
            "hidden": {},
        }

    async def run(self, **kwargs: Any) -> tuple[str, bool]:
        self.require_valid_inputs(kwargs, skip_choices=frozenset({"operation"}))
        operation = str(kwargs.get("operation", "basename") or "basename")
        path_text = str(kwargs.get("path", "") or "")
        if not path_text:
            raise ValueError("path is required")
        path = Path(path_text)

        if operation == "basename":
            result = path.name
            exists = path.exists()
        elif operation == "dirname":
            result = str(path.parent)
            exists = path.parent.exists()
        elif operation == "extension":
            result = path.suffix
            exists = path.exists()
        elif operation == "stem":
            result = path.stem
            exists = path.exists()
        elif operation == "join":
            path_b = str(kwargs.get("path_b", "") or "")
            if not path_b:
                raise ValueError("path_b is required for join operation")
            result = str(path / path_b)
            exists = Path(result).exists()
        elif operation == "relative":
            path_b = str(kwargs.get("path_b", "") or "")
            if not path_b:
                raise ValueError("path_b is required for relative operation")
            result = str(path.relative_to(Path(path_b)))
            exists = path.exists()
        elif operation == "exists":
            result = path_text
            exists = path.exists()
        elif operation == "is_file":
            result = path_text
            exists = path.is_file()
        elif operation == "is_dir":
            result = path_text
            exists = path.is_dir()
        elif operation == "absolute":
            result = str(path.resolve())
            exists = Path(result).exists()
        elif operation == "with_suffix":
            suffix = str(kwargs.get("suffix", "") or "")
            if not suffix:
                raise ValueError("suffix is required for with_suffix operation")
            result = str(path.with_suffix(suffix))
            exists = Path(result).exists()
        elif operation == "with_name":
            name = str(kwargs.get("name", "") or "")
            if not name:
                raise ValueError("name is required for with_name operation")
            result = str(path.with_name(Path(name).name))
            exists = Path(result).exists()
        else:
            raise ValueError(f"Unsupported path operation: {operation}")

        return (result, exists)


class _ReadFileContract(UtilityFileFormatNode):
    """Read a text file into workflow string outputs."""

    LEGACY_NODE_ID = "read_file"
    DISPLAY_NAME = "Read File"
    CATEGORY = "utils"
    DESCRIPTION = "Read a text file into content and line outputs with selectable encoding"
    SEARCH_ALIASES = ["read file", "load text", "file content", "text file", "open file"]
    RETURN_TYPES = ("STRING", "STRING", "INT")
    RETURN_NAMES = ("content", "lines", "line_count")
    REQUIRES_EXTERNAL_TOOLS = False

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "file_path": ("STRING", {"default": "", "description": "Text file path to read"}),
            },
            "optional": {
                "encoding": ("STRING", {"default": "utf-8", "description": "Text encoding"}),
            },
            "hidden": {},
        }

    async def run(self, **kwargs: Any) -> tuple[str, str, int]:
        self.require_valid_inputs(kwargs)
        file_path = str(kwargs.get("file_path", "") or "")
        if not file_path:
            raise ValueError("file_path is required")
        encoding = _validate_encoding(kwargs.get("encoding", "utf-8"))
        path = Path(file_path)
        if not path.is_file():
            raise ValueError(f"file_path is not a file: {file_path}")

        content = path.read_text(encoding=encoding)
        split_lines = content.splitlines()
        display_lines = list(split_lines)
        while display_lines and display_lines[-1] == "":
            display_lines.pop()
        lines = "\n".join(display_lines)
        if lines:
            lines += "\n"
        return (content, lines, len(split_lines))


class _WriteFileContract(UtilityFileFormatNode):
    """Write workflow string content to a file."""

    LEGACY_NODE_ID = "write_file"
    DISPLAY_NAME = "Write File"
    CATEGORY = "utils"
    DESCRIPTION = "Write text or formatted JSON content to a file with selectable encoding"
    SEARCH_ALIASES = ["write file", "save text", "file output", "write json", "export text"]
    RETURN_TYPES = ("STRING", "INT")
    RETURN_NAMES = ("file_path", "bytes_written")
    REQUIRES_EXTERNAL_TOOLS = False

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "content": ("STRING", {"default": "", "multiline": True, "description": "Content to write"}),
                "file_path": ("STRING", {"default": "", "description": "Destination file path"}),
            },
            "optional": {
                "format": ("STRING", {"default": "text", "options": ["text", "json"]}),
                "encoding": ("STRING", {"default": "utf-8", "description": "Text encoding"}),
            },
            "hidden": {},
        }

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        del output_dir
        file_path = str(inputs.get("file_path", "") or "")
        if not file_path:
            raise ValueError("file_path is required")
        return [Path(file_path)]

    async def run(self, **kwargs: Any) -> tuple[str, int]:
        self.require_valid_inputs(kwargs, skip_choices=frozenset({"format"}))
        file_path = str(kwargs.get("file_path", "") or "")
        if not file_path:
            raise ValueError("file_path is required")
        encoding = _validate_encoding(kwargs.get("encoding", "utf-8"))
        output_format = str(kwargs.get("format", "text") or "text").lower()
        content = str(kwargs.get("content", ""))

        if output_format == "text":
            output = content
        elif output_format == "json":
            try:
                output = json.dumps(json.loads(content), indent=2, sort_keys=True) + "\n"
            except json.JSONDecodeError as exc:
                raise ValueError(f"Invalid JSON content: {exc}") from exc
        else:
            raise ValueError(f"Unsupported write format: {output_format}")

        path = Path(file_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(output, encoding=encoding, newline="\n")
        return (str(path), len(output.encode(encoding)))


class _JSONOperationsContract(UtilityFileFormatNode):
    """Parse and manipulate JSON strings or JSON files."""

    LEGACY_NODE_ID = "json_operations"
    DISPLAY_NAME = "JSON Operations"
    CATEGORY = "utils/format"
    DESCRIPTION = "Parse and manipulate JSON: get, set, delete, keys, pretty, minify, validate"
    SEARCH_ALIASES = ["json", "parse json", "json field", "json extract", "json set", "json validate"]
    RETURN_TYPES = ("STRING", "STRING", "BOOLEAN")
    RETURN_NAMES = ("result_json", "value", "valid")
    REQUIRES_EXTERNAL_TOOLS = False

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "operation": (
                    ["get", "set", "delete", "keys", "pretty", "pretty_print", "minify", "validate", "parse", "stringify"],
                    {"default": "pretty", "description": "JSON operation"},
                ),
                "json_input": ("STRING", {"default": "{}", "multiline": True, "description": "JSON string or path to JSON file"}),
            },
            "optional": {
                "key": ("STRING", {"default": "", "description": "Dot-separated key path"}),
                "value": ("STRING", {"default": "", "description": "Value for set operation"}),
                "indent": ("INT", {"default": 2, "min": 0, "max": 8, "description": "Pretty-print indentation"}),
            },
            "hidden": {},
        }

    async def run(self, **kwargs: Any) -> tuple[str, str, bool]:
        self.require_valid_inputs(kwargs, skip_choices=frozenset({"operation"}))
        operation = str(kwargs.get("operation", "pretty") or "pretty")
        json_text = _read_text_or_literal(kwargs.get("json_input", "{}"), label="json_input")
        indent = int(kwargs.get("indent", 2))

        try:
            data = json.loads(json_text)
        except json.JSONDecodeError as exc:
            if operation == "validate":
                return ("", f"Invalid JSON: {exc}", False)
            raise ValueError(f"Invalid JSON: {exc}") from exc

        if operation == "validate":
            return (json_text, "", True)
        if operation in {"pretty", "parse", "pretty_print", "stringify"}:
            return (json.dumps(data, indent=indent), "", True)
        if operation == "minify":
            return (json.dumps(data, separators=(",", ":")), "", True)
        if operation == "keys":
            if not isinstance(data, dict):
                raise ValueError("keys operation requires a JSON object")
            return (json.dumps(data, sort_keys=True), "\n".join(str(key) for key in data), True)
        if operation == "get":
            key = str(kwargs.get("key", "") or "")
            if not key:
                raise ValueError("key is required for get operation")
            try:
                value = _get_path(data, key)
            except KeyError as exc:
                raise ValueError(f"JSON key not found: {key}") from exc
            return (json.dumps(data, sort_keys=True), _value_to_string(value), True)
        if operation == "set":
            key = str(kwargs.get("key", "") or "")
            if not key:
                raise ValueError("key is required for set operation")
            raw_value = str(kwargs.get("value", ""))
            try:
                parsed_value = json.loads(raw_value)
            except json.JSONDecodeError:
                parsed_value = raw_value
            return (json.dumps(_set_path(data, key, parsed_value), sort_keys=True), raw_value, True)
        if operation == "delete":
            key = str(kwargs.get("key", "") or "")
            if not key:
                raise ValueError("key is required for delete operation")
            try:
                _delete_path(data, key)
            except KeyError as exc:
                raise ValueError(f"JSON key not found: {key}") from exc
            return (json.dumps(data, sort_keys=True), "", True)

        raise ValueError(f"Unsupported JSON operation: {operation}")


class _YMLOperationsContract(UtilityFileFormatNode):
    """Parse and manipulate YAML strings or YAML files."""

    LEGACY_NODE_ID = "yaml_operations"
    DISPLAY_NAME = "YAML Operations"
    CATEGORY = "utils/format"
    DESCRIPTION = "Parse and manipulate YAML: get, set, keys, convert to JSON, validate"
    SEARCH_ALIASES = ["yaml", "yml", "parse yaml", "yaml field", "config", "yaml extract"]
    RETURN_TYPES = ("STRING", "STRING", "BOOLEAN")
    RETURN_NAMES = ("result_yaml", "value", "valid")
    REQUIRES_EXTERNAL_TOOLS = False

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "operation": (
                    ["get", "set", "keys", "to_json", "validate", "parse", "pretty", "pretty_print", "stringify"],
                    {"default": "parse", "description": "YAML operation"},
                ),
                "yaml_input": ("STRING", {"default": "", "multiline": True, "description": "YAML string or path to YAML file"}),
            },
            "optional": {
                "key": ("STRING", {"default": "", "description": "Dot-separated key path"}),
                "value": ("STRING", {"default": "", "description": "Value for set operation"}),
            },
            "hidden": {},
        }

    async def run(self, **kwargs: Any) -> tuple[str, str, bool]:
        self.require_valid_inputs(kwargs, skip_choices=frozenset({"operation"}))
        operation = str(kwargs.get("operation", "parse") or "parse")
        yaml_text = _read_text_or_literal(kwargs.get("yaml_input", ""), label="yaml_input")

        try:
            data = _load_yaml(yaml_text)
        except ValueError as exc:
            if operation == "validate":
                return ("", str(exc), False)
            raise
        except Exception as exc:
            if operation == "validate":
                return ("", f"Invalid YAML: {exc}", False)
            raise ValueError(f"Invalid YAML: {exc}") from exc

        if data is None:
            data = {}

        if operation == "validate":
            return (yaml_text, "", True)
        if operation in {"parse", "pretty", "pretty_print", "stringify"}:
            return (_dump_yaml(data), "", True)
        if operation == "to_json":
            return (json.dumps(data, sort_keys=True), "", True)
        if operation == "keys":
            if not isinstance(data, dict):
                raise ValueError("keys operation requires a YAML mapping")
            return (_dump_yaml(data), "\n".join(str(key) for key in data), True)
        if operation == "get":
            key = str(kwargs.get("key", "") or "")
            if not key:
                raise ValueError("key is required for get operation")
            try:
                value = _get_path(data, key)
            except KeyError as exc:
                raise ValueError(f"YAML key not found: {key}") from exc
            return (_dump_yaml(data), _value_to_string(value, as_yaml=True), True)
        if operation == "set":
            key = str(kwargs.get("key", "") or "")
            if not key:
                raise ValueError("key is required for set operation")
            raw_value = str(kwargs.get("value", ""))
            parsed_value = _parse_structured_or_scalar(raw_value)
            return (_dump_yaml(_set_path(data, key, parsed_value)), raw_value, True)

        raise ValueError(f"Unsupported YAML operation: {operation}")


class _CSVToJSONContract(UtilityFileFormatNode):
    """Convert a CSV or TSV file to JSON."""

    LEGACY_NODE_ID = "csv_to_json"
    DISPLAY_NAME = "CSV to JSON"
    CATEGORY = "utils/format"
    DESCRIPTION = "Convert delimited CSV or TSV tables to JSON arrays or keyed objects"
    SEARCH_ALIASES = ["csv", "tsv", "json", "csv to json", "table to json", "convert csv"]
    RETURN_TYPES = ("JSON", "STRING", "INT")
    RETURN_NAMES = ("json_file", "preview_json", "record_count")
    REQUIRES_EXTERNAL_TOOLS = False

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "csv_file": ("FILE", {"description": "CSV or TSV file with a header row"}),
            },
            "optional": {
                "delimiter": (
                    "STRING",
                    {"default": "auto", "options": ["auto", "csv", "tsv", "pipe", "semicolon"], "description": "Input delimiter"},
                ),
                "key_column": ("STRING", {"default": "", "description": "Optional column to key the JSON object by"}),
                "nest_separator": ("STRING", {"default": "", "description": "Column-name separator for nested JSON keys"}),
                "output_name": ("STRING", {"default": "", "description": "Optional output filename stem"}),
                "pretty": ("BOOLEAN", {"default": True, "description": "Write indented JSON"}),
            },
            "hidden": {},
        }

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        csv_file = str(inputs.get("csv_file", "") or "")
        if not csv_file:
            raise ValueError("csv_file is required")
        output_stem = str(inputs.get("output_name", "") or "").strip() or Path(csv_file).stem
        return [Path(output_dir) / cls.NODE_ID / f"{_safe_filename_stem(output_stem)}.json"]

    async def run(self, **kwargs: Any) -> tuple[str, str, int]:
        self.require_valid_inputs(kwargs, skip_choices=frozenset({"delimiter"}))
        csv_file = str(kwargs.get("csv_file", "") or "")
        if not csv_file:
            raise ValueError("csv_file is required")
        path = Path(csv_file)
        if not path.is_file():
            raise ValueError(f"csv_file path is not a file: {csv_file}")

        delimiter = _csv_delimiter(path, str(kwargs.get("delimiter", "auto") or "auto"))
        key_column = str(kwargs.get("key_column", "") or "").strip()
        nest_separator = str(kwargs.get("nest_separator", "") or "")
        pretty = _bool_input(kwargs.get("pretty", True), default=True)

        with path.open("r", encoding="utf-8", newline="") as handle:
            reader = csv.DictReader(handle, delimiter=delimiter)
            if not reader.fieldnames:
                raise ValueError("csv_file must include a header row")

            rows: list[dict[str, Any]] = []
            keyed_rows: dict[str, dict[str, Any]] = {}
            for raw_row in reader:
                if None in raw_row:
                    raise ValueError("CSV row contains more fields than the header")
                row = {str(column): "" if value is None else value for column, value in raw_row.items()}
                if key_column and key_column not in row:
                    raise ValueError(f"key_column not found in CSV header: {key_column}")
                converted = _nested_row(row, nest_separator)
                if key_column:
                    key_value = row[key_column]
                    if key_value in keyed_rows:
                        raise ValueError(f"Duplicate key_column value: {key_value}")
                    keyed_rows[key_value] = converted
                else:
                    rows.append(converted)

        data: list[dict[str, Any]] | dict[str, dict[str, Any]]
        preview: list[dict[str, Any]] | dict[str, dict[str, Any]]
        if key_column:
            data = keyed_rows
            first_item = next(iter(keyed_rows.items()), None)
            preview = {first_item[0]: first_item[1]} if first_item else {}
            record_count = len(keyed_rows)
        else:
            data = rows
            preview = rows[:1]
            record_count = len(rows)

        context = kwargs.get("context")
        output_root = Path(getattr(context, "node_dir", ".") if context else ".")
        output_path = self.PLAN_OUTPUTS(kwargs, output_root)[0]
        output_path.parent.mkdir(parents=True, exist_ok=True)
        json_kwargs: dict[str, Any] = {"indent": 2} if pretty else {"separators": (",", ":")}
        output_path.write_text(json.dumps(data, **json_kwargs) + "\n", encoding="utf-8")
        preview_json = json.dumps(preview, **json_kwargs)

        return (str(output_path), preview_json, record_count)
