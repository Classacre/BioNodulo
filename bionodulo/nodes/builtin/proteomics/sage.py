"""sage — proteomics node(s). One tool per file (extracted from proteomics.py)."""
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


class SageSearchNode(CommandNode):
    """Run Sage for fast peptide-spectrum matching."""
    NODE_ID = 'sage_search'
    DISPLAY_NAME = 'Sage Search'
    CATEGORY = 'proteomics'
    DESCRIPTION = 'Fast Rust-based peptide-spectrum matching for large-scale proteomics searches.'
    SEARCH_ALIASES = ['sage', 'sage-proteomics', 'proteomics', 'peptide identification', 'database search']
    RETURN_TYPES = ('TSV', 'JSON', 'FILE', 'FILE')
    RETURN_NAMES = ('results_tsv', 'results_json', 'config_json', 'pin_file')
    REQUIRED_EXECUTABLES = ['sage']
    REQUIRED_CONDA_PACKAGES = ['sage-proteomics']
    DOCUMENTATION_URL = 'https://github.com/lazear/sage'
    VERSION = '0.14.7'

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        base_validation = super().VALIDATE_INPUTS(inputs)
        if base_validation is not True:
            return base_validation
        if not _file_list(inputs.get('spectra_files')):
            return 'Sage Search requires at least one spectra file.'
        if int(inputs.get('threads', 4) or 0) <= 0:
            return 'Sage Search threads must be greater than zero.'
        return True

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        validation = cls.VALIDATE_INPUTS(inputs)
        if validation is not True:
            raise ValueError(str(validation))
        out_dir = Path(str(inputs.get('output', '.')))
        out_dir.mkdir(parents=True, exist_ok=True)
        spectra_files = _file_list(inputs.get('spectra_files'))
        config_file = out_dir / 'sage_config.json'
        fasta_db = str(inputs.get('fasta_db', ''))
        prec_ppm = inputs.get('precursor_tol_ppm', 20)
        frag_da = inputs.get('fragment_tol_da', 0.05)
        config = {'database': {'fasta': fasta_db}, 'mzml_paths': spectra_files, 'precursor_tol': {'ppm': [-abs(prec_ppm), abs(prec_ppm)]}, 'fragment_tol': {'da': [-abs(frag_da), abs(frag_da)]}, 'enzyme': _sage_enzyme_config(inputs), 'output_paths': {'results': 'results.sage.tsv'}}
        config_file.write_text(_sage_config_text(config), encoding='utf-8')
        cmd = ['sage', str(config_file), '-f', fasta_db, '-o', str(out_dir)]
        if inputs.get('write_pin', True):
            cmd.append('--write-pin')
        if inputs.get('parquet'):
            cmd.append('--parquet')
        cmd.extend(spectra_files)
        return cmd

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        node_out = Path(output_dir) / cls.NODE_ID
        node_out.mkdir(parents=True, exist_ok=True)
        outputs = [node_out / 'results.sage.tsv', node_out / 'results.json', node_out / 'sage_config.json']
        if inputs.get('write_pin', True):
            outputs.append(node_out / 'results.pin')
        return outputs

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {'required': {'spectra_files': ('FILE', {'description': 'MS/MS spectra files (.mzML, .mzXML, .mgf)'}), 'fasta_db': ('FASTA', {'description': 'Target-decoy protein database FASTA'})}, 'optional': {'threads': ('INT', {'default': 4, 'min': 1, 'max': 64}), 'precursor_tol_ppm': ('FLOAT', {'default': 20.0, 'min': 0.0}), 'fragment_tol_da': ('FLOAT', {'default': 0.05, 'min': 0.0}), 'enzyme': ('STRING', {'default': 'trypsin', 'options': ['trypsin']}), 'missed_cleavages': ('INT', {'default': 2, 'min': 0, 'max': 10}), 'min_peptide_length': ('INT', {'default': 7, 'min': 4, 'max': 60}), 'max_peptide_length': ('INT', {'default': 40, 'min': 4, 'max': 100}), 'write_pin': ('BOOLEAN', {'default': True, 'description': 'Ask Sage to write Percolator PIN output'}), 'parquet': ('BOOLEAN', {'default': False, 'description': 'Ask Sage to write parquet output when supported'})}, 'hidden': {'output': ('STRING', {})}}
