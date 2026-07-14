"""ibiosim — synthetic_biology node(s). One tool per file (extracted from synthetic_biology.py)."""
from __future__ import annotations
import re
import textwrap
from pathlib import Path
from typing import Any
from bionodulo.nodes.command_node import CommandNode
def _safe_output_stem(value: Any, fallback: str) -> str:
    text = str(value or '').strip()
    if not text:
        text = fallback
    stem = Path(text).stem
    stem = re.sub('\\.(gz|bz2|xz|zip)$', '', stem)
    stem = re.sub('[^A-Za-z0-9_.-]+', '_', stem).strip('._-')
    return stem or fallback


class iBioSimModelNode(CommandNode):
    """Execute iBioSim COMBINE/OMEX archives through the BioSimulators CLI."""
    NODE_ID = 'ibiosim_model'
    DISPLAY_NAME = 'iBioSim Model'
    CATEGORY = 'synthetic_biology'
    DESCRIPTION = 'Execute iBioSim COMBINE/OMEX archives containing SED-ML simulation experiments.'
    SEARCH_ALIASES = ['ibiosim', 'biosimulators', 'synthetic biology', 'biocad', 'combine archive', 'omex', 'sed-ml', 'sbml', 'model simulation']
    RETURN_TYPES = ('DIRECTORY', 'TSV', 'JSON', 'LOG')
    RETURN_NAMES = ('results_dir', 'result_index', 'metadata', 'log')
    REQUIRED_EXECUTABLES = ['ibiosim', 'python']
    REQUIRED_CONDA_PACKAGES: list[str] = []
    DOCUMENTATION_URL = 'https://docs.biosimulators.org/Biosimulators_iBioSim/'
    VERSION = '1.0'
    EXPERIMENTAL = True
    SHELL = True
    INDEX_SCRIPT = textwrap.dedent('        from __future__ import annotations\n        import csv\n        import json\n        import sys\n        from pathlib import Path\n\n        (\n            results_dir,\n            index_path,\n            metadata_path,\n            log_path,\n            archive_file,\n            execution_mode,\n            executable,\n            docker_image,\n            quiet,\n            debug,\n        ) = sys.argv[1:11]\n\n        root = Path(results_dir)\n        rows = []\n        if root.exists():\n            for path in sorted(root.rglob("*")):\n                if path.is_file():\n                    rows.append({\n                        "relative_path": str(path.relative_to(root)),\n                        "path": str(path),\n                        "size_bytes": path.stat().st_size,\n                    })\n\n        index_file = Path(index_path)\n        index_file.parent.mkdir(parents=True, exist_ok=True)\n        with index_file.open("w", newline="", encoding="utf-8") as handle:\n            writer = csv.DictWriter(handle, fieldnames=["relative_path", "path", "size_bytes"], delimiter="\\t")\n            writer.writeheader()\n            writer.writerows(rows)\n\n        log_file = Path(log_path)\n        metadata = {\n            "archive_file": archive_file,\n            "results_dir": results_dir,\n            "result_count": len(rows),\n            "result_index": index_path,\n            "log": {\n                "path": log_path,\n                "exists": log_file.exists(),\n                "size_bytes": log_file.stat().st_size if log_file.exists() else 0,\n            },\n            "execution_mode": execution_mode,\n            "ibiosim_executable": executable,\n            "docker_image": docker_image,\n            "quiet": quiet.lower() == "true",\n            "debug": debug.lower() == "true",\n        }\n        Path(metadata_path).write_text(json.dumps(metadata, indent=2, sort_keys=True) + "\\n", encoding="utf-8")\n    ')

    @classmethod
    def _planned_paths(cls, inputs: dict[str, Any], output_dir: str | Path) -> tuple[Path, Path, Path, Path]:
        node_out = Path(output_dir)
        node_out.mkdir(parents=True, exist_ok=True)
        stem = _safe_output_stem(inputs.get('output_name'), _safe_output_stem(inputs.get('archive_file'), 'ibiosim'))
        results_dir = node_out / stem
        return (results_dir, node_out / f'{stem}.result_index.tsv', node_out / f'{stem}.metadata.json', node_out / f'{stem}.log')

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        out_dir = Path(str(inputs.get('output', '.')))
        out_dir.mkdir(parents=True, exist_ok=True)
        results_dir, index_path, metadata_path, log_path = cls._planned_paths(inputs, out_dir)
        results_dir.mkdir(parents=True, exist_ok=True)
        archive_file = str(inputs.get('archive_file', ''))
        execution_mode = str(inputs.get('execution_mode', 'cli') or 'cli').strip().lower()
        executable = str(inputs.get('ibiosim_executable', '') or 'ibiosim')
        docker_image = str(inputs.get('docker_image', '') or 'ghcr.io/biosimulators/ibiosim:latest')
        quiet = bool(inputs.get('quiet', False))
        debug = bool(inputs.get('debug', False))
        if execution_mode not in {'cli', 'docker'}:
            raise ValueError('execution_mode must be one of: cli, docker')
        if execution_mode == 'cli':
            cmd = [executable]
            if debug:
                cmd.append('-d')
            if quiet:
                cmd.append('-q')
            cmd.extend(['-i', archive_file, '-o', str(results_dir)])
        else:
            archive_path = Path(archive_file)
            archive_dir = archive_path.parent
            docker_archive = f'/tmp/ibiosim-input/{archive_path.name}'
            cmd = ['docker', 'run', '--rm', '--mount', f'type=bind,source={archive_dir},target=/tmp/ibiosim-input,readonly', '--mount', f'type=bind,source={results_dir},target=/tmp/ibiosim-output', docker_image]
            if debug:
                cmd.append('-d')
            if quiet:
                cmd.append('-q')
            cmd.extend(['-i', docker_archive, '-o', '/tmp/ibiosim-output'])
        cmd.extend(['>', str(log_path), '2>&1', '&&', 'python', '-c', cls.INDEX_SCRIPT, str(results_dir), str(index_path), str(metadata_path), str(log_path), archive_file, execution_mode, executable, docker_image, str(quiet).lower(), str(debug).lower()])
        return cmd

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        node_out = Path(output_dir) / cls.NODE_ID
        return list(cls._planned_paths(inputs, node_out))

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {'required': {'archive_file': ('FILE', {'description': 'COMBINE/OMEX archive containing SED-ML simulation experiments'})}, 'optional': {'execution_mode': ('STRING', {'default': 'cli', 'options': ['cli', 'docker']}), 'ibiosim_executable': ('STRING', {'default': 'ibiosim', 'description': 'BioSimulators-iBioSim CLI executable name or full path'}), 'docker_image': ('STRING', {'default': 'ghcr.io/biosimulators/ibiosim:latest', 'description': 'Docker image for docker execution mode'}), 'quiet': ('BOOLEAN', {'default': False, 'description': 'Suppress iBioSim console output'}), 'debug': ('BOOLEAN', {'default': False, 'description': 'Enable iBioSim debug mode'}), 'output_name': ('STRING', {'default': '', 'description': 'Optional output directory and filename stem'})}, 'hidden': {'output': ('STRING', {})}}
