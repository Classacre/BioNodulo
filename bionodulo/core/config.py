"""Settings dataclass with YAML/JSON config loading for BioNodulo.

Supports environment variable overrides with BIONODULO_ prefix,
per-user JSON settings, and directory management.
"""

from __future__ import annotations

import json
import os
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

import yaml

_DEFAULT_REGISTRIES: dict[str, str] = {
    "bioconda": "https://api.anaconda.org/packages/bioconda/",
    "galaxy_toolshed": "https://toolshed.g2.bx.psu.edu/api/",
    "biocontainers": "https://api.biocontainers.pro/ga4gh/trs/v2/",
}


@dataclass
class ExecutionSettings:
    """Execution-specific configuration."""

    max_workers: int = 4
    cache_enabled: bool = True
    cache_ttl_seconds: int = 86400
    env_isolation: str = "auto"
    timeout_seconds: int = 3600


@dataclass
class Settings:
    """BioNodulo core settings loaded from config file and environment."""

    project_root: Path = field(default_factory=lambda: Path.cwd())
    runs_dir: Path = field(default_factory=lambda: Path("runs"))
    cache_dir: Path = field(default_factory=lambda: Path("cache"))
    custom_nodes_dir: Path = field(default_factory=lambda: Path("custom_nodes"))
    env_root: Path = field(default_factory=lambda: Path("environments"))
    data_roots: list[Path] = field(default_factory=list)
    tool_paths: dict[str, str] = field(default_factory=dict)
    registries: dict[str, str] = field(default_factory=lambda: dict(_DEFAULT_REGISTRIES))
    api_secrets: dict[str, str] = field(default_factory=dict)
    execution: ExecutionSettings = field(default_factory=ExecutionSettings)
    env_isolation_default: bool = True
    settings_file: Path = field(default_factory=lambda: Path("bionodulo.settings.json"))

    def __post_init__(self) -> None:
        self.project_root = Path(self.project_root)
        self.runs_dir = Path(self.runs_dir)
        self.cache_dir = Path(self.cache_dir)
        self.custom_nodes_dir = Path(self.custom_nodes_dir)
        self.data_roots = [Path(p) for p in self.data_roots]
        self.settings_file = Path(self.settings_file)

        if not self.runs_dir.is_absolute():
            self.runs_dir = self.project_root / self.runs_dir
        if not self.cache_dir.is_absolute():
            self.cache_dir = self.project_root / self.cache_dir
        if not self.custom_nodes_dir.is_absolute():
            self.custom_nodes_dir = self.project_root / self.custom_nodes_dir
        if not self.env_root.is_absolute():
            self.env_root = self.project_root / self.env_root
        if not self.settings_file.is_absolute():
            self.settings_file = self.project_root / self.settings_file
        self.data_roots = [
            p if p.is_absolute() else self.project_root / p
            for p in self.data_roots
        ]

    @classmethod
    def from_env(cls) -> Settings:
        project_root = Path(os.environ.get("BIONODULO_ROOT", Path.cwd())).resolve()

        config_file = os.environ.get("BIONODULO_CONFIG")
        if config_file:
            config_path = Path(config_file)
        else:
            config_path = project_root / "bionodulo.yaml"
            if not config_path.exists():
                config_path = project_root / "bionodulo.yml"
            if not config_path.exists():
                config_path = project_root / "bionodulo.json"

        config_data: dict[str, Any] = {}
        if config_path.exists():
            config_data = load_config(config_path)

        env_overrides = _collect_env_overrides()
        config_data.update(env_overrides)

        if "project_root" in config_data:
            project_root = Path(config_data["project_root"]).resolve()

        exec_data = config_data.pop("execution", {})
        execution = ExecutionSettings(**exec_data)

        data_roots_raw = config_data.pop("data_roots", [])
        data_roots = [Path(p) for p in data_roots_raw] if data_roots_raw else []

        runs_dir = Path(config_data.pop("runs_dir", "runs"))
        cache_dir = Path(config_data.pop("cache_dir", "cache"))
        custom_nodes_dir = Path(config_data.pop("custom_nodes_dir", "custom_nodes"))
        env_root = Path(config_data.pop("env_root", "environments"))
        settings_file = Path(
            config_data.pop("settings_file", str(project_root / "bionodulo.settings.json"))
        )
        tool_paths = config_data.pop("tool_paths", {})
        registries = config_data.pop("registries", dict(_DEFAULT_REGISTRIES))
        api_secrets = config_data.pop("api_secrets", {})
        env_isolation_default = config_data.pop(
            "env_isolation_default",
            os.environ.get("BIONODULO_ENV_ISOLATION", "1").lower() not in ("0", "false", "no"),
        )

        return cls(
            project_root=project_root,
            runs_dir=runs_dir,
            cache_dir=cache_dir,
            custom_nodes_dir=custom_nodes_dir,
            env_root=env_root,
            data_roots=data_roots,
            tool_paths=tool_paths,
            registries=registries,
            api_secrets=api_secrets,
            execution=execution,
            env_isolation_default=env_isolation_default,
            settings_file=settings_file,
        )

    def ensure_directories(self) -> None:
        self.project_root.mkdir(parents=True, exist_ok=True)
        self.runs_dir.mkdir(parents=True, exist_ok=True)
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.custom_nodes_dir.mkdir(parents=True, exist_ok=True)
        self.env_root.mkdir(parents=True, exist_ok=True)
        for dr in self.data_roots:
            dr.mkdir(parents=True, exist_ok=True)

    def as_effective_config(self) -> dict[str, Any]:
        def _convert(obj: Any) -> Any:
            if isinstance(obj, Path):
                return str(obj)
            if isinstance(obj, dict):
                return {k: _convert(v) for k, v in obj.items()}
            if isinstance(obj, list):
                return [_convert(i) for i in obj]
            return obj

        result = _convert(asdict(self))
        if "api_secrets" in result:
            result["api_secrets"] = {k: "***" for k in result["api_secrets"]}
        return result


