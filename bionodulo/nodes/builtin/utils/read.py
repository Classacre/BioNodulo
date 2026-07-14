"""read — utils node(s). One tool per file (extracted from utility_file_format.py)."""
from __future__ import annotations
import csv
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
from typing import Any
from bionodulo.nodes.base import BaseNode
def _node_output_dir(node: BaseNode, context: Any) -> Path:
    base = Path(getattr(context, 'node_dir', '.') if context else '.')
    out_dir = base / node.NODE_ID
    out_dir.mkdir(parents=True, exist_ok=True)
    return out_dir
def _safe_filename_stem(value: str) -> str:
    stem = Path(value).stem.strip()
    safe = ''.join((char if char.isalnum() or char in {'-', '_', '.'} else '_' for char in stem))
    return safe.strip('._') or 'output'
def _read_text_or_literal(value: Any, *, label: str) -> str:
    text = str(value or '')
    if not text:
        raise ValueError(f'{label} is required')
    path = Path(text)
    if path.exists():
        if not path.is_file():
            raise ValueError(f'{label} path is not a file: {text}')
        return path.read_text(encoding='utf-8')
    return text
def _parse_scalar(value: str) -> Any:
    stripped = value.strip()
    lowered = stripped.lower()
    if lowered in {'true', 'yes', 'on'}:
        return True
    if lowered in {'false', 'no', 'off'}:
        return False
    if lowered in {'null', 'none', '~'}:
        return None
    if stripped.startswith('"') and stripped.endswith('"') or (stripped.startswith("'") and stripped.endswith("'")):
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
    if stripped[0] in {'[', '{'} or '\n' in stripped:
        try:
            return _load_yaml(stripped)
        except ValueError:
            pass
    return _parse_scalar(value)
def _get_path(data: Any, key_path: str) -> Any:
    current = data
    for key in key_path.split('.'):
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
        raise ValueError('set operation requires a JSON/YAML object or list')
    keys = key_path.split('.')
    current = data
    for index, key in enumerate(keys[:-1]):
        next_key = keys[index + 1]
        if isinstance(current, dict):
            if key not in current or not isinstance(current[key], (dict, list)):
                current[key] = [] if next_key.isdigit() else {}
            current = current[key]
        elif isinstance(current, list):
            if not key.isdigit():
                raise ValueError(f'List path segment must be an integer: {key}')
            list_index = int(key)
            while len(current) <= list_index:
                current.append({} if not next_key.isdigit() else [])
            current = current[list_index]
        else:
            raise ValueError(f'Cannot set nested key under scalar path segment: {key}')
    last_key = keys[-1]
    if isinstance(current, dict):
        current[last_key] = value
    elif isinstance(current, list):
        if not last_key.isdigit():
            raise ValueError(f'List path segment must be an integer: {last_key}')
        list_index = int(last_key)
        while len(current) <= list_index:
            current.append(None)
        current[list_index] = value
    else:
        raise ValueError(f'Cannot set key on scalar path segment: {last_key}')
    return data
def _delete_path(data: Any, key_path: str) -> None:
    keys = key_path.split('.')
    parent = _get_path(data, '.'.join(keys[:-1])) if len(keys) > 1 else data
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
def _value_to_string(value: Any, *, as_yaml: bool=False) -> str:
    if isinstance(value, (dict, list)):
        if as_yaml:
            return _dump_yaml(value)
        return json.dumps(value, sort_keys=True)
    return str(value)
def _load_yaml(text: str) -> Any:
    try:
        import yaml
    except ImportError:
        return _load_simple_yaml(text)
    try:
        return yaml.safe_load(text)
    except Exception as exc:
        raise ValueError(f'Invalid YAML: {exc}') from exc
def _dump_yaml(data: Any) -> str:
    try:
        import yaml
    except ImportError:
        return _dump_simple_yaml(data)
    return str(yaml.safe_dump(data, sort_keys=False, default_flow_style=False))
