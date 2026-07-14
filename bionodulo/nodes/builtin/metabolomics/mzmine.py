"""mzmine — metabolomics node(s). One tool per file (extracted from metabolomics.py)."""
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


class MZmineBatchProcessingNode(CommandNode):
    """Run an MZmine batch workflow from the command-line interface."""
    NODE_ID = 'mzmine_batch_processing'
    DISPLAY_NAME = 'MZmine Batch Processing'
    CATEGORY = 'metabolomics'
    DESCRIPTION = 'Run an MZmine batch workflow for LC-MS preprocessing and export steps.'
    SEARCH_ALIASES = ['mzmine', 'metabolomics', 'lc-ms', 'batch', 'peak detection', 'feature finding']
    RETURN_TYPES = ('DIRECTORY', 'JSON')
    RETURN_NAMES = ('results_dir', 'metadata')
    REQUIRED_EXECUTABLES = ['mzmine']
    REQUIRED_CONDA_PACKAGES = ['mzmine']
    DOCUMENTATION_URL = 'https://mzmine.github.io/mzmine_documentation/commandline_tool.html'
    VERSION = '4.7'
    SHELL = True
    METADATA_SCRIPT = "import json, sys; from pathlib import Path; results=Path(sys.argv[1]); metadata=Path(sys.argv[2]); batch=sys.argv[3]; inputs=sys.argv[4].split('\\n') if sys.argv[4] else []; user=sys.argv[5]; prefs=sys.argv[6]; threads=int(sys.argv[7]) if sys.argv[7] else None; memory=sys.argv[8]; temp=sys.argv[9]; ignore=sys.argv[10].lower() == 'true'; metadata.parent.mkdir(parents=True, exist_ok=True); results.mkdir(parents=True, exist_ok=True); metadata.write_text(json.dumps({'batch_file': batch, 'input_files': inputs, 'user_file': user, 'preferences_file': prefs, 'threads': threads, 'memory_mode': memory, 'temp_dir': temp, 'ignore_parameter_warnings': ignore, 'results_dir': str(results)}, indent=2, sort_keys=True) + '\\n', encoding='utf-8')"

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        out_dir = Path(str(inputs.get('output', '.')))
        out_dir.mkdir(parents=True, exist_ok=True)
        batch_file = str(inputs.get('batch_file', ''))
        stem = _safe_output_stem(inputs.get('output_name'), _safe_output_stem(batch_file, 'mzmine'))
        results_dir = out_dir / stem
        metadata_json = out_dir / f'{stem}.metadata.json'
        input_files = _split_path_list(inputs.get('input_files'))
        input_list_file = out_dir / f'{stem}.input_files.txt'
        user_file = str(inputs.get('user_file', '') or '')
        preferences_file = str(inputs.get('preferences_file', '') or '')
        threads = inputs.get('threads', 1)
        memory_mode = str(inputs.get('memory_mode', '') or '')
        temp_dir = str(inputs.get('temp_dir', '') or '')
        ignore_warnings = bool(inputs.get('ignore_parameter_warnings', False))
        cmd = ['mzmine']
        if user_file:
            cmd.extend(['-user', user_file])
        cmd.extend(['-batch', batch_file])
        if input_files:
            input_list_file.write_text('\n'.join(input_files) + '\n', encoding='utf-8')
            cmd.extend(['-input', str(input_list_file)])
        cmd.extend(['-output', str(results_dir / stem)])
        if temp_dir:
            cmd.extend(['-temp', temp_dir])
        if preferences_file:
            cmd.extend(['-pref', preferences_file])
        if memory_mode:
            cmd.extend(['-memory', memory_mode])
        cmd.extend(['-threads', str(threads)])
        if ignore_warnings:
            cmd.append('-ignore-parameter-warnings')
        cmd.extend(['&&', 'python', '-c', cls.METADATA_SCRIPT, str(results_dir), str(metadata_json), batch_file, '\n'.join(input_files), user_file, preferences_file, str(threads), memory_mode, temp_dir, str(ignore_warnings).lower()])
        return cmd

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        node_out = Path(output_dir) / cls.NODE_ID
        node_out.mkdir(parents=True, exist_ok=True)
        stem = _safe_output_stem(inputs.get('output_name'), _safe_output_stem(inputs.get('batch_file'), 'mzmine'))
        return [node_out / stem, node_out / f'{stem}.metadata.json']

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {'required': {'batch_file': ('FILE', {'description': 'MZmine .mzbatch workflow file'})}, 'optional': {'input_files': ('FILE', {'description': 'Optional input files passed to MZmine as a generated file list'}), 'user_file': ('FILE', {'default': '', 'description': 'Optional MZmine user/login file for offline use'}), 'preferences_file': ('FILE', {'default': '', 'description': 'Optional MZmine preferences file'}), 'threads': ('INT', {'default': 1, 'min': 1, 'max': 64}), 'memory_mode': ('STRING', {'default': '', 'options': ['', 'none', 'all', 'features', 'raw'], 'description': 'MZmine memory mode'}), 'temp_dir': ('DIRECTORY', {'default': '', 'description': 'Optional MZmine temporary directory'}), 'ignore_parameter_warnings': ('BOOLEAN', {'default': False}), 'output_name': ('STRING', {'default': '', 'description': 'Optional output filename stem'})}, 'hidden': {'output': ('STRING', {})}}
