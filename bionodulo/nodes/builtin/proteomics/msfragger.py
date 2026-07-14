"""msfragger — proteomics node(s). One tool per file (extracted from proteomics.py)."""
from __future__ import annotations
import json
from pathlib import Path
from typing import Any
from bionodulo.nodes.command_node import CommandNode
def _file_list(value: Any) -> list[str]:
    if isinstance(value, list | tuple):
        return [str(item) for item in value if str(item)]
    text = str(value or '')
    return [text] if text else []
def _sage_enzyme_config(inputs: dict[str, Any]) -> dict[str, Any]:
    enzyme = str(inputs.get('enzyme', 'trypsin') or 'trypsin').lower()
    config = {'missed_cleavages': int(inputs.get('missed_cleavages', 2)), 'min_len': int(inputs.get('min_peptide_length', 7)), 'max_len': int(inputs.get('max_peptide_length', 40))}
    if enzyme == 'trypsin':
        config.update({'cleave_at': 'KR', 'restrict': 'P'})
    return config
def _sage_config_text(config: dict[str, Any]) -> str:
    enzyme = config['enzyme']
    enzyme_items = ', '.join((f'{json.dumps(key)}: {json.dumps(value)}' for key, value in enzyme.items()))
    return f"""{{\n  "database": {json.dumps(config['database'])},\n  "mzml_paths": {json.dumps(config['mzml_paths'])},\n  "precursor_tol": {json.dumps(config['precursor_tol'])},\n  "fragment_tol": {json.dumps(config['fragment_tol'])},\n  "enzyme": {{{enzyme_items}}},\n  "output_paths": {json.dumps(config['output_paths'])}\n}}\n"""


class MSFraggerNode(CommandNode):
    """Run MSFragger for peptide identification."""
    NODE_ID = 'msfragger'
    DISPLAY_NAME = 'MSFragger'
    CATEGORY = 'proteomics'
    DESCRIPTION = 'Ultra-fast peptide identification. Supports open search for PTM discovery and closed search.'
    SEARCH_ALIASES = ['msfragger', 'fragpipe', 'proteomics', 'peptide identification', 'database search']
    RETURN_TYPES = ('FILE',)
    RETURN_NAMES = ('pepxml',)
    REQUIRED_EXECUTABLES = ['msfragger']
    REQUIRED_CONDA_PACKAGES = ['msfragger']
    DOCUMENTATION_URL = 'https://msfragger.nesvilab.org/'
    VERSION = '4.1'
    SHELL = True
    EXPERIMENTAL = True

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        out_dir = Path(inputs.get('output', '.'))
        out_dir.mkdir(parents=True, exist_ok=True)
        params_file = out_dir / 'fragger.params'
        raw_files = inputs.get('raw_files', [])
        if isinstance(raw_files, str):
            raw_files = [raw_files]
        params_lines = [f"database_name = {inputs.get('fasta_db', '')}", f"num_threads = {inputs.get('threads', 4)}", f"precursor_mass_lower = -{inputs.get('prec_tol_low', 20)}", f"precursor_mass_upper = {inputs.get('prec_tol_high', 20)}", f"precursor_mass_units = {inputs.get('prec_tol_units', 1)}", f"fragment_mass_tolerance = {inputs.get('frag_tol', 20)}", f"fragment_mass_units = {inputs.get('frag_tol_units', 1)}", f"calibrate_mass = {inputs.get('calibrate_mass', 'none')}"]
        if not inputs.get('open_search'):
            params_lines.extend(['variable_mod_01 = 15.99490 M', 'variable_mod_02 = 42.01060 [^'])
        params_lines.append('output_format = pepxml')
        params_file.write_text('\n'.join(params_lines) + '\n')
        return ['msfragger', str(params_file)] + [str(raw_file) for raw_file in raw_files]

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        node_out = Path(output_dir) / cls.NODE_ID
        node_out.mkdir(parents=True, exist_ok=True)
        return [node_out / 'pepxml.pepXML']

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {'required': {'raw_files': ('FILE', {'description': 'MS raw files (.mzML, .mzXML, .raw)'}), 'fasta_db': ('FASTA', {'description': 'Target-decoy protein DB FASTA'}), 'threads': ('INT', {'default': 4, 'min': 1, 'max': 64})}, 'optional': {'open_search': ('BOOLEAN', {'default': False, 'description': 'Open search for PTM discovery'}), 'prec_tol_low': ('FLOAT', {'default': 20.0}), 'prec_tol_high': ('FLOAT', {'default': 20.0}), 'prec_tol_units': ('INT', {'default': 1, 'min': 0, 'max': 1, 'label': '0=Da, 1=ppm'}), 'frag_tol': ('FLOAT', {'default': 20.0}), 'frag_tol_units': ('INT', {'default': 1, 'min': 0, 'max': 1}), 'calibrate_mass': ('STRING', {'default': 'none', 'options': ['none', 'coarse', 'iterative']})}, 'hidden': {'output': ('STRING', {})}}
