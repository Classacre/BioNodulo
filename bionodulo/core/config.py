from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


@dataclass(slots=True)
class Settings:
    project_root: Path
    runs_dir: Path
    cache_dir: Path
    custom_nodes_dir: Path
    mock_tools_default: bool = True

    @classmethod
    def from_env(cls) -> "Settings":
        root = Path(os.environ.get("BIONODULO_ROOT", Path.cwd())).resolve()
        mock_env = os.environ.get("BIONODULO_MOCK_TOOLS", "1").lower()
        return cls(
            project_root=root,
            runs_dir=root / "runs",
            cache_dir=root / ".bionodulo_cache",
            custom_nodes_dir=root / "custom_nodes",
            mock_tools_default=mock_env not in {"0", "false", "no"},
        )

    def ensure_directories(self) -> None:
        self.runs_dir.mkdir(parents=True, exist_ok=True)
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.custom_nodes_dir.mkdir(parents=True, exist_ok=True)
