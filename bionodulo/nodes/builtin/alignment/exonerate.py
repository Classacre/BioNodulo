"""exonerate — alignment node(s). One tool per file (extracted from wrapped_variant_assembly.py)."""
from __future__ import annotations
from bionodulo.nodes.builtin._wrapped_tool_utils import *


class ExonerateNode(CommandNode):
    """Run Exonerate pairwise sequence comparison."""
    NODE_ID = 'exonerate'
    DISPLAY_NAME = 'Exonerate'
    REQUIRED_CONDA_PACKAGES = ['exonerate', 'python', 'bcbiogff']
    CATEGORY = 'alignment'
    DESCRIPTION = 'Run pairwise sequence comparison with Exonerate alignment models and Galaxy-style GFF outputs.'
    SEARCH_ALIASES = [BIONODULO_BUILTIN_ALIAS, 'Exonerate', 'exonerate pairwise sequence comparison', 'est2genome', 'protein2genome', 'coding2coding', 'target GFF', 'query GFF']
    RETURN_TYPES = ('GFF', 'GFF3', 'TXT')
    RETURN_NAMES = ('output_gff', 'output_gff3', 'output_ali')
    REQUIRED_EXECUTABLES = ['exonerate', 'python']
    DOCUMENTATION_URL = 'https://www.ebi.ac.uk/about/vertebrate-genomics/software/exonerate'
    CITATION_DOIS = ['10.1186/1471-2105-6-31']
    CITATION_URLS = [f'{DOI_URL}10.1186/1471-2105-6-31']
    CITATION_TEXT = 'Exonerate: a generic tool for sequence comparison.'
    VERSION = '2.4.0'
    SHELL = True
    MODELS = ['ungapped', 'est2genome', 'protein2genome', 'coding2coding']
    OUTFORMATS = ['targetgff', 'querygff', 'alignment']
    MODEL_TYPES = {'est2genome': ('dna', 'dna'), 'protein2genome': ('protein', 'dna'), 'coding2coding': ('dna', 'dna')}

    @classmethod
    def _model(cls, inputs: dict[str, Any]) -> str:
        return str(inputs.get('model', 'ungapped') or 'ungapped')

    @classmethod
    def _outformat(cls, inputs: dict[str, Any]) -> str:
        return str(inputs.get('outformat', 'targetgff') or 'targetgff')

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> str:
        out = _out(inputs)
        model = cls._model(inputs)
        outformat = cls._outformat(inputs)
        cmd = ['exonerate', '--query', str(inputs.get('query', '')), '--target', str(inputs.get('target', inputs.get('input_fasta', ''))), '--score', str(inputs.get('score', 100)), '--percent', str(inputs.get('percent', 0.0)), '--bestn', str(inputs.get('bestn', 0)), '--verbose', '0']
        if model != 'ungapped':
            cmd.extend(['--model', model])
        if model in cls.MODEL_TYPES:
            query_type, target_type = cls.MODEL_TYPES[model]
            cmd.extend(['--querytype', query_type, '--targettype', target_type])
        _add_if_value(cmd, '--minintron', inputs.get('minintron'))
        _add_if_value(cmd, '--maxintron', inputs.get('maxintron'))
        cmd.extend(['--cores', f"${{GALAXY_SLOTS:-{inputs.get('threads', 1)}}}"])
        if outformat == 'alignment':
            cmd.extend(['--showalignment', 'yes', '--showvulgar', 'no', '>', f'{out}/output.txt'])
            return _shell_join(cmd).replace("'${GALAXY_SLOTS:-", '${GALAXY_SLOTS:-').replace("}'", '}')
        if outformat == 'querygff':
            cmd.extend(['--showalignment', 'no', '--showvulgar', 'no', '--showtargetgff', 'no', '--showquerygff', 'yes'])
        else:
            cmd.extend(['--showalignment', 'no', '--showvulgar', 'no', '--showtargetgff', 'yes', '--showquerygff', 'no'])
        cmd.extend(['>', f'{out}/output.gff'])
        converter = str(inputs.get('gff3_converter', 'exonerategff_to_gff3.py') or 'exonerategff_to_gff3.py')
        convert_cmd = ['python', converter, f'{out}/output.gff', '>', f'{out}/output.gff3']
        shell_cmd = _shell_join(cmd).replace("'${GALAXY_SLOTS:-", '${GALAXY_SLOTS:-').replace("}'", '}')
        return f'{shell_cmd} && {_shell_join(convert_cmd)}'

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        out = Path(output_dir) / cls.NODE_ID
        out.mkdir(parents=True, exist_ok=True)
        if cls._outformat(inputs) == 'alignment':
            return [out / 'output.txt']
        return [out / 'output.gff', out / 'output.gff3']

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {'required': {'query': ('FASTA', {'description': 'Query sequence FASTA'}), 'target': ('FASTA', {'description': 'Target/reference sequence FASTA'})}, 'optional': {'model': ('STRING', {'default': 'ungapped', 'options': cls.MODELS, 'description': 'Exonerate alignment model'}), 'outformat': ('STRING', {'default': 'targetgff', 'options': cls.OUTFORMATS, 'description': 'Galaxy output format'}), 'score': ('INT', {'default': 100, 'min': 0, 'max': 10000}), 'percent': ('FLOAT', {'default': 0.0, 'min': 0, 'max': 100}), 'bestn': ('INT', {'default': 0, 'min': 0, 'max': 10000}), 'minintron': ('INT', {'default': '', 'min': 0}), 'maxintron': ('INT', {'default': '', 'min': 0}), 'threads': ('INT', {'default': 1, 'min': 1, 'max': 128, 'display': 'slider'}), 'gff3_converter': ('FILE', {'default': 'exonerategff_to_gff3.py', 'description': 'Galaxy helper script that converts Exonerate GFF to GFF3'})}, 'hidden': {'output': ('STRING', {})}}

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        if not str(inputs.get('query', '')).strip():
            return 'query FASTA is required'
        if not str(inputs.get('target', inputs.get('input_fasta', ''))).strip():
            return 'target FASTA is required'
        model = cls._model(inputs)
        if model not in cls.MODELS:
            return 'model must be one of: ungapped, est2genome, protein2genome, coding2coding'
        outformat = cls._outformat(inputs)
        if outformat not in cls.OUTFORMATS:
            return 'outformat must be one of: targetgff, querygff, alignment'
        for name, minimum in {'score': 0, 'bestn': 0, 'minintron': 0, 'maxintron': 0, 'threads': 1}.items():
            raw = inputs.get(name)
            if raw is None or str(raw) == '':
                continue
            try:
                value = int(raw)
            except (TypeError, ValueError):
                return f'{name} must be an integer'
            if value < minimum:
                return f'{name} must be >= {minimum}'
        percent = float(inputs.get('percent', 0.0))
        if percent < 0 or percent > 100:
            return 'percent must be between 0 and 100'
        return super().VALIDATE_INPUTS(inputs)
