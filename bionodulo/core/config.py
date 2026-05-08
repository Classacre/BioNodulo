from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass(slots=True)
class Settings:
    project_root: Path
    runs_dir: Path
    cache_dir: Path
    custom_nodes_dir: Path
    data_roots: list[Path]
    tool_paths: dict[str, str]
    registries: list[str]
    api_secrets: dict[str, str]
    execution: dict[str, Any]
    mock_tools_default: bool = True

    @classmethod
    def from_env(cls, config_path: str | Path | None = None) -> "Settings":
        config = load_config(config_path or os.environ.get("BIONODULO_CONFIG"))
        root = Path(os.environ.get("BIONODULO_ROOT", config.get("project_root", Path.cwd()))).resolve()
        mock_env = os.environ.get("BIONODULO_MOCK_TOOLS", "1").lower()
        runs_dir = Path(os.environ.get("BIONODULO_RUNS_DIR", config.get("runs_dir", root / "runs"))).resolve()
        cache_dir = Path(os.environ.get("BIONODULO_CACHE_DIR", config.get("cache_dir", root / ".bionodulo_cache"))).resolve()
        custom_nodes_dir = Path(os.environ.get("BIONODULO_CUSTOM_NODES_DIR", config.get("custom_nodes_dir", root / "custom_nodes"))).resolve()
        data_roots = [Path(item).expanduser().resolve() for item in _list(config.get("data_roots", []))]
        tool_paths = {str(key): str(value) for key, value in dict(config.get("tool_paths", {})).items()}
        registries = [str(item) for item in _list(config.get("registries", []))]
        api_secrets = _load_api_secrets(dict(config.get("api_secrets", {})))
        execution = dict(config.get("execution", {}))
        return cls(
            project_root=root,
            runs_dir=runs_dir,
            cache_dir=cache_dir,
            custom_nodes_dir=custom_nodes_dir,
            data_roots=data_roots,
            tool_paths=tool_paths,
            registries=registries,
            api_secrets=api_secrets,
            execution=execution,
            mock_tools_default=mock_env not in {"0", "false", "no"},
        )

    def ensure_directories(self) -> None:
        self.runs_dir.mkdir(parents=True, exist_ok=True)
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.custom_nodes_dir.mkdir(parents=True, exist_ok=True)

    def as_effective_config(self) -> dict[str, Any]:
        return {
            "project_root": str(self.project_root),
            "runs_dir": str(self.runs_dir),
            "cache_dir": str(self.cache_dir),
            "custom_nodes_dir": str(self.custom_nodes_dir),
            "data_roots": [str(path) for path in self.data_roots],
            "tool_paths": dict(self.tool_paths),
            "registries": list(self.registries),
            "api_secrets": sorted(self.api_secrets),
            "execution": dict(self.execution),
            "mock_tools_default": self.mock_tools_default,
        }


def load_config(path: str | Path | None) -> dict[str, Any]:
    if not path:
        default = Path("bionodulo.yaml")
        if not default.exists():
            return {}
        path = default
    config_path = Path(path).expanduser()
    if not config_path.exists():
        return {}
    text = config_path.read_text(encoding="utf-8")
    if config_path.suffix.lower() == ".json":
        return json.loads(text)
    try:
        import yaml  # type: ignore

        value = yaml.safe_load(text) or {}
        return value if isinstance(value, dict) else {}
    except Exception:
        return _parse_simple_yaml(text)


def _parse_simple_yaml(text: str) -> dict[str, Any]:
    result: dict[str, Any] = {}
    current_key: str | None = None
    for raw_line in text.splitlines():
        line = raw_line.split("#", 1)[0].rstrip()
        if not line.strip():
            continue
        if not raw_line.startswith((" ", "\t")) and ":" in line:
            key, value = line.split(":", 1)
            key = key.strip()
            value = value.strip()
            current_key = key
            result[key] = _coerce(value) if value else {}
            continue
        if current_key and line.lstrip().startswith("-"):
            if not isinstance(result.get(current_key), list):
                result[current_key] = []
            result[current_key].append(_coerce(line.lstrip()[1:].strip()))
        elif current_key and ":" in line:
            if not isinstance(result.get(current_key), dict):
                result[current_key] = {}
            key, value = line.strip().split(":", 1)
            result[current_key][key.strip()] = _coerce(value.strip())
    return result


def _coerce(value: str) -> Any:
    if value in {"true", "True"}:
        return True
    if value in {"false", "False"}:
        return False
    if value.startswith("[") and value.endswith("]"):
        return [item.strip().strip("'\"") for item in value[1:-1].split(",") if item.strip()]
    return value.strip("'\"")


def _list(value: Any) -> list[Any]:
    if value is None:
        return []
    if isinstance(value, list):
        return value
    return [value]


def _load_api_secrets(configured: dict[str, str]) -> dict[str, str]:
    secrets = {str(key): str(value) for key, value in configured.items()}
    prefix = "BIONODULO_SECRET_"
    for key, value in os.environ.items():
        if key.startswith(prefix):
            secrets[key.removeprefix(prefix).lower()] = value
    return secrets
