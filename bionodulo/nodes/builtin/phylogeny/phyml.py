"""phyml — phylogeny node(s). One tool per file (extracted from wrapped_phylogeny_assembly.py)."""
from __future__ import annotations
from bionodulo.nodes.builtin._wrapped_tool_utils import *


class PhyMLNode(CommandNode):
    """Infer maximum-likelihood phylogenies with PhyML."""
    NODE_ID = 'phyml'
    DISPLAY_NAME = 'PhyML'
    REQUIRED_CONDA_PACKAGES = ['phyml']
    CATEGORY = 'phylogeny'
    DESCRIPTION = 'Infer maximum-likelihood phylogenies from PHYLIP alignments with PhyML.'
    SEARCH_ALIASES = [BIONODULO_BUILTIN_ALIAS, 'PhyML', 'phyml', 'maximum likelihood', 'phylogeny', 'PHYLIP', 'bootstrap', 'aLRT', 'SH-like branch support']
    RETURN_TYPES = ('PHYLOGENY_TREE', 'TXT', 'TXT')
    RETURN_NAMES = ('output_tree', 'output_stats', 'output_stdout')
    REQUIRED_EXECUTABLES = ['phyml']
    DOCUMENTATION_URL = f'{DOI_URL}{PHYML_CITATION_DOI}'
    CITATION_DOIS = [PHYML_CITATION_DOI]
    CITATION_URLS = [f'{DOI_URL}{PHYML_CITATION_DOI}']
    CITATION_TEXT = PHYML_CITATION_TEXT
    VERSION = '3.3.20220408+galaxy0'
    SHELL = True
    PHYLIP_FORMAT_OPTIONS = ['', '--sequential']
    TYPE_OPTIONS = ['nt', 'aa']
    NT_MODEL_OPTIONS = ['HKY85', 'JC69', 'K80', 'F81', 'F84', 'TN93', 'GTR']
    AA_MODEL_OPTIONS = ['LG', 'WAG', 'JTT', 'MtREV', 'Dayhoff', 'DCMut', 'RtREV', 'CpREV', 'VT', 'Blosum62', 'MtMam', 'MtArt', 'HIVw', 'HIVb']
    EQUI_FREQ_OPTIONS = ['m', 'e']
    MOVE_OPTIONS = ['NNI', 'SPR', 'BEST']
    OPTIMISATION_OPTIONS = ['tlr', 'tl', 'l', 'r', 'n']
    BRANCH_SUPPORT_OPTIONS = ['0', '1', '-1', '-2', '-4', '-5']

    @staticmethod
    def _staged_name(path: str) -> str:
        return sub('[^\\s\\w\\-]', '_', Path(path).name or 'input')

    @classmethod
    def _model(cls, inputs: dict[str, Any]) -> str:
        if str(inputs.get('type_of_seq', 'nt')) == 'aa':
            return str(inputs.get('aa_model', 'LG'))
        return str(inputs.get('nt_model', inputs.get('model', 'HKY85')))

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> str:
        input_file = str(inputs.get('input', ''))
        staged_input = cls._staged_name(input_file)
        commands = [_shell_join(['ln', '-sf', input_file, staged_input])]
        user_tree = str(inputs.get('userInputTree', '') or '')
        staged_tree = ''
        if user_tree:
            staged_tree = cls._staged_name(user_tree)
            commands.append(_shell_join(['ln', '-sf', user_tree, staged_tree]))
        branch_support = str(inputs.get('branchSupport', '-4'))
        bootstrap = str(inputs.get('replicate', 100)) if branch_support == '1' else branch_support
        cmd = ['phyml', '--input', staged_input]
        phylip_format = str(inputs.get('phylip_format', ''))
        if phylip_format:
            cmd.append(phylip_format)
        type_of_seq = str(inputs.get('type_of_seq', 'nt'))
        cmd.extend(['--datatype', type_of_seq, '--multiple', str(inputs.get('nb_data_set', 1)), '--bootstrap', bootstrap, '--model', cls._model(inputs)])
        if type_of_seq == 'nt':
            cmd.extend(['-t', str(inputs.get('tstv', 'e'))])
        cmd.extend(['-f', str(inputs.get('equi_freq', 'm')), '--pinv', str(inputs.get('prop_invar', 'e')), '--nclasses', str(inputs.get('nbSubstCat', 4))])
        if str(inputs.get('nbSubstCat', 4)) != '1':
            cmd.extend(['--alpha', str(inputs.get('gamma', 'e'))])
        cmd.extend(['--search', str(inputs.get('move', 'NNI')), '-o', str(inputs.get('optimisationTopology', 'tlr'))])
        if staged_tree:
            cmd.extend(['--inputtree', staged_tree])
        if str(inputs.get('numStartSeed', 0)) != '0':
            cmd.extend(['--r_seed', str(inputs.get('numStartSeed'))])
        cmd.extend(['--no_memory_check', '|', 'tee', f'{_out(inputs)}/output_stdout.txt'])
        commands.append(_shell_join(cmd))
        return ' && '.join(commands)

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        out = Path(output_dir) / cls.NODE_ID
        out.mkdir(parents=True, exist_ok=True)
        return [out / 'output_tree.nwk', out / 'output_stats.txt', out / 'output_stdout.txt']

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        if not str(inputs.get('input', '')).strip():
            return 'input alignment is required'
        phylip_format = str(inputs.get('phylip_format', ''))
        if phylip_format not in cls.PHYLIP_FORMAT_OPTIONS:
            return f"phylip_format must be one of: {', '.join(cls.PHYLIP_FORMAT_OPTIONS)}"
        type_of_seq = str(inputs.get('type_of_seq', 'nt'))
        if type_of_seq not in cls.TYPE_OPTIONS:
            return f"type_of_seq must be one of: {', '.join(cls.TYPE_OPTIONS)}"
        if type_of_seq == 'nt':
            nt_model = str(inputs.get('nt_model', inputs.get('model', 'HKY85')))
            if nt_model not in cls.NT_MODEL_OPTIONS:
                return f"nt_model must be one of: {', '.join(cls.NT_MODEL_OPTIONS)}"
        else:
            aa_model = str(inputs.get('aa_model', 'LG'))
            if aa_model not in cls.AA_MODEL_OPTIONS:
                return f"aa_model must be one of: {', '.join(cls.AA_MODEL_OPTIONS)}"
        if int(inputs.get('nb_data_set', 1)) < 1:
            return 'nb_data_set must be >= 1'
        if int(inputs.get('nbSubstCat', 4)) < 1:
            return 'nbSubstCat must be >= 1'
        branch_support = str(inputs.get('branchSupport', '-4'))
        if branch_support not in cls.BRANCH_SUPPORT_OPTIONS:
            return f"branchSupport must be one of: {', '.join(cls.BRANCH_SUPPORT_OPTIONS)}"
        if branch_support == '1' and int(inputs.get('replicate', 100)) < 1:
            return 'replicate must be >= 1 when branchSupport is 1'
        move = str(inputs.get('move', 'NNI'))
        if move not in cls.MOVE_OPTIONS:
            return f"move must be one of: {', '.join(cls.MOVE_OPTIONS)}"
        optimisation = str(inputs.get('optimisationTopology', 'tlr'))
        if optimisation not in cls.OPTIMISATION_OPTIONS:
            return f"optimisationTopology must be one of: {', '.join(cls.OPTIMISATION_OPTIONS)}"
        equi_freq = str(inputs.get('equi_freq', 'm'))
        if equi_freq not in cls.EQUI_FREQ_OPTIONS:
            return f"equi_freq must be one of: {', '.join(cls.EQUI_FREQ_OPTIONS)}"
        return True

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {'required': {'input': ('FILE', {'description': 'PHYLIP alignment file for PhyML'})}, 'optional': {'phylip_format': ('STRING', {'default': '', 'options': cls.PHYLIP_FORMAT_OPTIONS, 'description': 'Interleaved or sequential PHYLIP'}), 'nb_data_set': ('INT', {'default': 1, 'min': 1, 'description': 'Number of datasets'}), 'type_of_seq': ('STRING', {'default': 'nt', 'options': cls.TYPE_OPTIONS, 'description': 'Nucleotide or amino-acid alignment'}), 'tstv': ('STRING', {'default': 'e', 'description': 'Transition/transversion ratio or e to estimate', 'advanced': True}), 'nt_model': ('STRING', {'default': 'HKY85', 'options': cls.NT_MODEL_OPTIONS, 'description': 'Nucleotide substitution model'}), 'aa_model': ('STRING', {'default': 'LG', 'options': cls.AA_MODEL_OPTIONS, 'description': 'Amino-acid evolution model'}), 'prop_invar': ('STRING', {'default': 'e', 'description': 'Invariant-site proportion or e to estimate'}), 'equi_freq': ('STRING', {'default': 'm', 'options': cls.EQUI_FREQ_OPTIONS, 'description': 'Equilibrium frequencies'}), 'nbSubstCat': ('INT', {'default': 4, 'min': 1, 'description': 'Discrete gamma model category count'}), 'gamma': ('STRING', {'default': 'e', 'description': 'Gamma model alpha parameter or e to estimate'}), 'move': ('STRING', {'default': 'NNI', 'options': cls.MOVE_OPTIONS, 'description': 'Tree topology search'}), 'optimisationTopology': ('STRING', {'default': 'tlr', 'options': cls.OPTIMISATION_OPTIONS, 'description': 'Optimized parameters'}), 'branchSupport': ('STRING', {'default': '-4', 'options': cls.BRANCH_SUPPORT_OPTIONS, 'description': 'Bootstrap or approximate branch support test'}), 'replicate': ('INT', {'default': 100, 'min': 1, 'description': 'Bootstrap replicate count when branchSupport is 1'}), 'numStartSeed': ('INT', {'default': 0, 'description': 'Random seed; 0 asks PhyML to choose a seed'}), 'userInputTree': ('PHYLOGENY_TREE', {'default': '', 'description': 'Optional Newick/NHX starting tree', 'advanced': True})}, 'hidden': {'output': ('STRING', {})}}
