"""checkm2 — qc node(s). One tool per file (extracted from wrapped_assembly_typing.py)."""
from __future__ import annotations
from bionodulo.nodes.builtin._wrapped_tool_utils import *


class CheckM2Node(CommandNode):
    """Assess MAG, SAG, or isolate genome quality with CheckM2."""
    NODE_ID = 'checkm2'
    DISPLAY_NAME = 'CheckM2'
    REQUIRED_CONDA_PACKAGES = ['checkm2']
    CATEGORY = 'qc'
    DESCRIPTION = 'Rapidly predict genome bin completeness and contamination for MAGs, SAGs, and isolate genomes using CheckM2 machine-learning models.'
    SEARCH_ALIASES = [BIONODULO_BUILTIN_ALIAS, 'checkm2', 'CheckM2', 'genome quality', 'MAG quality', 'SAG quality', 'completeness contamination', 'bin quality']
    RETURN_TYPES = ('TSV', 'FASTA_LIST', 'TSV_LIST')
    RETURN_NAMES = ('quality', 'protein_files', 'diamond_files')
    REQUIRED_EXECUTABLES = ['checkm2']
    DOCUMENTATION_URL = 'https://github.com/chklovski/CheckM2'
    CITATION_DOIS = ['10.1038/s41592-023-01940-w']
    CITATION_URLS = ['https://doi.org/10.1038/s41592-023-01940-w']
    CITATION_TEXT = 'CheckM2: a rapid, scalable and accurate tool for assessing microbial genome quality using machine learning.'
    VERSION = '1.1.0'
    SHELL = True

    @classmethod
    def _input_files(cls, inputs: dict[str, Any]) -> list[str]:
        return _as_list(inputs.get('input', inputs.get('inputs')))

    @classmethod
    def _link_name(cls, path: str) -> str:
        return f'{_safe_name(path)}.dat'

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        out = _out(inputs)
        input_dir = f'{out}/input_dir'
        output_dir = f'{out}/output'
        cmd = ['mkdir', '-p', input_dir, output_dir]
        for input_file in cls._input_files(inputs):
            cmd.extend(['&&', 'ln', '-sf', input_file, f'{input_dir}/{cls._link_name(input_file)}'])
        cmd.extend(['&&', 'checkm2', 'predict', '--input', input_dir])
        model = str(inputs.get('model', ''))
        if model:
            cmd.append(model)
        if inputs.get('genes'):
            cmd.append('--genes')
        _add_if_value(cmd, '--ttable', inputs.get('ttable'))
        cmd.extend(['-x', '.dat', '--threads', str(inputs.get('threads', 1)), '--database_path', str(inputs.get('database_path', inputs.get('database', ''))), '--output-directory', output_dir])
        return cmd

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        out = Path(output_dir) / cls.NODE_ID / 'output'
        protein_out = out / 'protein_files'
        diamond_out = out / 'diamond_output'
        protein_out.mkdir(parents=True, exist_ok=True)
        diamond_out.mkdir(parents=True, exist_ok=True)
        return [out / 'quality_report.tsv', protein_out, diamond_out]

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {'required': {'input': ('FASTA_LIST', {'description': 'Input MAG, SAG, isolate genome, or predicted protein FASTA files'}), 'database_path': ('FILE', {'description': 'CheckM2 DIAMOND database path, such as uniref100.KO.1.dmnd'})}, 'optional': {'genes': ('BOOLEAN', {'default': False, 'description': 'Treat input files as predicted protein FASTA files'}), 'model': ('STRING', {'default': '', 'options': ['', '--general', '--specific', '--allmodels'], 'description': 'Force general, specific, or both quality prediction models'}), 'ttable': ('STRING', {'default': '', 'options': CHECKM2_TRANSLATION_TABLES, 'description': 'Prodigal translation table for nucleotide inputs'}), 'threads': ('INT', {'default': 1, 'min': 1, 'max': 128, 'display': 'slider'})}, 'hidden': {'output': ('STRING', {})}}