def _load_simple_yaml(text: str) -> Any:
    lines = [line.rstrip() for line in text.splitlines() if line.strip() and (not line.lstrip().startswith('#'))]
    if not lines:
        return {}
    if all((line.startswith('- ') for line in lines)):
        return [_parse_scalar(line[2:]) for line in lines]
    result: dict[str, Any] = {}
    for line in lines:
        if line.startswith((' ', '\t')):
            raise ValueError('Invalid YAML: nested YAML requires PyYAML')
        if ':' not in line:
            raise ValueError(f'Invalid YAML line: {line}')
        key, value = line.split(':', 1)
        key = key.strip()
        if not key:
            raise ValueError(f'Invalid YAML line: {line}')
        result[key] = _parse_scalar(value)
    return result
def _dump_simple_yaml(data: Any) -> str:
    if isinstance(data, dict):
        return ''.join((f'{key}: {_format_yaml_scalar(value)}\n' for key, value in data.items()))
    if isinstance(data, list):
        return ''.join((f'- {_format_yaml_scalar(value)}\n' for value in data))
    return f'{_format_yaml_scalar(data)}\n'
def _format_yaml_scalar(value: Any) -> str:
    if value is True:
        return 'true'
    if value is False:
        return 'false'
    if value is None:
        return 'null'
    if isinstance(value, (dict, list)):
        raise ValueError('YAML fallback only supports flat mappings and lists')
    return str(value)
def _bool_input(value: Any, *, default: bool) -> bool:
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    text = str(value).strip().lower()
    if not text:
        return default
    return text in {'1', 'true', 'yes', 'on'}
def _csv_delimiter(path: Path, delimiter: str) -> str:
    normalized = delimiter.strip().lower()
    if normalized in {'', 'auto'}:
        first_line = path.read_text(encoding='utf-8').splitlines()[0] if path.stat().st_size else ''
        if path.suffix.lower() == '.tsv' or '\t' in first_line:
            return '\t'
        return ','
    if normalized == 'csv':
        return ','
    if normalized == 'tsv':
        return '\t'
    if normalized == 'pipe':
        return '|'
    if normalized == 'semicolon':
        return ';'
    if delimiter == '\\t':
        return '\t'
    if len(delimiter) == 1:
        return delimiter
    raise ValueError(f'Unsupported delimiter: {delimiter}')
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
                raise ValueError(f'Cannot nest CSV column under scalar key: {key}')
            current = existing
        current[parts[-1]] = value
    return nested


class ReadFileNode(BaseNode):
    """Read a text file into workflow string outputs."""
    NODE_ID = 'read_file'
    DISPLAY_NAME = 'Read File'
    CATEGORY = 'utils'
    DESCRIPTION = 'Read a text file into content and line outputs with selectable encoding'
    SEARCH_ALIASES = ['read file', 'load text', 'file content', 'text file', 'open file']
    RETURN_TYPES = ('STRING', 'STRING', 'INT')
    RETURN_NAMES = ('content', 'lines', 'line_count')
    REQUIRES_EXTERNAL_TOOLS = False

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {'required': {'file_path': ('STRING', {'default': '', 'description': 'Text file path to read'})}, 'optional': {'encoding': ('STRING', {'default': 'utf-8', 'description': 'Text encoding'})}, 'hidden': {}}

    async def run(self, **kwargs: Any) -> tuple[str, str, int]:
        file_path = str(kwargs.get('file_path', '') or '')
        if not file_path:
            raise ValueError('file_path is required')
        encoding = str(kwargs.get('encoding', 'utf-8') or 'utf-8')
        path = Path(file_path)
        if not path.is_file():
            raise ValueError(f'file_path is not a file: {file_path}')
        content = path.read_text(encoding=encoding)
        split_lines = content.splitlines()
        display_lines = list(split_lines)
        while display_lines and display_lines[-1] == '':
            display_lines.pop()
        lines = '\n'.join(display_lines)
        if lines:
            lines += '\n'
        return (content, lines, len(split_lines))
