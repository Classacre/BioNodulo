"""fragpipe — proteomics node(s). One tool per file (extracted from proteomics.py)."""
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


class FragPipeWorkflowNode(CommandNode):
    """Run a FragPipe headless proteomics workflow."""
    NODE_ID = 'fragpipe'
    DISPLAY_NAME = 'FragPipe Workflow'
    CATEGORY = 'proteomics'
    DESCRIPTION = 'Run FragPipe headless workflows for end-to-end proteomics processing.'
    SEARCH_ALIASES = ['fragpipe', 'headless', 'msfragger', 'proteomics', 'proteomics workflow', 'peptide identification']
    RETURN_TYPES = ('DIRECTORY',)
    RETURN_NAMES = ('results_dir',)
    REQUIRED_EXECUTABLES = ['fragpipe']
    REQUIRED_CONDA_PACKAGES = ['fragpipe']
    DOCUMENTATION_URL = 'https://fragpipe.nesvilab.org/'
    VERSION = '24.0'
    SHELL = True
    EXPERIMENTAL = True

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        base_validation = super().VALIDATE_INPUTS(inputs)
        if base_validation is not True:
            return base_validation
        if not str(inputs.get('workflow_file', '')).strip():
            return 'FragPipe Workflow requires a workflow file.'
        if not str(inputs.get('manifest_file', '')).strip():
            return 'FragPipe Workflow requires a manifest file.'
        return True

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        validation = cls.VALIDATE_INPUTS(inputs)
        if validation is not True:
            raise ValueError(str(validation))
        out_dir = Path(str(inputs.get('output', '.')))
        out_dir.mkdir(parents=True, exist_ok=True)
        return ['fragpipe', '--headless', '--workflow', str(inputs.get('workflow_file', '')), '--manifest', str(inputs.get('manifest_file', '')), '--workdir', str(out_dir)]

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        node_out = Path(output_dir) / cls.NODE_ID
        node_out.mkdir(parents=True, exist_ok=True)
        return [node_out]

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {'required': {'workflow_file': ('FILE', {'description': 'FragPipe workflow file (.workflow)'}), 'manifest_file': ('FILE', {'description': 'FragPipe manifest file (.fp-manifest)'})}, 'optional': {}, 'hidden': {'output': ('STRING', {})}}
