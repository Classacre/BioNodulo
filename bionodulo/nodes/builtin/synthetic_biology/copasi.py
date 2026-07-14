"""copasi — synthetic_biology node(s). One tool per file (extracted from synthetic_biology.py)."""
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


class COPASISimulationNode(CommandNode):
    """Run COPASI batch simulations from configured COPASI, SED-ML, or COMBINE models."""
    NODE_ID = 'copasi_simulation'
    DISPLAY_NAME = 'COPASI Simulation'
    CATEGORY = 'synthetic_biology'
    DESCRIPTION = 'Run COPASI batch simulations using executable model tasks and capture reports.'
    SEARCH_ALIASES = ['copasi', 'CopasiSE', 'synthetic biology', 'biocad', 'kinetic model', 'sbml', 'sed-ml', 'combine archive']
    RETURN_TYPES = ('TSV', 'CPS', 'LOG', 'JSON')
    RETURN_NAMES = ('report', 'updated_model', 'log', 'metadata')
    REQUIRED_EXECUTABLES = ['CopasiSE', 'python']
    REQUIRED_CONDA_PACKAGES: list[str] = []
    DOCUMENTATION_URL = 'https://copasi.org/Support/User_Manual/Model_Creation/Commandline_Version_and_Commandline_Options/'
    VERSION = '1.0'
    EXPERIMENTAL = True
    SHELL = True
    METADATA_SCRIPT = textwrap.dedent('        from __future__ import annotations\n        import json\n        import sys\n        from pathlib import Path\n\n        (\n            metadata_path,\n            model_file,\n            report_file,\n            updated_model,\n            log_file,\n            executable,\n            scheduled_task,\n            sedml_task,\n            validate_only,\n            save_model,\n            verbose,\n            max_time,\n        ) = sys.argv[1:13]\n\n        def file_info(path_text):\n            path = Path(path_text)\n            return {\n                "path": path_text,\n                "exists": path.exists(),\n                "size_bytes": path.stat().st_size if path.exists() else 0,\n            }\n\n        metadata = {\n            "model_file": model_file,\n            "report": file_info(report_file),\n            "updated_model": file_info(updated_model),\n            "log": file_info(log_file),\n            "copasi_executable": executable,\n            "scheduled_task": scheduled_task,\n            "sedml_task": sedml_task,\n            "validate_only": validate_only.lower() == "true",\n            "save_model": save_model.lower() == "true",\n            "verbose": verbose.lower() == "true",\n            "max_time": int(max_time),\n        }\n        Path(metadata_path).write_text(json.dumps(metadata, indent=2, sort_keys=True) + "\\n", encoding="utf-8")\n    ')

    @classmethod
    def _planned_paths(cls, inputs: dict[str, Any], output_dir: str | Path) -> tuple[Path, Path, Path, Path]:
        node_out = Path(output_dir)
        node_out.mkdir(parents=True, exist_ok=True)
        stem = _safe_output_stem(inputs.get('output_name'), _safe_output_stem(inputs.get('model_file'), 'copasi'))
        return (node_out / f'{stem}.report.tsv', node_out / f'{stem}.updated.cps', node_out / f'{stem}.log', node_out / f'{stem}.metadata.json')

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        out_dir = Path(str(inputs.get('output', '.')))
        out_dir.mkdir(parents=True, exist_ok=True)
        report_path, updated_model_path, log_path, metadata_path = cls._planned_paths(inputs, out_dir)
        model_file = str(inputs.get('model_file', ''))
        executable = str(inputs.get('copasi_executable', '') or 'CopasiSE')
        scheduled_task = str(inputs.get('scheduled_task', '') or '').strip()
        sedml_task = str(inputs.get('sedml_task', '') or '').strip()
        save_model = bool(inputs.get('save_model', True))
        validate_only = bool(inputs.get('validate_only', False))
        verbose = bool(inputs.get('verbose', False))
        max_time = int(inputs.get('max_time', 0) or 0)
        if scheduled_task and sedml_task:
            raise ValueError('COPASI supports only one task override; set either scheduled_task or sedml_task, not both')
        if max_time < 0:
            raise ValueError('max_time must be greater than or equal to 0')
        cmd = [executable, '--nologo']
        if verbose:
            cmd.append('--verbose')
        if validate_only:
            cmd.append('--validate')
        cmd.append(model_file)
        if save_model:
            cmd.extend(['-s', str(updated_model_path)])
        cmd.extend(['--report-file', str(report_path)])
        if scheduled_task:
            cmd.extend(['--scheduled-task', scheduled_task])
        if sedml_task:
            cmd.extend(['--sedmlTask', sedml_task])
        if max_time > 0:
            cmd.extend(['--maxTime', str(max_time)])
        cmd.extend(['>', str(log_path), '2>&1', '&&', 'python', '-c', cls.METADATA_SCRIPT, str(metadata_path), model_file, str(report_path), str(updated_model_path), str(log_path), executable, scheduled_task, sedml_task, str(validate_only).lower(), str(save_model).lower(), str(verbose).lower(), str(max_time)])
        return cmd

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        node_out = Path(output_dir) / cls.NODE_ID
        return list(cls._planned_paths(inputs, node_out))

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {'required': {'model_file': ('FILE', {'description': 'COPASI, SBML, SED-ML, or COMBINE archive model file'})}, 'optional': {'copasi_executable': ('STRING', {'default': 'CopasiSE', 'description': 'CopasiSE executable name or full path'}), 'scheduled_task': ('STRING', {'default': '', 'description': 'COPASI task name to run instead of the executable task'}), 'sedml_task': ('STRING', {'default': '', 'description': 'SED-ML task id for SED-ML or COMBINE archive inputs'}), 'save_model': ('BOOLEAN', {'default': True, 'description': 'Save the updated model after execution'}), 'validate_only': ('BOOLEAN', {'default': False, 'description': 'Validate the model file before processing'}), 'verbose': ('BOOLEAN', {'default': False, 'description': 'Enable COPASI verbose output'}), 'max_time': ('INT', {'default': 0, 'min': 0, 'description': 'Maximum CopasiSE runtime in seconds; 0 disables'}), 'output_name': ('STRING', {'default': '', 'description': 'Optional output filename stem'})}, 'hidden': {'output': ('STRING', {})}}
