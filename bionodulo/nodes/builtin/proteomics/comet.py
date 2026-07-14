"""comet — proteomics node(s). One tool per file (extracted from proteomics.py)."""
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


class CometNode(CommandNode):
    """Run Comet for peptide identification from MS/MS spectra."""
    NODE_ID = 'comet'
    DISPLAY_NAME = 'Comet'
    CATEGORY = 'proteomics'
    DESCRIPTION = 'MS/MS database search for peptide identification from mzML, mzXML, or raw spectra.'
    SEARCH_ALIASES = ['comet', 'ms/ms', 'proteomics', 'peptide identification', 'database search', 'pepxml']
    RETURN_TYPES = ('FILE', 'TSV', 'FILE')
    RETURN_NAMES = ('pep_xml', 'psm_tsv', 'params')
    REQUIRED_EXECUTABLES = ['comet']
    REQUIRED_CONDA_PACKAGES = ['comet-ms']
    DOCUMENTATION_URL = 'https://uwpr.github.io/Comet/'
    VERSION = '2024.01'
    SHELL = True

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        out_dir = Path(str(inputs.get('output', '.')))
        out_dir.mkdir(parents=True, exist_ok=True)
        params_file = out_dir / 'comet.params'
        output_stem = out_dir / 'comet'
        spectra_files = inputs.get('spectra_files', [])
        if isinstance(spectra_files, str):
            spectra_files = [spectra_files] if spectra_files else []
        params_lines = [f"database_name = {inputs.get('fasta_db', '')}", f"num_threads = {inputs.get('threads', 4)}", f"peptide_mass_tolerance_lower = {inputs.get('peptide_mass_tolerance_lower', -20)}", f"peptide_mass_tolerance_upper = {inputs.get('peptide_mass_tolerance_upper', 20)}", f"peptide_mass_units = {inputs.get('peptide_mass_units', 2)}", f"fragment_bin_tol = {inputs.get('fragment_bin_tol', 0.02)}", f"fragment_bin_offset = {inputs.get('fragment_bin_offset', 0.0)}", f"search_enzyme_number = {inputs.get('search_enzyme_number', 1)}", f"allowed_missed_cleavage = {inputs.get('allowed_missed_cleavage', 2)}", f"decoy_search = {inputs.get('decoy_search', 1)}", 'output_pepxmlfile = 1', f"output_txtfile = {(1 if inputs.get('output_txtfile', True) else 0)}"]
        params_file.write_text('\n'.join(params_lines) + '\n')
        return ['comet', '-P', str(params_file), '-D', str(inputs.get('fasta_db', '')), '-N', str(output_stem)] + [str(spectra_file) for spectra_file in spectra_files]

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        node_out = Path(output_dir) / cls.NODE_ID
        node_out.mkdir(parents=True, exist_ok=True)
        return [node_out / 'comet.pep.xml', node_out / 'comet.txt', node_out / 'comet.params']

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {'required': {'spectra_files': ('FILE', {'description': 'MS/MS spectra files (.mzML, .mzXML, .mgf, .raw)'}), 'fasta_db': ('FASTA', {'description': 'Target-decoy protein database FASTA'})}, 'optional': {'threads': ('INT', {'default': 4, 'min': 1, 'max': 64}), 'peptide_mass_tolerance_lower': ('FLOAT', {'default': -20.0}), 'peptide_mass_tolerance_upper': ('FLOAT', {'default': 20.0}), 'peptide_mass_units': ('INT', {'default': 2, 'min': 0, 'max': 2, 'label': '0=amu, 1=mmu, 2=ppm'}), 'fragment_bin_tol': ('FLOAT', {'default': 0.02, 'min': 0.0}), 'fragment_bin_offset': ('FLOAT', {'default': 0.0}), 'search_enzyme_number': ('INT', {'default': 1, 'min': 0, 'max': 10}), 'allowed_missed_cleavage': ('INT', {'default': 2, 'min': 0, 'max': 10}), 'decoy_search': ('INT', {'default': 1, 'min': 0, 'max': 2}), 'output_txtfile': ('BOOLEAN', {'default': True})}, 'hidden': {'output': ('STRING', {})}}
