"""clustalw — phylogeny node(s). One tool per file (extracted from wrapped_phylogeny_assembly.py)."""
from __future__ import annotations
from bionodulo.nodes.builtin._wrapped_tool_utils import *


class ClustalWNode(CommandNode):
    """Align DNA or protein FASTA sequences with ClustalW."""
    NODE_ID = 'clustalw'
    DISPLAY_NAME = 'ClustalW'
    REQUIRED_CONDA_PACKAGES = ['clustalw']
    CATEGORY = 'phylogeny'
    DESCRIPTION = 'Align DNA or protein FASTA sequences with ClustalW and emit the alignment plus guide tree.'
    SEARCH_ALIASES = [BIONODULO_BUILTIN_ALIAS, 'ClustalW', 'clustalw2', 'clustal', 'multiple sequence alignment', 'DNA alignment', 'protein alignment', 'guide tree']
    RETURN_TYPES = ('ALIGNMENT', 'PHYLOGENY_TREE')
    RETURN_NAMES = ('alignment', 'guide_tree')
    REQUIRED_EXECUTABLES = ['clustalw2']
    DOCUMENTATION_URL = 'http://www.clustal.org/clustal2/'
    CITATION_DOIS = [CLUSTALW_CITATION_DOI]
    CITATION_URLS = [f'{DOI_URL}{CLUSTALW_CITATION_DOI}']
    CITATION_TEXT = CLUSTALW_CITATION_TEXT
    VERSION = '2.1'
    SHELL = True
    OUTPUT_EXTENSIONS = {'clustal': 'aln', 'phylip': 'phy', 'fasta': 'fasta'}

    @classmethod
    def _alignment_output(cls, inputs: dict[str, Any]) -> str:
        outform = str(inputs.get('outform', 'clustal') or 'clustal').lower()
        ext = cls.OUTPUT_EXTENSIONS.get(outform, 'aln')
        return f'{_out(inputs)}/alignment.{ext}'

    @classmethod
    def _append_value_option(cls, cmd: list[str], flag: str, value: Any) -> None:
        if value is not None and str(value) != '':
            cmd.append(f'{flag}={value}')

    @classmethod
    def _append_multiple_alignment_options(cls, cmd: list[str], inputs: dict[str, Any]) -> None:
        cls._append_value_option(cmd, '-GAPOPEN', inputs.get('gapopen'))
        cls._append_value_option(cmd, '-GAPEXT', inputs.get('gapext'))
        if inputs.get('endgaps'):
            cmd.append('-ENDGAPS')
        cls._append_value_option(cmd, '-GAPDIST', inputs.get('gapdist'))
        if inputs.get('nopgap'):
            cmd.append('-NOPGAP')
        if inputs.get('nohgap'):
            cmd.append('-NOHGAP')
        cls._append_value_option(cmd, '-MAXDIV', inputs.get('maxdiv'))
        if inputs.get('negative'):
            cmd.append('-NEGATIVE')
        cls._append_value_option(cmd, '-TRANSWEIGHT', inputs.get('transweight'))

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> str:
        sequence_type = str(inputs.get('sequence_type', 'DNA') or 'DNA').upper()
        outform = str(inputs.get('outform', 'clustal') or 'clustal').lower()
        clustal_output = {'clustal': 'CLUSTAL', 'phylip': 'PHYLIP', 'fasta': 'FASTA'}.get(outform, 'CLUSTAL')
        input_fasta = str(inputs.get('input', ''))
        cmd = ['clustalw2', '-INFILE=input.fasta', f'-OUTFILE={cls._alignment_output(inputs)}', f"-OUTORDER={inputs.get('out_order', 'ALIGNED')}", f'-TYPE={sequence_type}', f'-OUTPUT={clustal_output}']
        if outform == 'clustal' and inputs.get('out_seqnos'):
            cmd.append('-SEQNOS=ON')
        if str(inputs.get('range_mode', 'complete')) == 'part':
            cmd.append(f"-RANGE={inputs.get('seq_range_start', 1)},{inputs.get('seq_range_end', 99999)}")
        algorithm = str(inputs.get('algorithm', 'slow') or 'slow').lower()
        if sequence_type == 'PROTEIN':
            if algorithm == 'fast':
                cmd.append('-QUICKTREE')
                for flag, key in (('-KTUPLE', 'ktuple'), ('-TOPDIAGS', 'topdiags'), ('-WINDOW', 'window'), ('-PAIRGAP', 'pairgap'), ('-SCORE', 'score')):
                    cls._append_value_option(cmd, flag, inputs.get(key))
            else:
                cls._append_value_option(cmd, '-PWMATRIX', inputs.get('pwmatrix', 'GONNET'))
                cls._append_value_option(cmd, '-PWGAPOPEN', inputs.get('pwgapopen'))
                cls._append_value_option(cmd, '-PWGAPEXT', inputs.get('pwgapext'))
            cls._append_value_option(cmd, '-MATRIX', inputs.get('matrix', 'GONNET'))
        else:
            if algorithm == 'fast':
                cmd.append('-QUICKTREE')
                for flag, key in (('-KTUPLE', 'ktuple'), ('-TOPDIAGS', 'topdiags'), ('-WINDOW', 'window'), ('-PAIRGAP', 'pairgap'), ('-SCORE', 'score')):
                    cls._append_value_option(cmd, flag, inputs.get(key))
            else:
                cls._append_value_option(cmd, '-PWDNAMATRIX', inputs.get('pwdnamatrix', 'IUB'))
                cls._append_value_option(cmd, '-PWGAPOPEN', inputs.get('pwgapopen'))
                cls._append_value_option(cmd, '-PWGAPEXT', inputs.get('pwgapext'))
            cls._append_value_option(cmd, '-DNAMATRIX', inputs.get('dn_matrix', 'IUB'))
        cls._append_multiple_alignment_options(cmd, inputs)
        cls._append_value_option(cmd, '-OUTPUTTREE', inputs.get('outputtree', 'PHYLIP'))
        if inputs.get('kimura'):
            cmd.append('-KIMURA')
        if inputs.get('tossgaps'):
            cmd.append('-TOSSGAPS')
        return f"ln -sf {shlex.quote(input_fasta)} input.fasta && {' '.join((shlex.quote(part) for part in cmd))} && cp input.dnd {shlex.quote(f'{_out(inputs)}/guide_tree.dnd')}"

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        out = Path(output_dir) / cls.NODE_ID
        out.mkdir(parents=True, exist_ok=True)
        outform = str(inputs.get('outform', 'clustal') or 'clustal').lower()
        ext = cls.OUTPUT_EXTENSIONS.get(outform, 'aln')
        return [out / f'alignment.{ext}', out / 'guide_tree.dnd']

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        if not inputs.get('input'):
            return 'input FASTA is required'
        base_validation = super().VALIDATE_INPUTS(inputs)
        if base_validation is not True:
            return base_validation
        return True

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {'required': {'input': ('FASTA', {'description': 'FASTA sequences to align'}), 'sequence_type': ('STRING', {'default': 'DNA', 'options': ['DNA', 'PROTEIN'], 'description': 'DNA/RNA or protein sequences'}), 'outform': ('STRING', {'default': 'clustal', 'options': ['clustal', 'phylip', 'fasta'], 'description': 'Alignment output format'})}, 'optional': {'out_order': ('STRING', {'default': 'ALIGNED', 'options': ['ALIGNED', 'INPUT'], 'description': 'Output aligned or input order'}), 'out_seqnos': ('BOOLEAN', {'default': False, 'description': 'Show residue numbers in Clustal output'}), 'range_mode': ('STRING', {'default': 'complete', 'options': ['complete', 'part'], 'description': 'Output complete alignment or a range'}), 'seq_range_start': ('INT', {'default': 1, 'min': 1, 'advanced': True}), 'seq_range_end': ('INT', {'default': 99999, 'min': 1, 'advanced': True}), 'algorithm': ('STRING', {'default': 'slow', 'options': ['slow', 'fast'], 'description': 'Guide-tree algorithm'}), 'pwdnamatrix': ('STRING', {'default': 'IUB', 'options': ['IUB', 'CLUSTALW'], 'advanced': True}), 'dn_matrix': ('STRING', {'default': 'IUB', 'options': ['IUB', 'CLUSTALW'], 'advanced': True}), 'pwmatrix': ('STRING', {'default': 'GONNET', 'options': ['BLOSUM', 'PAM', 'GONNET', 'ID'], 'advanced': True}), 'matrix': ('STRING', {'default': 'GONNET', 'options': ['BLOSUM', 'PAM', 'GONNET', 'ID'], 'advanced': True}), 'pwgapopen': ('INT', {'default': '', 'min': 0, 'advanced': True}), 'pwgapext': ('FLOAT', {'default': '', 'min': 0, 'advanced': True}), 'ktuple': ('INT', {'default': '', 'min': 0, 'advanced': True}), 'topdiags': ('INT', {'default': '', 'min': 0, 'advanced': True}), 'window': ('INT', {'default': '', 'min': 0, 'advanced': True}), 'pairgap': ('INT', {'default': '', 'min': 0, 'advanced': True}), 'score': ('STRING', {'default': 'PERCENT', 'options': ['PERCENT', 'ABSOLUTE'], 'advanced': True}), 'gapopen': ('INT', {'default': '', 'min': 0, 'advanced': True}), 'gapext': ('FLOAT', {'default': '', 'min': 0, 'advanced': True}), 'endgaps': ('BOOLEAN', {'default': False, 'advanced': True}), 'gapdist': ('INT', {'default': '', 'min': 0, 'advanced': True}), 'nopgap': ('BOOLEAN', {'default': False, 'advanced': True}), 'nohgap': ('BOOLEAN', {'default': False, 'advanced': True}), 'maxdiv': ('INT', {'default': '', 'min': 0, 'max': 100, 'advanced': True}), 'negative': ('BOOLEAN', {'default': False, 'advanced': True}), 'transweight': ('FLOAT', {'default': '', 'min': 0, 'max': 1, 'advanced': True}), 'outputtree': ('STRING', {'default': 'PHYLIP', 'options': ['PHYLIP', 'DIST', 'NJ', 'NEXUS'], 'advanced': True}), 'kimura': ('BOOLEAN', {'default': False, 'advanced': True}), 'tossgaps': ('BOOLEAN', {'default': False, 'advanced': True})}, 'hidden': {'output': ('STRING', {})}}