def load_config(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    content = path.read_text(encoding="utf-8")
    suffix = path.suffix.lower()
    if suffix in (".yaml", ".yml"):
        return yaml.safe_load(content) or {}
    if suffix == ".json":
        return json.loads(content) or {}
    try:
        return yaml.safe_load(content) or {}
    except yaml.YAMLError:
        return json.loads(content) or {}


def _collect_env_overrides() -> dict[str, Any]:
    overrides: dict[str, Any] = {}
    prefix = "BIONODULO_"
    for key, value in os.environ.items():
        if key.startswith(prefix) and key != "BIONODULO_CONFIG":
            stripped = key[len(prefix):].lower()
            parts = stripped.split("__")
            target = overrides
            for part in parts[:-1]:
                target.setdefault(part, {})
                target = target[part]
            target[parts[-1]] = _parse_env_value(value)
    return overrides


def _parse_env_value(value: str) -> Any:
    lower = value.lower()
    if lower in ("true", "yes", "1"):
        return True
    if lower in ("false", "no", "0"):
        return False
    try:
        return int(value)
    except ValueError:
        pass
    try:
        return float(value)
    except ValueError:
        pass
    if value.startswith("[") or value.startswith("{"):
        try:
            return json.loads(value)
        except json.JSONDecodeError:
            pass
    return value


class SettingsManager:
    """Per-user JSON settings file manager."""

    def __init__(self, settings_file: Path) -> None:
        self._settings_file = settings_file
        self._defaults: dict[str, Any] = {
            "theme": "dark",
            "locale": "en",
            "auto_save": True,
            "auto_save_interval": 30,
            "show_preview": True,
            "snap_to_grid": True,
            "grid_size": 20,
            "confirm_delete": True,
            "default_workflow_directory": "",
            "file_browser_sort": "name",
            "node_library_sort": "category",
            "console_log_level": "info",
            "max_concurrent_runs": 4,
            "default_env_isolation": True,
            "cache_enabled": True,
            "bionodulo.theme": "system",
            "bionodulo.snapToGrid": False,
            "bionodulo.showMinimap": True,
            "bionodulo.linksHidden": False,
            "bionodulo.viewportLocked": False,
            "bionodulo.cacheEnabled": True,
            "bionodulo.llm.provider": "openai",
            "bionodulo.llm.model": "gpt-4.1-mini",
            "bionodulo.llm.baseUrl": "",
            "bionodulo.llm.apiKey": "",
            "bionodulo.llm.temperature": 0.2,
            "bionodulo.hpc.enabled": False,
            "bionodulo.hpc.backend": "slurm",
            "bionodulo.hpc.partition": "",
            "bionodulo.hpc.account": "",
            "bionodulo.hpc.modules": [],
            "bionodulo.hpc.container": "",
            "bionodulo.hpc.walltime": "01:00:00",
            "bionodulo.hpc.cpus_per_task": 4,
            "bionodulo.hpc.mem_per_cpu": "4G",
            "bionodulo.collab.enabled": False,
            "bionodulo.collab.presence": True,
            "bionodulo.getting_started.show_on_startup": True,
            "bionodulo.getting_started.dismissed": False,
            "editor_settings": {
                "font_size": 14,
                "line_numbers": True,
                "word_wrap": True,
                "tab_size": 4,
            },
        }
        self._settings: dict[str, Any] = {}
        self._load()

    def _load(self) -> None:
        if self._settings_file.exists():
            try:
                content = self._settings_file.read_text(encoding="utf-8")
                loaded = json.loads(content)
                if isinstance(loaded, dict):
                    self._settings = loaded
            except (json.JSONDecodeError, OSError):
                self._settings = dict(self._defaults)
        else:
            self._settings = dict(self._defaults)

    def _save(self) -> None:
        self._settings_file.parent.mkdir(parents=True, exist_ok=True)
        self._settings_file.write_text(
            json.dumps(self._settings, indent=2, sort_keys=True, ensure_ascii=False),
            encoding="utf-8",
        )

    def get(self, key: str, default: Any = None) -> Any:
        if "." in key:
            parts = key.split(".")
            target = self._settings
            for part in parts:
                if isinstance(target, dict) and part in target:
                    target = target[part]
                else:
                    return default
            return target
        return self._settings.get(key, default)

    def get_all(self) -> dict[str, Any]:
        merged = dict(self._defaults)
        merged.update(self._settings)
        return merged

    def set(self, key: str, value: Any) -> None:
        if "." in key:
            parts = key.split(".")
            target = self._settings
            for part in parts[:-1]:
                if part not in target or not isinstance(target[part], dict):
                    target[part] = {}
                target = target[part]
            target[parts[-1]] = value
        else:
            self._settings[key] = value
        self._save()

    def set_many(self, settings: dict[str, Any]) -> None:
        self._settings.update(settings)
        self._save()

    def reset(self, key: str) -> None:
        if key in self._settings:
            del self._settings[key]
        self._save()

    def reset_all(self) -> None:
        self._settings = dict(self._defaults)
        self._save()

    @property
    def settings_file(self) -> Path:
        return self._settings_file
