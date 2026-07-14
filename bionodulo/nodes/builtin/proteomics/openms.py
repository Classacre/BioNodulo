"""openms — proteomics node(s). One tool per file (extracted from proteomics.py)."""
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


class OpenMSFeatureFinderNode(CommandNode):
    """Detect peptide features from centroided LC-MS data with OpenMS."""
    NODE_ID = 'openms_feature_finder'
    DISPLAY_NAME = 'OpenMS FeatureFinder'
    CATEGORY = 'proteomics'
    DESCRIPTION = 'Detect peptide features (RT, m/z, intensity) from centroided LC-MS using OpenMS.'
    SEARCH_ALIASES = ['openms', 'feature finder', 'lc-ms', 'peptide feature', 'topp']
    RETURN_TYPES = ('FILE',)
    RETURN_NAMES = ('feature_xml',)
    REQUIRED_EXECUTABLES = ['FeatureFinderCentroided']
    REQUIRED_CONDA_PACKAGES = ['openms']
    DOCUMENTATION_URL = 'https://openms.readthedocs.io/'
    VERSION = '3.2.0'
    SHELL = True

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        out_dir = inputs.get('output', '.')
        cmd = ['FeatureFinderCentroided', '-in', str(inputs.get('mzml_file', '')), '-out', f'{out_dir}/feature_xml.featureXML']
        if inputs.get('ini_file'):
            cmd.extend(['-ini', str(inputs['ini_file'])])
        else:
            cmd.extend(['-algorithm:min_peak_width', str(inputs.get('min_peak_width', 0.2)), '-algorithm:signal_to_noise', str(inputs.get('signal_to_noise', 1.0))])
        if inputs.get('threads'):
            cmd.extend(['-threads', str(inputs['threads'])])
        return cmd

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        node_out = Path(output_dir) / cls.NODE_ID
        node_out.mkdir(parents=True, exist_ok=True)
        return [node_out / 'feature_xml.featureXML']

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {'required': {'mzml_file': ('FILE', {'description': 'Centroided mzML file'})}, 'optional': {'ini_file': ('FILE', {'description': 'OpenMS INI params', 'advanced': True}), 'min_peak_width': ('FLOAT', {'default': 0.2, 'min': 0.05}), 'signal_to_noise': ('FLOAT', {'default': 1.0, 'min': 0.1}), 'threads': ('INT', {'default': 1, 'min': 1, 'max': 64})}, 'hidden': {'output': ('STRING', {})}}


class OpenMSFeatureNode(OpenMSFeatureFinderNode):
    """Compatibility wrapper for the original OpenMS feature roadmap node ID."""
    NODE_ID = 'openms_feature'
    DISPLAY_NAME = 'OpenMS Feature'
    DESCRIPTION = 'Detect peptide features from centroided LC-MS data with OpenMS FeatureFinder.'
    SEARCH_ALIASES = ['openms feature', 'openms', 'feature finder', 'lc-ms', 'peptide feature', 'topp']
