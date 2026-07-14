"""msdial — metabolomics node(s). One tool per file (extracted from metabolomics.py)."""
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
def _split_path_list(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, (list, tuple)):
        return [str(item) for item in value if str(item)]
    text = str(value).strip()
    if not text:
        return []
    return [part.strip() for part in re.split('[\\n,]+', text) if part.strip()]
def _r_string_vector(values: list[str]) -> str:
    quoted = [value.replace('\\', '\\\\').replace('"', '\\"') for value in values]
    return 'c(' + ', '.join((f'"{value}"' for value in quoted)) + ')'
def _r_string(value: Any) -> str:
    text = str(value or '')
    return '"' + text.replace('\\', '\\\\').replace('"', '\\"') + '"'
def _r_bool(value: Any) -> str:
    return 'TRUE' if bool(value) else 'FALSE'


class MSDIALProcessingNode(CommandNode):
    """Run MS-DIAL console batch processing with a user-supplied parameter file."""
    NODE_ID = 'msdial_processing'
    DISPLAY_NAME = 'MS-DIAL Processing'
    CATEGORY = 'metabolomics'
    DESCRIPTION = 'Run MS-DIAL console batch processing for LC-MS or GC-MS data with a parameter file.'
    SEARCH_ALIASES = ['ms-dial', 'msdial', 'metabolomics', 'lcmsdda', 'lcmsdia', 'gcms', 'peak picking']
    RETURN_TYPES = ('DIRECTORY', 'TSV', 'JSON')
    RETURN_NAMES = ('results_dir', 'result_index', 'metadata')
    REQUIRED_EXECUTABLES = ['mono']
    REQUIRED_CONDA_PACKAGES = ['mono']
    DOCUMENTATION_URL = 'https://systemsomicslab.github.io/compms/msdial/consoleapp.html'
    VERSION = '4.0'
    EXPERIMENTAL = True
    SHELL = True
    INDEX_SCRIPT = "import json, sys; from pathlib import Path; results=Path(sys.argv[1]); index=Path(sys.argv[2]); metadata=Path(sys.argv[3]); input_dir=sys.argv[4]; parameter_file=sys.argv[5]; analysis_type=sys.argv[6]; executable=sys.argv[7]; use_mono=sys.argv[8].lower() == 'true'; keep_project=sys.argv[9].lower() == 'true'; files=sorted(p for p in results.rglob('*') if p.is_file()); index.parent.mkdir(parents=True, exist_ok=True); metadata.parent.mkdir(parents=True, exist_ok=True); index.write_text('path\\tname\\tsuffix\\tsize_bytes\\n' + ''.join(f'{p}\\t{p.name}\\t{p.suffix}\\t{p.stat().st_size}\\n' for p in files), encoding='utf-8'); metadata.write_text(json.dumps({'input_dir': input_dir, 'parameter_file': parameter_file, 'analysis_type': analysis_type, 'msdial_executable': executable, 'use_mono': use_mono, 'keep_project_file': keep_project, 'results_dir': str(results), 'result_count': len(files), 'result_files': [str(p) for p in files]}, indent=2, sort_keys=True) + '\\n', encoding='utf-8')"

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        out_dir = Path(str(inputs.get('output', '.')))
        out_dir.mkdir(parents=True, exist_ok=True)
        analysis_type = str(inputs.get('analysis_type', 'lcmsdda') or 'lcmsdda')
        allowed_types = {'gcms', 'lcmsdda', 'lcmsdia'}
        if analysis_type not in allowed_types:
            msg = f'MS-DIAL analysis_type must be one of {sorted(allowed_types)}.'
            raise ValueError(msg)
        input_dir = str(inputs.get('input_dir', ''))
        parameter_file = str(inputs.get('parameter_file', ''))
        msdial_executable = str(inputs.get('msdial_executable', 'MsdialConsoleApp.exe') or 'MsdialConsoleApp.exe')
        use_mono = bool(inputs.get('use_mono', True))
        keep_project_file = bool(inputs.get('keep_project_file', False))
        stem = _safe_output_stem(inputs.get('output_name'), analysis_type)
        results_dir = out_dir / stem
        result_index = out_dir / f'{stem}.result_index.tsv'
        metadata_json = out_dir / f'{stem}.metadata.json'
        cmd: list[str] = []
        if use_mono:
            cmd.append('mono')
        cmd.extend([msdial_executable, analysis_type, '-i', input_dir, '-o', str(results_dir), '-m', parameter_file])
        if keep_project_file:
            cmd.append('-p')
        cmd.extend(['&&', 'python', '-c', cls.INDEX_SCRIPT, str(results_dir), str(result_index), str(metadata_json), input_dir, parameter_file, analysis_type, msdial_executable, str(use_mono).lower(), str(keep_project_file).lower()])
        return cmd

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        node_out = Path(output_dir) / cls.NODE_ID
        node_out.mkdir(parents=True, exist_ok=True)
        stem = _safe_output_stem(inputs.get('output_name'), str(inputs.get('analysis_type', 'lcmsdda') or 'lcmsdda'))
        return [node_out / stem, node_out / f'{stem}.result_index.tsv', node_out / f'{stem}.metadata.json']

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {'required': {'input_dir': ('DIRECTORY', {'description': 'Folder containing MS-DIAL input files'}), 'parameter_file': ('FILE', {'description': 'MS-DIAL parameter text file'})}, 'optional': {'analysis_type': ('STRING', {'default': 'lcmsdda', 'options': ['lcmsdda', 'lcmsdia', 'gcms']}), 'msdial_executable': ('STRING', {'default': 'MsdialConsoleApp.exe', 'description': 'Path to the manually installed MS-DIAL console app'}), 'use_mono': ('BOOLEAN', {'default': True}), 'keep_project_file': ('BOOLEAN', {'default': False, 'description': 'Add -p to keep MS-DIAL MTD project files'}), 'output_name': ('STRING', {'default': '', 'description': 'Optional output filename stem'})}, 'hidden': {'output': ('STRING', {})}}
