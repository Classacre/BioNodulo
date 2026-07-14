"""sirius — metabolomics node(s). One tool per file (extracted from metabolomics.py)."""
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


class SiriusFormulaIDNode(CommandNode):
    """Identify molecular formulas and structures from MS/MS data with SIRIUS."""
    NODE_ID = 'sirius_formula_id'
    DISPLAY_NAME = 'SIRIUS Formula ID'
    CATEGORY = 'metabolomics'
    DESCRIPTION = 'Identify molecular formulas and optional structures from MS/MS spectra using SIRIUS.'
    SEARCH_ALIASES = ['sirius', 'csi:fingerid', 'formula identification', 'metabolomics', 'ms/ms', 'canopus']
    RETURN_TYPES = ('DIRECTORY', 'TSV', 'JSON')
    RETURN_NAMES = ('results_dir', 'summary', 'metadata')
    REQUIRED_EXECUTABLES = ['sirius']
    REQUIRED_CONDA_PACKAGES = ['sirius']
    DOCUMENTATION_URL = 'https://bio.informatik.uni-jena.de/software/sirius/'
    VERSION = '5.8'
    SHELL = True
    SUMMARY_SCRIPT = "import json, sys; from pathlib import Path; results=Path(sys.argv[1]); summary=Path(sys.argv[2]); metadata=Path(sys.argv[3]); spectra=sys.argv[4]; database=sys.argv[5]; profile=sys.argv[6]; ionization=sys.argv[7]; candidates=sorted(results.rglob('*.tsv')) + sorted(results.rglob('*.csv')); summary.parent.mkdir(parents=True, exist_ok=True); metadata.parent.mkdir(parents=True, exist_ok=True); summary.write_text('source_file\\tpath\\n' + ''.join(f'{p.name}\\t{p}\\n' for p in candidates), encoding='utf-8'); metadata.write_text(json.dumps({'spectra_file': spectra, 'database': database, 'profile': profile, 'ionization': ionization, 'results_dir': str(results), 'candidate_tables': [str(p) for p in candidates]}, indent=2, sort_keys=True) + '\\n', encoding='utf-8')"

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        out_dir = Path(str(inputs.get('output', '.')))
        out_dir.mkdir(parents=True, exist_ok=True)
        spectra_file = str(inputs.get('spectra_file', ''))
        stem = _safe_output_stem(inputs.get('output_name'), _safe_output_stem(spectra_file, 'sirius'))
        results_dir = out_dir / stem
        summary_tsv = out_dir / f'{stem}.summary.tsv'
        metadata_json = out_dir / f'{stem}.metadata.json'
        database = str(inputs.get('database', '') or '')
        profile = str(inputs.get('profile', '') or '')
        ionization = str(inputs.get('ionization', '') or '')
        cmd = ['sirius', '-i', spectra_file, '-o', str(results_dir)]
        if database:
            cmd.extend(['--database', database])
        if profile:
            cmd.extend(['--profile', profile])
        if ionization:
            cmd.extend(['--ionization', ionization])
        if inputs.get('ppm_max'):
            cmd.extend(['--ppm-max', str(inputs['ppm_max'])])
        cmd.extend(['--cores', str(inputs.get('cores', 1))])
        cmd.append('formula')
        if inputs.get('run_zodiac', True):
            cmd.append('zodiac')
        if inputs.get('run_structure', False):
            cmd.append('structure')
        if inputs.get('run_canopus', False):
            cmd.append('canopus')
        cmd.extend(['&&', 'python', '-c', cls.SUMMARY_SCRIPT, str(results_dir), str(summary_tsv), str(metadata_json), spectra_file, database, profile, ionization])
        return cmd

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        node_out = Path(output_dir) / cls.NODE_ID
        node_out.mkdir(parents=True, exist_ok=True)
        stem = _safe_output_stem(inputs.get('output_name'), _safe_output_stem(inputs.get('spectra_file'), 'sirius'))
        return [node_out / stem, node_out / f'{stem}.summary.tsv', node_out / f'{stem}.metadata.json']

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {'required': {'spectra_file': ('FILE', {'description': 'MS/MS input file for SIRIUS (.ms, .mgf, .mzML)'})}, 'optional': {'database': ('STRING', {'default': 'ALL', 'description': 'SIRIUS structure database, e.g. ALL'}), 'profile': ('STRING', {'default': '', 'description': 'Instrument/profile preset'}), 'ionization': ('STRING', {'default': '', 'description': 'Ion/adduct, e.g. [M+H]+'}), 'ppm_max': ('FLOAT', {'default': 0.0, 'min': 0.0, 'description': 'Optional maximum precursor ppm error'}), 'cores': ('INT', {'default': 1, 'min': 1, 'max': 64}), 'run_zodiac': ('BOOLEAN', {'default': True}), 'run_structure': ('BOOLEAN', {'default': False}), 'run_canopus': ('BOOLEAN', {'default': False}), 'output_name': ('STRING', {'default': '', 'description': 'Optional output filename stem'})}, 'hidden': {'output': ('STRING', {})}}
