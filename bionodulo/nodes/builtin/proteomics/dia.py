"""dia — proteomics node(s). One tool per file (extracted from proteomics.py)."""
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


class DIANNNode(CommandNode):
    """Analyze DIA proteomics data with DIA-NN."""
    NODE_ID = 'dia_nn'
    DISPLAY_NAME = 'DIA-NN'
    CATEGORY = 'proteomics'
    DESCRIPTION = 'Analyze DIA (Data Independent Acquisition) proteomics data with DIA-NN.'
    SEARCH_ALIASES = ['dia', 'dia-nn', 'diann', 'data independent acquisition', 'proteomics', 'quantification']
    RETURN_TYPES = ('TSV', 'JSON')
    RETURN_NAMES = ('report', 'stats')
    REQUIRED_EXECUTABLES = ['diann']
    REQUIRED_CONDA_PACKAGES = ['diann']
    DOCUMENTATION_URL = 'https://github.com/vdemichev/DiaNN'
    VERSION = '1.8'
    SHELL = True

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        out_dir = Path(str(inputs.get('output', '.')))
        report = out_dir / 'report.tsv'
        stats = out_dir / 'stats.json'
        raw_files = inputs.get('raw_files', [])
        if isinstance(raw_files, str):
            raw_files = [raw_files] if raw_files else []
        cmd = ['diann', '--lib', str(inputs.get('library', '')), '--fasta', str(inputs.get('fasta', '')), '--out', str(report), '--threads', str(inputs.get('threads', 4)), '--qvalue', str(inputs.get('qvalue', 0.01))]
        if inputs.get('mass_accuracy'):
            cmd.extend(['--mass-acc', str(inputs['mass_accuracy'])])
        if inputs.get('use_predictor'):
            cmd.append('--predictor')
        for raw_file in raw_files:
            cmd.extend(['--f', str(raw_file)])
        cmd.extend(['&&', 'python', '-c', "import csv, json, sys; rows=list(csv.DictReader(open(sys.argv[1]), delimiter='\\t')); json.dump({'rows': len(rows), 'columns': list(rows[0]) if rows else []}, open(sys.argv[2], 'w'))", str(report), str(stats)])
        return cmd

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        node_out = Path(output_dir) / cls.NODE_ID
        node_out.mkdir(parents=True, exist_ok=True)
        return [node_out / 'report.tsv', node_out / 'stats.json']

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {'required': {'raw_files': ('FILE', {'description': 'DIA raw files (.mzML, .raw, .dia)'}), 'library': ('FILE', {'description': 'Spectral library TSV'}), 'fasta': ('FASTA', {'description': 'Protein FASTA database'})}, 'optional': {'threads': ('INT', {'default': 4, 'min': 1, 'max': 64}), 'qvalue': ('FLOAT', {'default': 0.01, 'min': 0.001, 'max': 0.1, 'step': 0.001}), 'mass_accuracy': ('FLOAT', {'default': 0, 'min': 0}), 'use_predictor': ('BOOLEAN', {'default': False})}, 'hidden': {'output': ('STRING', {})}}
