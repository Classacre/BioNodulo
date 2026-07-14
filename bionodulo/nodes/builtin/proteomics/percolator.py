"""percolator — proteomics node(s). One tool per file (extracted from proteomics.py)."""
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


class PercolatorNode(CommandNode):
    """Run Percolator for PSM validation and FDR estimation."""
    NODE_ID = 'percolator'
    DISPLAY_NAME = 'Percolator'
    CATEGORY = 'proteomics'
    DESCRIPTION = 'Semi-supervised ML for PSM validation and FDR estimation. Superior to target-decoy alone.'
    SEARCH_ALIASES = ['percolator', 'psm validation', 'fdr', 'peptide spectrum match']
    RETURN_TYPES = ('TSV', 'TSV')
    RETURN_NAMES = ('percolator_psms', 'percolator_proteins')
    REQUIRED_EXECUTABLES = ['percolator']
    REQUIRED_CONDA_PACKAGES = ['percolator']
    DOCUMENTATION_URL = 'https://github.com/percolator/percolator'
    VERSION = '3.7.1'
    SHELL = True

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        out_dir = inputs.get('output', '.')
        cmd = ['percolator', str(inputs.get('pin_file', '')), '-X', f'{out_dir}/percolator_psms.tsv', '--protein-decoy-pattern', str(inputs.get('decoy_prefix', 'decoy')), '--decoy-xml-output', '--no-split-large-instances']
        if inputs.get('fdr_psm'):
            cmd.extend(['--post-processing-tdc', '--fdr', str(inputs['fdr_psm'])])
        if inputs.get('fdr_protein'):
            cmd.extend(['--picked-protein', str(inputs.get('fasta_db', ''))])
            cmd.extend(['--protein-fdr', str(inputs['fdr_protein'])])
        if inputs.get('enzyme'):
            cmd.extend(['--enzyme', str(inputs['enzyme'])])
        cmd.extend(['-l', f'{out_dir}/percolator_proteins.tsv'])
        return cmd

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        node_out = Path(output_dir) / cls.NODE_ID
        node_out.mkdir(parents=True, exist_ok=True)
        return [node_out / 'percolator_psms.tsv', node_out / 'percolator_proteins.tsv']

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {'required': {'pin_file': ('FILE', {'description': 'PIN file from search engine'}), 'fasta_db': ('FASTA', {'description': 'Protein DB FASTA'})}, 'optional': {'decoy_prefix': ('STRING', {'default': 'decoy'}), 'fdr_psm': ('FLOAT', {'default': 0.01, 'min': 0.001, 'max': 0.1, 'step': 0.001}), 'fdr_protein': ('FLOAT', {'default': 0.01, 'min': 0.001, 'max': 0.1, 'step': 0.001}), 'enzyme': ('STRING', {'default': 'trypsin', 'options': ['trypsin', 'chymotrypsin', 'lys-c', 'argc']})}, 'hidden': {'output': ('STRING', {})}}
