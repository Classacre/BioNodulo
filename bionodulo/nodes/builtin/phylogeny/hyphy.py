"""hyphy — phylogeny node(s). One tool per file (extracted from wrapped_hyphy_metagenomics.py)."""
from __future__ import annotations
from bionodulo.nodes.builtin._wrapped_tool_utils import *


class HyPhyABSRELNode(CommandNode):
    """Detect episodic diversifying selection with HyPhy aBSREL."""
    NODE_ID = 'hyphy_absrel'
    DISPLAY_NAME = 'HyPhy-aBSREL'
    REQUIRED_CONDA_PACKAGES = ['hyphy']
    CATEGORY = 'phylogeny'
    DESCRIPTION = 'Detect episodic diversifying selection with adaptive Branch-Site Random Effects Likelihood.'
    SEARCH_ALIASES = [BIONODULO_BUILTIN_ALIAS, 'HyPhy', 'aBSREL', 'adaptive branch-site random effects likelihood', 'episodic diversifying selection', 'selection', 'phylogenetics']
    RETURN_TYPES = ('TEXT', 'JSON')
    RETURN_NAMES = ('absrel_md_report', 'absrel_output')
    REQUIRED_EXECUTABLES = ['hyphy']
    DOCUMENTATION_URL = 'http://www.hyphy.org/methods/selection-methods/#absrel'
    CITATION_DOIS = HYPHY_ABSREL_CITATION_DOIS
    CITATION_URLS = [f'{DOI_URL}{doi}' for doi in HYPHY_ABSREL_CITATION_DOIS]
    CITATION_TEXT = HYPHY_ABSREL_CITATION_TEXT
    VERSION = '2.5.96'
    SHELL = True
    GENETIC_CODES = ['Universal', 'Vertebrate-mtDNA', 'Yeast-mtDNA', 'Mold-Protozoan-mtDNA', 'Invertebrate-mtDNA', 'Ciliate-Nuclear', 'Echinoderm-mtDNA', 'Euplotid-Nuclear', 'Alt-Yeast-Nuclear', 'Ascidian-mtDNA', 'Flatworm-mtDNA', 'Blepharisma-Nuclear', 'Chlorophycean-mtDNA', 'Trematode-mtDNA', 'Scenedesmus-obliquus-mtDNA', 'Thraustochytrium-mtDNA', 'Pterobranchia-mtDNA', 'SR1-and-Gracilibacteria', 'Pachysolen-Nuclear', 'Mesodinium-Nuclear', 'Peritrich-Nuclear', 'Cephalodiscidae-mtDNA']
    BRANCH_SELECTIONS = ['All', 'Internal', 'Leaves', 'Unlabeled-branches', 'specify']
    MULTIPLE_HITS = ['None', 'Double', 'Double+Triple']
    KILL_ZERO_LENGTHS = ['Yes', 'Constrain', 'No']
    INPUT_EXTENSIONS = ['fasta', 'fasta.gz', 'nex']

    @classmethod
    def _input_name(cls, inputs: dict[str, Any]) -> str:
        ext = str(inputs.get('input_ext', 'fasta')).strip().lstrip('.') or 'fasta'
        return f'input.{ext}'

    @classmethod
    def _branch_arg(cls, inputs: dict[str, Any]) -> str:
        branch_sel = str(inputs.get('branch_sel', 'All') or 'All')
        if branch_sel == 'specify':
            return str(inputs.get('branch_label', '')).strip()
        return branch_sel

    @classmethod
    def _srv_enabled(cls, inputs: dict[str, Any]) -> bool:
        value = inputs.get('srv_enabled', True)
        if isinstance(value, str):
            return value.lower() in {'true', 'yes', '1', 'on'}
        return bool(value)

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> str:
        out = _out(inputs)
        input_name = cls._input_name(inputs)
        commands: list[str] = []
        if str(inputs.get('input_nhx', '')).strip():
            commands.append(_shell_join(['ln', '-s', str(inputs.get('input_nhx', '')), 'input.nhx']))
        commands.append(_shell_join(['ln', '-s', str(inputs.get('input_file', '')), input_name]))
        commands.append(_shell_join(['ln', '-s', f'{out}/absrel_output.json', f'{input_name}.aBSREL.json']))
        cmd = ['hyphy', f"CPU={inputs.get('threads', 4)}", 'absrel', '--alignment', f'./{input_name}']
        if str(inputs.get('input_nhx', '')).strip():
            cmd.extend(['--tree', 'input.nhx'])
        cmd.extend(['--code', str(inputs.get('gencodeid', 'Universal') or 'Universal'), '--branches', cls._branch_arg(inputs), '--output', f'{out}/absrel_output.json', '--multiple-hits', str(inputs.get('multiple_hits', 'None') or 'None')])
        if cls._srv_enabled(inputs):
            cmd.extend(['--srv', 'Yes', '--syn-rates', str(inputs.get('syn_rates', 3))])
        cmd.extend(['--blb', str(inputs.get('blb', 1.0)), '--kill-zero-lengths', str(inputs.get('kill_zero_lengths', 'Yes') or 'Yes'), '>', f'{out}/absrel_stdout.md'])
        commands.append(_shell_join(cmd))
        return ' && '.join(commands)

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        out = Path(output_dir) / cls.NODE_ID
        out.mkdir(parents=True, exist_ok=True)
        return [out / 'absrel_stdout.md', out / 'absrel_output.json']

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        if not str(inputs.get('input_file', '')).strip():
            return 'HyPhy-aBSREL alignment input is required'
        gencodeid = str(inputs.get('gencodeid', 'Universal') or 'Universal')
        if gencodeid not in cls.GENETIC_CODES:
            return f'Unsupported HyPhy genetic code: {gencodeid}'
        branch_sel = str(inputs.get('branch_sel', 'All') or 'All')
        if branch_sel not in cls.BRANCH_SELECTIONS:
            return f'Unsupported HyPhy-aBSREL branch selection: {branch_sel}'
        if branch_sel == 'specify' and (not str(inputs.get('branch_label', '')).strip()):
            return 'HyPhy-aBSREL custom branch selection requires a branch label'
        multiple_hits = str(inputs.get('multiple_hits', 'None') or 'None')
        if multiple_hits not in cls.MULTIPLE_HITS:
            return f'Unsupported HyPhy-aBSREL multiple-hits mode: {multiple_hits}'
        if cls._srv_enabled(inputs):
            try:
                syn_rates = int(inputs.get('syn_rates', 3))
            except (TypeError, ValueError):
                return 'HyPhy-aBSREL synonymous rate classes must be between 1 and 10'
            if syn_rates < 1 or syn_rates > 10:
                return 'HyPhy-aBSREL synonymous rate classes must be between 1 and 10'
        kill_zero_lengths = str(inputs.get('kill_zero_lengths', 'Yes') or 'Yes')
        if kill_zero_lengths not in cls.KILL_ZERO_LENGTHS:
            return f'Unsupported HyPhy-aBSREL zero-length branch handling: {kill_zero_lengths}'
        try:
            threads = int(inputs.get('threads', 4))
        except (TypeError, ValueError):
            return 'HyPhy-aBSREL threads must be a positive integer'
        if threads < 1:
            return 'HyPhy-aBSREL threads must be a positive integer'
        try:
            blb = float(inputs.get('blb', 1.0))
        except (TypeError, ValueError):
            return 'HyPhy-aBSREL BLB resampling value must be non-negative'
        if blb < 0:
            return 'HyPhy-aBSREL BLB resampling value must be non-negative'
        return True

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {'required': {'input_file': ('FASTA', {'description': 'Codon alignment in FASTA, compressed FASTA, or NEXUS format'})}, 'optional': {'input_nhx': ('FILE', {'default': '', 'description': 'Optional Newick/NHX phylogenetic tree'}), 'input_ext': ('STRING', {'default': 'fasta', 'options': cls.INPUT_EXTENSIONS, 'advanced': True}), 'gencodeid': ('STRING', {'default': 'Universal', 'options': cls.GENETIC_CODES, 'description': 'HyPhy genetic code for codon interpretation'}), 'branch_sel': ('STRING', {'default': 'All', 'options': cls.BRANCH_SELECTIONS, 'description': 'Branches to test for episodic diversifying selection'}), 'branch_label': ('STRING', {'default': '', 'description': 'Custom branch label when branch selection is specify'}), 'multiple_hits': ('STRING', {'default': 'None', 'options': cls.MULTIPLE_HITS, 'description': 'Multiple-hit correction mode', 'advanced': True}), 'blb': ('FLOAT', {'default': 1.0, 'min': 0, 'description': 'Bag of little bootstrap resampling rate'}), 'srv_enabled': ('BOOLEAN', {'default': True, 'description': 'Enable synonymous rate variation modelling'}), 'syn_rates': ('INT', {'default': 3, 'min': 1, 'max': 10, 'description': 'Synonymous rate classes'}), 'kill_zero_lengths': ('STRING', {'default': 'Yes', 'options': cls.KILL_ZERO_LENGTHS, 'description': 'Zero-length branch handling', 'advanced': True}), 'threads': ('INT', {'default': 4, 'min': 1, 'max': 128})}, 'hidden': {'output': ('STRING', {})}}


class HyPhyAnnotateNode(CommandNode):
    """Annotate branches in a Newick/NHX tree with HyPhy label-tree."""
    NODE_ID = 'hyphy_annotate'
    DISPLAY_NAME = 'HyPhy Annotate'
    REQUIRED_CONDA_PACKAGES = ['hyphy']
    CATEGORY = 'phylogeny'
    DESCRIPTION = 'Annotate a Newick/NHX phylogenetic tree with HyPhy label-tree.'
    SEARCH_ALIASES = [BIONODULO_BUILTIN_ALIAS, 'HyPhy', 'label-tree', 'Annotate', 'Newick annotation', 'branch labels', 'phylogenetic tree annotation']
    RETURN_TYPES = ('PHYLOGENY_TREE', 'TEXT')
    RETURN_NAMES = ('labeled_tree', 'annotate_md_report')
    REQUIRED_EXECUTABLES = ['hyphy']
    DOCUMENTATION_URL = 'https://github.com/veg/hyphy/blob/master/res/TemplateBatchFiles/lib/label-tree.bf'
    CITATION_DOIS = [HYPHY_CITATION_DOI]
    CITATION_URLS = [f'{DOI_URL}{HYPHY_CITATION_DOI}']
    CITATION_TEXT = HYPHY_CITATION_TEXT
    VERSION = '2.5.96'
    SHELL = True
    SELECTION_METHODS = ['regexp', 'list']
    INTERNAL_NODE_STRATEGIES = ['All descendants', 'None', 'All descendants, no MRCA', 'Some descendants', 'Parsimony']
    LEAF_NODE_STRATEGIES = ['Label', 'Skip']

    @classmethod
    def _invert_value(cls, inputs: dict[str, Any]) -> str:
        value = inputs.get('invert', False)
        if isinstance(value, str):
            return 'Yes' if value.lower() in {'true', 'yes', '1', 'on', '--invert yes'} else 'No'
        return 'Yes' if bool(value) else 'No'

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> str:
        out = _out(inputs)
        commands = [_shell_join(['cp', str(inputs.get('input_tree', '')), 'input.nhx'])]
        cmd = ['hyphy', 'label-tree', '--tree', 'input.nhx', '--output', f'{out}/labeled_tree.nhx']
        selection_method = str(inputs.get('selection_method', 'regexp') or 'regexp')
        if selection_method == 'list':
            cmd.extend(['--list', str(inputs.get('list_file', ''))])
        else:
            cmd.extend(['--regexp', str(inputs.get('regexp', ''))])
        cmd.extend(['--label', str(inputs.get('label', 'Foreground') or 'Foreground'), '--reroot', str(inputs.get('reroot', 'None') or 'None'), '--invert', cls._invert_value(inputs), '--internal-nodes', str(inputs.get('internal_nodes', 'All descendants') or 'All descendants'), '--leaf-nodes', str(inputs.get('leaf_nodes', 'Label') or 'Label'), '>', f'{out}/annotate_stdout.md', '2>/dev/null'])
        commands.append(_shell_join(cmd))
        return ' && '.join(commands)

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        out = Path(output_dir) / cls.NODE_ID
        out.mkdir(parents=True, exist_ok=True)
        return [out / 'labeled_tree.nhx', out / 'annotate_stdout.md']

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        if not str(inputs.get('input_tree', '')).strip():
            return 'HyPhy Annotate input tree is required'
        selection_method = str(inputs.get('selection_method', 'regexp') or 'regexp')
        if selection_method not in cls.SELECTION_METHODS:
            return f'Unsupported HyPhy Annotate selection method: {selection_method}'
        if selection_method == 'regexp':
            regexp = str(inputs.get('regexp', '')).strip()
            if not regexp:
                return 'HyPhy Annotate regular expression is required'
            if regexp.endswith('\\'):
                return 'HyPhy Annotate regular expression must not end with a backslash'
        if selection_method == 'list' and (not str(inputs.get('list_file', '')).strip()):
            return 'HyPhy Annotate sequence list file is required'
        if not str(inputs.get('label', 'Foreground')).strip():
            return 'HyPhy Annotate label is required'
        internal_nodes = str(inputs.get('internal_nodes', 'All descendants') or 'All descendants')
        if internal_nodes not in cls.INTERNAL_NODE_STRATEGIES:
            return f'Unsupported HyPhy Annotate internal-node strategy: {internal_nodes}'
        leaf_nodes = str(inputs.get('leaf_nodes', 'Label') or 'Label')
        if leaf_nodes not in cls.LEAF_NODE_STRATEGIES:
            return f'Unsupported HyPhy Annotate leaf-node strategy: {leaf_nodes}'
        return True

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {'required': {'input_tree': ('PHYLOGENY_TREE', {'description': 'Newick/NHX tree to annotate'}), 'selection_method': ('STRING', {'default': 'regexp', 'options': cls.SELECTION_METHODS, 'description': 'Select branches by regular expression or sequence-name list'})}, 'optional': {'regexp': ('STRING', {'default': '', 'description': 'Regular expression used to select matching leaf names'}), 'list_file': ('FILE', {'default': '', 'description': 'Line list of sequence names used when selection method is list'}), 'label': ('STRING', {'default': 'Foreground', 'description': 'Label to apply to selected branches'}), 'reroot': ('STRING', {'default': 'None', 'description': 'Tree node to reroot on, or None to skip rerooting'}), 'invert': ('BOOLEAN', {'default': False, 'description': 'Invert the regex or list branch selection'}), 'internal_nodes': ('STRING', {'default': 'All descendants', 'options': cls.INTERNAL_NODE_STRATEGIES, 'description': 'Strategy for labeling internal nodes'}), 'leaf_nodes': ('STRING', {'default': 'Label', 'options': cls.LEAF_NODE_STRATEGIES, 'description': 'Strategy for labeling selected leaves'})}, 'hidden': {'output': ('STRING', {})}}


class HyPhyBStillNode(CommandNode):
    """Detect invariant or near-invariant codon sites with HyPhy B-STILL."""
    NODE_ID = 'hyphy_b_still'
    DISPLAY_NAME = 'HyPhy-B-STILL'
    REQUIRED_CONDA_PACKAGES = ['hyphy']
    CATEGORY = 'phylogeny'
    DESCRIPTION = 'Detect invariant or near-invariant codon sites with HyPhy B-STILL.'
    SEARCH_ALIASES = [BIONODULO_BUILTIN_ALIAS, 'HyPhy', 'B-STILL', 'Bayesian Significance Test of Invariant Low Likelihoods', 'FUBAR', 'invariant sites', 'purifying selection', 'phylogenetics']
    RETURN_TYPES = ('JSON', 'TEXT')
    RETURN_NAMES = ('b_still_output', 'b_still_md_report')
    REQUIRED_EXECUTABLES = ['hyphy']
    DOCUMENTATION_URL = 'https://github.com/veg/hyphy/blob/master/res/TemplateBatchFiles/SelectionAnalyses/B-STILL.bf'
    CITATION_DOIS = HYPHY_B_STILL_CITATION_DOIS
    CITATION_URLS = [f'{DOI_URL}{doi}' for doi in HYPHY_B_STILL_CITATION_DOIS]
    CITATION_TEXT = HYPHY_B_STILL_CITATION_TEXT
    VERSION = '2.5.96'
    SHELL = True
    GENETIC_CODES = HyPhyABSRELNode.GENETIC_CODES
    INPUT_EXTENSIONS = HyPhyABSRELNode.INPUT_EXTENSIONS
    KILL_ZERO_LENGTHS = HyPhyABSRELNode.KILL_ZERO_LENGTHS
    POSTERIOR_ESTIMATION_METHODS = ['Variational-Bayes', 'Metropolis-Hastings', 'Collapsed-Gibbs']

    @classmethod
    def _input_name(cls, inputs: dict[str, Any]) -> str:
        ext = str(inputs.get('input_ext', 'fasta')).strip().lstrip('.') or 'fasta'
        return f'input.{ext}'

    @classmethod
    def _yes_no(cls, value: Any) -> str:
        if isinstance(value, str):
            return 'Yes' if value.lower() in {'true', 'yes', '1', 'on', 'yes'} else 'No'
        return 'Yes' if bool(value) else 'No'

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> str:
        out = _out(inputs)
        input_name = cls._input_name(inputs)
        commands: list[str] = []
        if str(inputs.get('input_nhx', '')).strip():
            commands.append(_shell_join(['ln', '-s', str(inputs.get('input_nhx', '')), 'input.nhx']))
        commands.append(_shell_join(['ln', '-s', str(inputs.get('input_file', '')), input_name]))
        method = str(inputs.get('method', 'Variational-Bayes') or 'Variational-Bayes')
        cmd = ['hyphy', 'b-still', '--alignment', f'./{input_name}']
        if str(inputs.get('input_nhx', '')).strip():
            cmd.extend(['--tree', 'input.nhx'])
        cmd.extend(['--code', str(inputs.get('gencodeid', 'Universal') or 'Universal'), '--method', method])
        if method != 'Variational-Bayes':
            cmd.extend(['--chains', str(inputs.get('chains', 5)), '--chain-length', str(inputs.get('chain_length', 2000000)), '--burn-in', str(inputs.get('burn_in', 1000000)), '--samples', str(inputs.get('samples', 100))])
        cmd.extend(['--grid', str(inputs.get('grid', 20)), '--concentration_parameter', str(inputs.get('concentration_parameter', 0.5)), '--non-zero', cls._yes_no(inputs.get('non_zero', False)), '--ebf', str(inputs.get('ebf', 10.0)), '--radius-threshold', str(inputs.get('radius_threshold', 0.5)), '--kill-zero-lengths', str(inputs.get('kill_zero_lengths', 'Yes') or 'Yes'), '--output', f'{out}/b_still_output.json', '>', f'{out}/b_still_stdout.md'])
        commands.append(_shell_join(cmd))
        return ' && '.join(commands)

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        out = Path(output_dir) / cls.NODE_ID
        out.mkdir(parents=True, exist_ok=True)
        return [out / 'b_still_output.json', out / 'b_still_stdout.md']

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        if not str(inputs.get('input_file', '')).strip():
            return 'HyPhy-B-STILL alignment input is required'
        gencodeid = str(inputs.get('gencodeid', 'Universal') or 'Universal')
        if gencodeid not in cls.GENETIC_CODES:
            return f'Unsupported HyPhy genetic code: {gencodeid}'
        method = str(inputs.get('method', 'Variational-Bayes') or 'Variational-Bayes')
        if method not in cls.POSTERIOR_ESTIMATION_METHODS:
            return f'Unsupported HyPhy-B-STILL posterior estimation method: {method}'
        try:
            grid = int(inputs.get('grid', 20))
        except (TypeError, ValueError):
            return 'HyPhy-B-STILL grid points must be between 5 and 50'
        if grid < 5 or grid > 50:
            return 'HyPhy-B-STILL grid points must be between 5 and 50'
        try:
            concentration = float(inputs.get('concentration_parameter', 0.5))
        except (TypeError, ValueError):
            return 'HyPhy-B-STILL concentration parameter must be between 0.001 and 1'
        if concentration < 0.001 or concentration > 1:
            return 'HyPhy-B-STILL concentration parameter must be between 0.001 and 1'
        try:
            ebf = float(inputs.get('ebf', 10.0))
        except (TypeError, ValueError):
            return 'HyPhy-B-STILL EBF threshold must be non-negative'
        if ebf < 0:
            return 'HyPhy-B-STILL EBF threshold must be non-negative'
        if ebf > 10000:
            return 'HyPhy-B-STILL EBF threshold must be between 0 and 10000'
        try:
            radius_threshold = float(inputs.get('radius_threshold', 0.5))
        except (TypeError, ValueError):
            return 'HyPhy-B-STILL radius threshold must be between 0 and 10'
        if radius_threshold < 0 or radius_threshold > 10:
            return 'HyPhy-B-STILL radius threshold must be between 0 and 10'
        kill_zero_lengths = str(inputs.get('kill_zero_lengths', 'Yes') or 'Yes')
        if kill_zero_lengths not in cls.KILL_ZERO_LENGTHS:
            return f'Unsupported HyPhy-B-STILL zero-length branch handling: {kill_zero_lengths}'
        if method != 'Variational-Bayes':
            try:
                chains = int(inputs.get('chains', 5))
            except (TypeError, ValueError):
                return 'HyPhy-B-STILL chains must be between 2 and 20'
            if chains < 2 or chains > 20:
                return 'HyPhy-B-STILL chains must be between 2 and 20'
            try:
                chain_length = int(inputs.get('chain_length', 2000000))
            except (TypeError, ValueError):
                return 'HyPhy-B-STILL chain length must be between 500000 and 50000000'
            if chain_length < 500000 or chain_length > 50000000:
                return 'HyPhy-B-STILL chain length must be between 500000 and 50000000'
            try:
                burn_in = int(inputs.get('burn_in', 1000000))
            except (TypeError, ValueError):
                return 'HyPhy-B-STILL burn-in samples must be between 100000 and 1900000'
            if burn_in < 100000 or burn_in > 1900000:
                return 'HyPhy-B-STILL burn-in samples must be between 100000 and 1900000'
            try:
                samples = int(inputs.get('samples', 100))
            except (TypeError, ValueError):
                return 'HyPhy-B-STILL samples per chain must be between 50 and 1000000'
            if samples < 50 or samples > 1000000:
                return 'HyPhy-B-STILL samples per chain must be between 50 and 1000000'
        return True

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {'required': {'input_file': ('FASTA', {'description': 'Codon alignment in FASTA, compressed FASTA, or NEXUS format'})}, 'optional': {'input_nhx': ('FILE', {'default': '', 'description': 'Optional Newick/NHX phylogenetic tree'}), 'input_ext': ('STRING', {'default': 'fasta', 'options': cls.INPUT_EXTENSIONS, 'advanced': True}), 'gencodeid': ('STRING', {'default': 'Universal', 'options': cls.GENETIC_CODES, 'description': 'HyPhy genetic code for codon interpretation'}), 'method': ('STRING', {'default': 'Variational-Bayes', 'options': cls.POSTERIOR_ESTIMATION_METHODS, 'description': 'Posterior estimation method'}), 'chains': ('INT', {'default': 5, 'min': 2, 'max': 20, 'description': 'Number of MCMC chains', 'advanced': True}), 'chain_length': ('INT', {'default': 2000000, 'min': 500000, 'max': 50000000, 'description': 'Length of each MCMC chain', 'advanced': True}), 'burn_in': ('INT', {'default': 1000000, 'min': 100000, 'max': 1900000, 'description': 'Samples to use for burn-in', 'advanced': True}), 'samples': ('INT', {'default': 100, 'min': 50, 'max': 1000000, 'description': 'Samples to draw from each chain', 'advanced': True}), 'grid': ('INT', {'default': 20, 'min': 5, 'max': 50, 'description': 'Grid points used to approximate the posterior distribution'}), 'concentration_parameter': ('FLOAT', {'default': 0.5, 'min': 0.001, 'max': 1, 'description': 'Dirichlet prior concentration parameter'}), 'non_zero': ('BOOLEAN', {'default': False, 'description': 'Enforce non-zero synonymous rates on the grid'}), 'ebf': ('FLOAT', {'default': 10.0, 'min': 0, 'max': 10000, 'description': 'Empirical Bayes Factor threshold for proximal invariance'}), 'radius_threshold': ('FLOAT', {'default': 0.5, 'min': 0, 'max': 10, 'description': 'Expected substitution multiplier for near-zero selective regimes'}), 'kill_zero_lengths': ('STRING', {'default': 'Yes', 'options': cls.KILL_ZERO_LENGTHS, 'description': 'Zero-length branch handling', 'advanced': True})}, 'hidden': {'output': ('STRING', {})}}


class HyPhyBGMNode(CommandNode):
    """Detect coevolving sites with HyPhy Bayesian graphical models."""
    NODE_ID = 'hyphy_bgm'
    DISPLAY_NAME = 'HyPhy-BGM'
    REQUIRED_CONDA_PACKAGES = ['hyphy']
    CATEGORY = 'phylogeny'
    DESCRIPTION = 'Detect coevolving sites in sequence alignments with HyPhy Bayesian graphical models.'
    SEARCH_ALIASES = [BIONODULO_BUILTIN_ALIAS, 'HyPhy', 'BGM', 'Bayesian graphical model', 'Spidermonkey', 'coevolving sites', 'correlated substitutions', 'phylogenetics']
    RETURN_TYPES = ('JSON', 'TEXT')
    RETURN_NAMES = ('bgm_output', 'bgm_md_report')
    REQUIRED_EXECUTABLES = ['hyphy']
    DOCUMENTATION_URL = 'http://hyphy.org/methods/selection-methods/#BGM'
    CITATION_DOIS = HYPHY_BGM_CITATION_DOIS
    CITATION_URLS = [f'{DOI_URL}{doi}' for doi in HYPHY_BGM_CITATION_DOIS]
    CITATION_TEXT = HYPHY_BGM_CITATION_TEXT
    VERSION = '2.5.96'
    SHELL = True
    GENETIC_CODES = HyPhyABSRELNode.GENETIC_CODES
    INPUT_EXTENSIONS = HyPhyABSRELNode.INPUT_EXTENSIONS
    BRANCH_SELECTIONS = HyPhyABSRELNode.BRANCH_SELECTIONS
    DATATYPES = ['nucleotide', 'amino-acid', 'codon']
    AMINO_ACID_MODELS = ['LG', 'WAG', 'JTT', 'JC69', 'mtMet', 'mtVer', 'mtInv', 'gcpREV', 'HIVBm', 'HIVWm', 'GTR']

    @classmethod
    def _input_name(cls, inputs: dict[str, Any]) -> str:
        ext = str(inputs.get('input_ext', 'fasta')).strip().lstrip('.') or 'fasta'
        return f'input.{ext}'

    @classmethod
    def _branch_arg(cls, inputs: dict[str, Any]) -> str:
        branch_sel = str(inputs.get('branch_sel', 'All') or 'All')
        if branch_sel == 'specify':
            return str(inputs.get('branch_label', '')).strip()
        return branch_sel

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> str:
        out = _out(inputs)
        input_name = cls._input_name(inputs)
        commands: list[str] = []
        if str(inputs.get('input_nhx', '')).strip():
            commands.append(_shell_join(['ln', '-s', str(inputs.get('input_nhx', '')), 'input.nhx']))
        commands.append(_shell_join(['ln', '-s', str(inputs.get('input_file', '')), input_name]))
        datatype = str(inputs.get('datatype', 'codon') or 'codon')
        cmd = ['TOLERATE_NUMERICAL_ERRORS=1', 'hyphy', f"CPU={inputs.get('threads', 4)}", 'bgm', '--alignment', f'./{input_name}']
        if str(inputs.get('input_nhx', '')).strip():
            cmd.extend(['--tree', 'input.nhx'])
        cmd.extend(['--type', datatype])
        if datatype == 'codon':
            cmd.extend(['--code', str(inputs.get('gencodeid', 'Universal') or 'Universal')])
        if datatype == 'amino-acid':
            cmd.extend(['--baseline_model', str(inputs.get('baseline_model', 'LG') or 'LG')])
        cmd.extend(['--branches', cls._branch_arg(inputs), '--steps', str(inputs.get('chain_length', 100000)), '--burn-in', str(inputs.get('burn_in', 10000)), '--samples', str(inputs.get('samples', 100)), '--max-parents', str(inputs.get('parents', 1)), '--min-subs', str(inputs.get('min_subs', 1)), '--output', f'{out}/bgm_output.json', '>', f'{out}/bgm_stdout.md'])
        commands.append(_shell_join(cmd))
        return ' && '.join(commands)

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        out = Path(output_dir) / cls.NODE_ID
        out.mkdir(parents=True, exist_ok=True)
        return [out / 'bgm_output.json', out / 'bgm_stdout.md']

    @classmethod
    def _validate_int_range(cls, inputs: dict[str, Any], key: str, default: int, low: int, high: int, label: str) -> str | None:
        try:
            value = int(inputs.get(key, default))
        except (TypeError, ValueError):
            return f'HyPhy-BGM {label} must be between {low} and {high}'
        if value < low or value > high:
            return f'HyPhy-BGM {label} must be between {low} and {high}'
        return None

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        if not str(inputs.get('input_file', '')).strip():
            return 'HyPhy-BGM alignment input is required'
        datatype = str(inputs.get('datatype', 'codon') or 'codon')
        if datatype not in cls.DATATYPES:
            return f'Unsupported HyPhy-BGM data type: {datatype}'
        if datatype == 'codon':
            gencodeid = str(inputs.get('gencodeid', 'Universal') or 'Universal')
            if gencodeid not in cls.GENETIC_CODES:
                return f'Unsupported HyPhy genetic code: {gencodeid}'
        if datatype == 'amino-acid':
            baseline_model = str(inputs.get('baseline_model', 'LG') or 'LG')
            if baseline_model not in cls.AMINO_ACID_MODELS:
                return f'Unsupported HyPhy-BGM amino-acid substitution model: {baseline_model}'
        branch_sel = str(inputs.get('branch_sel', 'All') or 'All')
        if branch_sel not in cls.BRANCH_SELECTIONS:
            return f'Unsupported HyPhy-BGM branch selection: {branch_sel}'
        if branch_sel == 'specify' and (not str(inputs.get('branch_label', '')).strip()):
            return 'HyPhy-BGM custom branch selection requires a branch label'
        for key, default, low, high, label in [('chain_length', 100000, 0, 1000000000, 'chain length'), ('burn_in', 10000, 0, 1000000000, 'burn-in'), ('samples', 100, 1, 100000, 'samples'), ('parents', 1, 1, 3, 'maximum parents'), ('min_subs', 1, 1, 1000, 'minimum substitutions')]:
            message = cls._validate_int_range(inputs, key, default, low, high, label)
            if message:
                return message
        try:
            threads = int(inputs.get('threads', 4))
        except (TypeError, ValueError):
            return 'HyPhy-BGM threads must be a positive integer'
        if threads < 1:
            return 'HyPhy-BGM threads must be a positive integer'
        return True

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {'required': {'input_file': ('FASTA', {'description': 'Sequence alignment in FASTA, compressed FASTA, or NEXUS format'})}, 'optional': {'input_nhx': ('FILE', {'default': '', 'description': 'Optional Newick/NHX phylogenetic tree'}), 'input_ext': ('STRING', {'default': 'fasta', 'options': cls.INPUT_EXTENSIONS, 'advanced': True}), 'datatype': ('STRING', {'default': 'codon', 'options': cls.DATATYPES, 'description': 'Alignment data type'}), 'gencodeid': ('STRING', {'default': 'Universal', 'options': cls.GENETIC_CODES, 'description': 'HyPhy genetic code used for codon alignments'}), 'baseline_model': ('STRING', {'default': 'LG', 'options': cls.AMINO_ACID_MODELS, 'description': 'Amino-acid substitution model'}), 'branch_sel': ('STRING', {'default': 'All', 'options': cls.BRANCH_SELECTIONS, 'description': 'Branches to include in the coevolution analysis'}), 'branch_label': ('STRING', {'default': '', 'description': 'Custom branch label when branch selection is specify'}), 'chain_length': ('INT', {'default': 100000, 'min': 0, 'max': 1000000000, 'description': 'Length of MCMC chain'}), 'burn_in': ('INT', {'default': 10000, 'min': 0, 'max': 1000000000, 'description': 'MCMC burn-in steps'}), 'samples': ('INT', {'default': 100, 'min': 1, 'max': 100000, 'description': 'Samples to extract from the chain'}), 'parents': ('INT', {'default': 1, 'min': 1, 'max': 3, 'description': 'Maximum parents allowed per graph node'}), 'min_subs': ('INT', {'default': 1, 'min': 1, 'max': 1000, 'description': 'Minimum substitutions per site included in the analysis'}), 'threads': ('INT', {'default': 4, 'min': 1, 'max': 128})}, 'hidden': {'output': ('STRING', {})}}


class HyPhyFADENode(CommandNode):
    """Test protein alignments for directional selection with HyPhy FADE."""
    NODE_ID = 'hyphy_fade'
    DISPLAY_NAME = 'HyPhy-FADE'
    REQUIRED_CONDA_PACKAGES = ['hyphy']
    CATEGORY = 'phylogeny'
    DESCRIPTION = 'Test a protein alignment for directional selection with HyPhy FADE.'
    SEARCH_ALIASES = [BIONODULO_BUILTIN_ALIAS, 'HyPhy', 'FADE', 'FUBAR Approach to Directional Evolution', 'directional selection', 'protein alignment', 'amino acid substitution bias', 'empirical Bayes factor', 'phylogenetics']
    RETURN_TYPES = ('JSON', 'TEXT')
    RETURN_NAMES = ('fade_output', 'fade_md_report')
    REQUIRED_EXECUTABLES = ['hyphy']
    DOCUMENTATION_URL = 'http://hyphy.org/methods/selection-methods/#FADE'
    CITATION_DOIS = HYPHY_FADE_CITATION_DOIS
    CITATION_URLS = [f'{DOI_URL}{doi}' for doi in HYPHY_FADE_CITATION_DOIS]
    CITATION_TEXT = HYPHY_FADE_CITATION_TEXT
    VERSION = '2.5.96'
    SHELL = True
    INPUT_EXTENSIONS = HyPhyABSRELNode.INPUT_EXTENSIONS
    BRANCH_SELECTIONS = HyPhyABSRELNode.BRANCH_SELECTIONS
    AMINO_ACID_MODELS = HyPhyBGMNode.AMINO_ACID_MODELS
    POSTERIOR_ESTIMATION_METHODS = HyPhyBStillNode.POSTERIOR_ESTIMATION_METHODS

    @classmethod
    def _input_name(cls, inputs: dict[str, Any]) -> str:
        ext = str(inputs.get('input_ext', 'fasta')).strip().lstrip('.') or 'fasta'
        return f'input.{ext}'

    @classmethod
    def _branch_arg(cls, inputs: dict[str, Any]) -> str:
        branch_sel = str(inputs.get('branch_sel', 'All') or 'All')
        if branch_sel == 'specify':
            return str(inputs.get('branch_label', '')).strip()
        return branch_sel

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> str:
        out = _out(inputs)
        input_name = cls._input_name(inputs)
        commands: list[str] = []
        if str(inputs.get('input_nhx', '')).strip():
            commands.append(_shell_join(['ln', '-s', str(inputs.get('input_nhx', '')), 'input.nhx']))
        commands.append(_shell_join(['ln', '-s', str(inputs.get('input_file', '')), input_name]))
        method = str(inputs.get('method', 'Variational-Bayes') or 'Variational-Bayes')
        cmd = ['hyphy', 'fade', '--alignment', input_name]
        if str(inputs.get('input_nhx', '')).strip():
            cmd.extend(['--tree', 'input.nhx'])
        cmd.extend(['--branches', cls._branch_arg(inputs), '--model', str(inputs.get('model', 'GTR') or 'GTR'), '--method', method])
        if method != 'Variational-Bayes':
            cmd.extend(['--chains', str(inputs.get('chains', 5)), '--chain-length', str(inputs.get('chain_length', 2000000)), '--burn-in', str(inputs.get('burn_in', 1000000)), '--samples', str(inputs.get('samples', 100))])
        cmd.extend(['--grid', str(inputs.get('grid', 20)), '--concentration_parameter', str(inputs.get('concentration_parameter', 0.5)), '--output', f'{out}/fade_output.json', '>', f'{out}/fade_stdout.md'])
        commands.append(_shell_join(cmd))
        return ' && '.join(commands)

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        out = Path(output_dir) / cls.NODE_ID
        out.mkdir(parents=True, exist_ok=True)
        return [out / 'fade_output.json', out / 'fade_stdout.md']

    @staticmethod
    def _validate_int_range(value: Any, label: str, low: int, high: int) -> str | None:
        try:
            parsed = int(value)
        except (TypeError, ValueError):
            return f'HyPhy-FADE {label} must be between {low} and {high}'
        if parsed < low or parsed > high:
            return f'HyPhy-FADE {label} must be between {low} and {high}'
        return None

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        if not str(inputs.get('input_file', '')).strip():
            return 'HyPhy-FADE protein alignment input is required'
        input_ext = str(inputs.get('input_ext', 'fasta') or 'fasta').strip().lstrip('.')
        if input_ext not in cls.INPUT_EXTENSIONS:
            return f'Unsupported HyPhy-FADE input extension: {input_ext}'
        branch_sel = str(inputs.get('branch_sel', 'All') or 'All')
        if branch_sel not in cls.BRANCH_SELECTIONS:
            return f'Unsupported HyPhy-FADE branch selection: {branch_sel}'
        if branch_sel == 'specify' and (not str(inputs.get('branch_label', '')).strip()):
            return 'HyPhy-FADE custom branch selection requires a branch label'
        model = str(inputs.get('model', 'GTR') or 'GTR')
        if model not in cls.AMINO_ACID_MODELS:
            return f'Unsupported HyPhy-FADE amino-acid substitution model: {model}'
        method = str(inputs.get('method', 'Variational-Bayes') or 'Variational-Bayes')
        if method not in cls.POSTERIOR_ESTIMATION_METHODS:
            return f'Unsupported HyPhy-FADE posterior estimation method: {method}'
        message = cls._validate_int_range(inputs.get('grid', 20), 'grid points', 5, 50)
        if message:
            return message
        try:
            concentration = float(inputs.get('concentration_parameter', 0.5))
        except (TypeError, ValueError):
            return 'HyPhy-FADE concentration parameter must be between 0.001 and 1'
        if concentration < 0.001 or concentration > 1:
            return 'HyPhy-FADE concentration parameter must be between 0.001 and 1'
        if method != 'Variational-Bayes':
            for key, default, label, low, high in [('chains', 5, 'chains', 2, 20), ('chain_length', 2000000, 'chain length', 500000, 50000000), ('burn_in', 1000000, 'burn-in samples', 100000, 1900000), ('samples', 100, 'samples per chain', 50, 1000000)]:
                message = cls._validate_int_range(inputs.get(key, default), label, low, high)
                if message:
                    return message
        return True

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {'required': {'input_file': ('FASTA', {'description': 'Protein alignment in FASTA, compressed FASTA, or NEXUS format'})}, 'optional': {'input_nhx': ('FILE', {'default': '', 'description': 'Optional rooted Newick/NHX phylogenetic tree'}), 'input_ext': ('STRING', {'default': 'fasta', 'options': cls.INPUT_EXTENSIONS, 'advanced': True}), 'branch_sel': ('STRING', {'default': 'All', 'options': cls.BRANCH_SELECTIONS, 'description': 'Branches to test for directional selection'}), 'branch_label': ('STRING', {'default': '', 'description': 'Custom branch label when branch selection is specify'}), 'model': ('STRING', {'default': 'GTR', 'options': cls.AMINO_ACID_MODELS, 'description': 'Baseline amino-acid substitution model'}), 'method': ('STRING', {'default': 'Variational-Bayes', 'options': cls.POSTERIOR_ESTIMATION_METHODS, 'description': 'Posterior estimation method'}), 'grid': ('INT', {'default': 20, 'min': 5, 'max': 50, 'description': 'Grid points per dimension'}), 'concentration_parameter': ('FLOAT', {'default': 0.5, 'min': 0.001, 'max': 1, 'description': 'Dirichlet prior concentration parameter'}), 'chains': ('INT', {'default': 5, 'min': 2, 'max': 20, 'description': 'Number of MCMC chains', 'advanced': True}), 'chain_length': ('INT', {'default': 2000000, 'min': 500000, 'max': 50000000, 'description': 'Length of each MCMC chain', 'advanced': True}), 'burn_in': ('INT', {'default': 1000000, 'min': 100000, 'max': 1900000, 'description': 'Samples to use for burn-in', 'advanced': True}), 'samples': ('INT', {'default': 100, 'min': 50, 'max': 1000000, 'description': 'Samples to draw from each chain', 'advanced': True})}, 'hidden': {'output': ('STRING', {})}}


class HyPhyFELNode(CommandNode):
    """Detect pervasive site-level selection with HyPhy FEL."""
    NODE_ID = 'hyphy_fel'
    DISPLAY_NAME = 'HyPhy-FEL'
    REQUIRED_CONDA_PACKAGES = ['hyphy']
    CATEGORY = 'phylogeny'
    DESCRIPTION = 'Detect pervasive site-level selection with HyPhy Fixed Effects Likelihood.'
    SEARCH_ALIASES = [BIONODULO_BUILTIN_ALIAS, 'HyPhy', 'FEL', 'Fixed Effects Likelihood', 'pervasive selection', 'site-level selection', 'diversifying selection', 'purifying selection', 'synonymous rate variation', 'multiple nucleotide substitutions', 'phylogenetics']
    RETURN_TYPES = ('JSON', 'TEXT')
    RETURN_NAMES = ('fel_output', 'fel_md_report')
    REQUIRED_EXECUTABLES = ['HYPHYMPI', 'mpirun']
    DOCUMENTATION_URL = 'http://hyphy.org/methods/selection-methods/#FEL'
    CITATION_DOIS = HYPHY_FEL_CITATION_DOIS
    CITATION_URLS = [f'{DOI_URL}{doi}' for doi in HYPHY_FEL_CITATION_DOIS]
    CITATION_TEXT = HYPHY_FEL_CITATION_TEXT
    VERSION = '2.5.96'
    SHELL = True
    GENETIC_CODES = HyPhyABSRELNode.GENETIC_CODES
    INPUT_EXTENSIONS = HyPhyABSRELNode.INPUT_EXTENSIONS
    BRANCH_SELECTIONS = HyPhyABSRELNode.BRANCH_SELECTIONS
    MULTIPLE_HITS = HyPhyABSRELNode.MULTIPLE_HITS
    SITE_MULTIHIT = ['Estimate', 'No']
    SRV_OPTIONS = ['Yes', 'No']
    PRECISION_OPTIONS = ['standard', 'reduced']
    KILL_ZERO_LENGTHS = HyPhyABSRELNode.KILL_ZERO_LENGTHS

    @classmethod
    def _input_name(cls, inputs: dict[str, Any]) -> str:
        ext = str(inputs.get('input_ext', 'fasta')).strip().lstrip('.') or 'fasta'
        return f'input.{ext}'

    @classmethod
    def _branch_arg(cls, inputs: dict[str, Any]) -> str:
        branch_sel = str(inputs.get('branch_sel', 'All') or 'All')
        if branch_sel == 'specify':
            return str(inputs.get('branch_label', '')).strip()
        return branch_sel

    @staticmethod
    def _bool_value(value: Any) -> bool:
        if isinstance(value, str):
            return value.lower() in {'true', 'yes', '1', 'on'}
        return bool(value)

    @staticmethod
    def _mpirun_prefix(threads: Any) -> str:
        return f'${{GALAXY_MPIRUN:-mpirun --allow-run-as-root --oversubscribe -mca orte_tmpdir_base "${{TMPDIR:-.}}" -np {threads}}}'

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> str:
        out = _out(inputs)
        input_name = cls._input_name(inputs)
        commands: list[str] = []
        if str(inputs.get('input_nhx', '')).strip():
            commands.append(_shell_join(['ln', '-s', str(inputs.get('input_nhx', '')), 'input.nhx']))
        commands.append(_shell_join(['ln', '-s', str(inputs.get('input_file', '')), input_name]))
        cmd = ['--alignment', f'./{input_name}']
        if str(inputs.get('input_nhx', '')).strip():
            cmd.extend(['--tree', 'input.nhx'])
        cmd.extend(['--code', str(inputs.get('gencodeid', 'Universal') or 'Universal'), '--multiple-hits', str(inputs.get('multiple_hits', 'None') or 'None'), '--branches', cls._branch_arg(inputs), '--srv', str(inputs.get('srv', 'Yes') or 'Yes'), '--pvalue', str(inputs.get('pvalue', 0.1))])
        resample = inputs.get('resample', 0)
        if str(resample) not in {'', '0'}:
            cmd.extend(['--resample', str(resample)])
        if cls._bool_value(inputs.get('restrict_sites', False)):
            cmd.extend(['--limit-to-sites', str(inputs.get('limit_to_sites', 'null') or 'null'), '--save-lf-for-sites', str(inputs.get('save_lf_for_sites', 'null') or 'null')])
        cmd.extend(['--precision', str(inputs.get('precision', 'standard') or 'standard')])
        if cls._bool_value(inputs.get('ci', False)):
            cmd.extend(['--ci', 'Yes'])
        cmd.extend(['--output', f'{out}/fel_output.json'])
        multiple_hits = str(inputs.get('multiple_hits', 'None') or 'None')
        if multiple_hits != 'None':
            cmd.extend(['--site-multihit', str(inputs.get('site_multihit', 'Estimate') or 'Estimate')])
        cmd.extend(['--kill-zero-lengths', str(inputs.get('kill_zero_lengths', 'Yes') or 'Yes')])
        if cls._bool_value(inputs.get('full_model', True)):
            cmd.extend(['--full-model', 'Yes'])
        cmd.extend(['>', f'{out}/fel_stdout.md'])
        commands.append(f"{cls._mpirun_prefix(inputs.get('threads', 4))} HYPHYMPI fel {_shell_join(cmd)}")
        return ' && '.join(commands)

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        out = Path(output_dir) / cls.NODE_ID
        out.mkdir(parents=True, exist_ok=True)
        return [out / 'fel_output.json', out / 'fel_stdout.md']

    @staticmethod
    def _validate_unit_float(value: Any, message: str) -> str | None:
        try:
            parsed = float(value)
        except (TypeError, ValueError):
            return message
        return message if parsed < 0 or parsed > 1 else None

    @staticmethod
    def _validate_int_range(value: Any, message: str, low: int, high: int) -> str | None:
        try:
            parsed = int(value)
        except (TypeError, ValueError):
            return message
        return message if parsed < low or parsed > high else None

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        if not str(inputs.get('input_file', '')).strip():
            return 'HyPhy-FEL alignment input is required'
        input_ext = str(inputs.get('input_ext', 'fasta') or 'fasta').strip().lstrip('.')
        if input_ext not in cls.INPUT_EXTENSIONS:
            return f'Unsupported HyPhy-FEL input extension: {input_ext}'
        gencodeid = str(inputs.get('gencodeid', 'Universal') or 'Universal')
        if gencodeid not in cls.GENETIC_CODES:
            return f'Unsupported HyPhy genetic code: {gencodeid}'
        branch_sel = str(inputs.get('branch_sel', 'All') or 'All')
        if branch_sel not in cls.BRANCH_SELECTIONS:
            return f'Unsupported HyPhy-FEL branch selection: {branch_sel}'
        if branch_sel == 'specify' and (not str(inputs.get('branch_label', '')).strip()):
            return 'HyPhy-FEL custom branch selection requires a branch label'
        multiple_hits = str(inputs.get('multiple_hits', 'None') or 'None')
        if multiple_hits not in cls.MULTIPLE_HITS:
            return f'Unsupported HyPhy-FEL multiple-hits mode: {multiple_hits}'
        if multiple_hits != 'None':
            site_multihit = str(inputs.get('site_multihit', 'Estimate') or 'Estimate')
            if site_multihit not in cls.SITE_MULTIHIT:
                return f'Unsupported HyPhy-FEL site-multihit mode: {site_multihit}'
        srv = str(inputs.get('srv', 'Yes') or 'Yes')
        if srv not in cls.SRV_OPTIONS:
            return f'Unsupported HyPhy-FEL synonymous rate variation setting: {srv}'
        message = cls._validate_unit_float(inputs.get('pvalue', 0.1), 'HyPhy-FEL p-value threshold must be between 0 and 1')
        if message:
            return message
        message = cls._validate_int_range(inputs.get('resample', 0), 'HyPhy-FEL resampling replicates must be between 0 and 1000', 0, 1000)
        if message:
            return message
        precision = str(inputs.get('precision', 'standard') or 'standard')
        if precision not in cls.PRECISION_OPTIONS:
            return f'Unsupported HyPhy-FEL optimization precision: {precision}'
        kill_zero_lengths = str(inputs.get('kill_zero_lengths', 'Yes') or 'Yes')
        if kill_zero_lengths not in cls.KILL_ZERO_LENGTHS:
            return f'Unsupported HyPhy-FEL zero-length branch handling: {kill_zero_lengths}'
        try:
            threads = int(inputs.get('threads', 4))
        except (TypeError, ValueError):
            return 'HyPhy-FEL threads must be a positive integer'
        if threads < 1:
            return 'HyPhy-FEL threads must be a positive integer'
        return True

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {'required': {'input_file': ('FASTA', {'description': 'Codon alignment in FASTA, compressed FASTA, or NEXUS format'})}, 'optional': {'input_nhx': ('FILE', {'default': '', 'description': 'Optional Newick/NHX phylogenetic tree'}), 'input_ext': ('STRING', {'default': 'fasta', 'options': cls.INPUT_EXTENSIONS, 'advanced': True}), 'gencodeid': ('STRING', {'default': 'Universal', 'options': cls.GENETIC_CODES, 'description': 'HyPhy genetic code for codon interpretation'}), 'branch_sel': ('STRING', {'default': 'All', 'options': cls.BRANCH_SELECTIONS, 'description': 'Branches to test for pervasive selection'}), 'branch_label': ('STRING', {'default': '', 'description': 'Custom branch label when branch selection is specify'}), 'multiple_hits': ('STRING', {'default': 'None', 'options': cls.MULTIPLE_HITS, 'description': 'Multiple-hit correction mode', 'advanced': True}), 'site_multihit': ('STRING', {'default': 'Estimate', 'options': cls.SITE_MULTIHIT, 'description': 'Estimate multiple-hit rates for each site when multiple hits are enabled', 'advanced': True}), 'srv': ('STRING', {'default': 'Yes', 'options': cls.SRV_OPTIONS, 'description': 'Include synonymous rate variation'}), 'pvalue': ('FLOAT', {'default': 0.1, 'min': 0, 'max': 1, 'description': 'P-value threshold for site tests'}), 'ci': ('BOOLEAN', {'default': False, 'description': 'Compute profile likelihood confidence intervals for each variable site', 'advanced': True}), 'resample': ('INT', {'default': 0, 'min': 0, 'max': 1000, 'description': 'Parametric bootstrap resampling replicates per site', 'advanced': True}), 'restrict_sites': ('BOOLEAN', {'default': False, 'description': 'Restrict FEL analysis to a subset of sites'}), 'limit_to_sites': ('STRING', {'default': 'null', 'description': 'Comma-separated 1-based site indices to analyze'}), 'save_lf_for_sites': ('STRING', {'default': 'null', 'description': 'Comma-separated sites for likelihood-function snapshots'}), 'precision': ('STRING', {'default': 'standard', 'options': cls.PRECISION_OPTIONS, 'description': 'Optimization precision for preliminary fits', 'advanced': True}), 'kill_zero_lengths': ('STRING', {'default': 'Yes', 'options': cls.KILL_ZERO_LENGTHS, 'description': 'Zero-length branch handling', 'advanced': True}), 'full_model': ('BOOLEAN', {'default': True, 'description': 'Re-optimize branch lengths under the full codon model', 'advanced': True}), 'threads': ('INT', {'default': 4, 'min': 1, 'max': 128})}, 'hidden': {'output': ('STRING', {})}}


class HyPhyFUBARNode(CommandNode):
    """Detect pervasive site-level selection with HyPhy FUBAR."""
    NODE_ID = 'hyphy_fubar'
    DISPLAY_NAME = 'HyPhy-FUBAR'
    REQUIRED_CONDA_PACKAGES = ['hyphy']
    CATEGORY = 'phylogeny'
    DESCRIPTION = 'Detect pervasive site-level selection with HyPhy FUBAR.'
    SEARCH_ALIASES = [BIONODULO_BUILTIN_ALIAS, 'HyPhy', 'FUBAR', 'Fast Unconstrained Bayesian AppRoximation', 'pervasive selection', 'site-level selection', 'diversifying selection', 'purifying selection', 'posterior probability', 'empirical Bayes factor', 'phylogenetics']
    RETURN_TYPES = ('JSON', 'TEXT')
    RETURN_NAMES = ('fubar_output', 'fubar_md_report')
    REQUIRED_EXECUTABLES = ['hyphy']
    DOCUMENTATION_URL = 'http://hyphy.org/methods/selection-methods/#FUBAR'
    CITATION_DOIS = HYPHY_FUBAR_CITATION_DOIS
    CITATION_URLS = [f'{DOI_URL}{doi}' for doi in HYPHY_FUBAR_CITATION_DOIS]
    CITATION_TEXT = HYPHY_FUBAR_CITATION_TEXT
    VERSION = '2.5.96'
    SHELL = True
    GENETIC_CODES = HyPhyABSRELNode.GENETIC_CODES
    INPUT_EXTENSIONS = HyPhyABSRELNode.INPUT_EXTENSIONS
    POSTERIOR_ESTIMATION_METHODS = HyPhyBStillNode.POSTERIOR_ESTIMATION_METHODS
    KILL_ZERO_LENGTHS = HyPhyABSRELNode.KILL_ZERO_LENGTHS

    @classmethod
    def _input_name(cls, inputs: dict[str, Any]) -> str:
        ext = str(inputs.get('input_ext', 'fasta')).strip().lstrip('.') or 'fasta'
        return f'input.{ext}'

    @staticmethod
    def _yes_no(value: Any) -> str:
        if isinstance(value, str):
            return 'Yes' if value.lower() in {'true', 'yes', '1', 'on', 'yes'} else 'No'
        return 'Yes' if bool(value) else 'No'

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> str:
        out = _out(inputs)
        input_name = cls._input_name(inputs)
        commands: list[str] = []
        if str(inputs.get('input_nhx', '')).strip():
            commands.append(_shell_join(['ln', '-s', str(inputs.get('input_nhx', '')), 'input.nhx']))
        commands.append(_shell_join(['ln', '-s', str(inputs.get('input_file', '')), input_name]))
        commands.append(_shell_join(['ln', '-s', f'{out}/fubar_output.json', f'{input_name}.FUBAR.json']))
        method = str(inputs.get('method', 'Variational-Bayes') or 'Variational-Bayes')
        cmd = ['hyphy', 'fubar', '--alignment', f'./{input_name}']
        if str(inputs.get('input_nhx', '')).strip():
            cmd.extend(['--tree', 'input.nhx'])
        cmd.extend(['--code', str(inputs.get('gencodeid', 'Universal') or 'Universal'), '--method', method])
        if method != 'Variational-Bayes':
            cmd.extend(['--chains', str(inputs.get('chains', 5)), '--chain-length', str(inputs.get('chain_length', 2000000)), '--burn-in', str(inputs.get('burn_in', 1000000)), '--samples', str(inputs.get('samples', 100))])
        cmd.extend(['--grid', str(inputs.get('grid', 20)), '--concentration_parameter', str(inputs.get('concentration_parameter', 0.5)), '--non-zero', cls._yes_no(inputs.get('non_zero', False)), '--kill-zero-lengths', str(inputs.get('kill_zero_lengths', 'Yes') or 'Yes'), '>', f'{out}/fubar_stdout.md'])
        commands.append(_shell_join(cmd))
        return ' && '.join(commands)

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        out = Path(output_dir) / cls.NODE_ID
        out.mkdir(parents=True, exist_ok=True)
        return [out / 'fubar_output.json', out / 'fubar_stdout.md']

    @staticmethod
    def _validate_int_range(value: Any, label: str, low: int, high: int) -> str | None:
        try:
            parsed = int(value)
        except (TypeError, ValueError):
            return f'HyPhy-FUBAR {label} must be between {low} and {high}'
        if parsed < low or parsed > high:
            return f'HyPhy-FUBAR {label} must be between {low} and {high}'
        return None

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        if not str(inputs.get('input_file', '')).strip():
            return 'HyPhy-FUBAR alignment input is required'
        input_ext = str(inputs.get('input_ext', 'fasta') or 'fasta').strip().lstrip('.')
        if input_ext not in cls.INPUT_EXTENSIONS:
            return f'Unsupported HyPhy-FUBAR input extension: {input_ext}'
        gencodeid = str(inputs.get('gencodeid', 'Universal') or 'Universal')
        if gencodeid not in cls.GENETIC_CODES:
            return f'Unsupported HyPhy genetic code: {gencodeid}'
        method = str(inputs.get('method', 'Variational-Bayes') or 'Variational-Bayes')
        if method not in cls.POSTERIOR_ESTIMATION_METHODS:
            return f'Unsupported HyPhy-FUBAR posterior estimation method: {method}'
        message = cls._validate_int_range(inputs.get('grid', 20), 'grid points', 5, 50)
        if message:
            return message
        try:
            concentration = float(inputs.get('concentration_parameter', 0.5))
        except (TypeError, ValueError):
            return 'HyPhy-FUBAR concentration parameter must be between 0.001 and 1'
        if concentration < 0.001 or concentration > 1:
            return 'HyPhy-FUBAR concentration parameter must be between 0.001 and 1'
        kill_zero_lengths = str(inputs.get('kill_zero_lengths', 'Yes') or 'Yes')
        if kill_zero_lengths not in cls.KILL_ZERO_LENGTHS:
            return f'Unsupported HyPhy-FUBAR zero-length branch handling: {kill_zero_lengths}'
        if method != 'Variational-Bayes':
            for key, default, label, low, high in [('chains', 5, 'chains', 2, 20), ('chain_length', 2000000, 'chain length', 500000, 50000000), ('burn_in', 1000000, 'burn-in samples', 100000, 1900000), ('samples', 100, 'samples per chain', 50, 1000000)]:
                message = cls._validate_int_range(inputs.get(key, default), label, low, high)
                if message:
                    return message
        return True

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {'required': {'input_file': ('FASTA', {'description': 'Codon alignment in FASTA, compressed FASTA, or NEXUS format'})}, 'optional': {'input_nhx': ('FILE', {'default': '', 'description': 'Optional Newick/NHX phylogenetic tree'}), 'input_ext': ('STRING', {'default': 'fasta', 'options': cls.INPUT_EXTENSIONS, 'advanced': True}), 'gencodeid': ('STRING', {'default': 'Universal', 'options': cls.GENETIC_CODES, 'description': 'HyPhy genetic code for codon interpretation'}), 'method': ('STRING', {'default': 'Variational-Bayes', 'options': cls.POSTERIOR_ESTIMATION_METHODS, 'description': 'Posterior estimation method'}), 'grid': ('INT', {'default': 20, 'min': 5, 'max': 50, 'description': 'Grid points per dimension'}), 'concentration_parameter': ('FLOAT', {'default': 0.5, 'min': 0.001, 'max': 1, 'description': 'Dirichlet prior concentration parameter'}), 'non_zero': ('BOOLEAN', {'default': False, 'description': 'Enforce non-zero synonymous rates on the grid'}), 'chains': ('INT', {'default': 5, 'min': 2, 'max': 20, 'description': 'Number of MCMC chains', 'advanced': True}), 'chain_length': ('INT', {'default': 2000000, 'min': 500000, 'max': 50000000, 'description': 'Length of each MCMC chain', 'advanced': True}), 'burn_in': ('INT', {'default': 1000000, 'min': 100000, 'max': 1900000, 'description': 'Samples to use for burn-in', 'advanced': True}), 'samples': ('INT', {'default': 100, 'min': 50, 'max': 1000000, 'description': 'Samples to draw from each chain', 'advanced': True}), 'kill_zero_lengths': ('STRING', {'default': 'Yes', 'options': cls.KILL_ZERO_LENGTHS, 'description': 'Zero-length branch handling', 'advanced': True})}, 'hidden': {'output': ('STRING', {})}}


class HyPhyGARDNode(CommandNode):
    """Detect recombination breakpoints with HyPhy GARD."""
    NODE_ID = 'hyphy_gard'
    DISPLAY_NAME = 'HyPhy-GARD'
    REQUIRED_CONDA_PACKAGES = ['hyphy']
    CATEGORY = 'phylogeny'
    DESCRIPTION = 'Detect recombination breakpoints with HyPhy Genetic Algorithm for Recombination Detection.'
    SEARCH_ALIASES = [BIONODULO_BUILTIN_ALIAS, 'HyPhy', 'GARD', 'Genetic Algorithm for Recombination Detection', 'recombination detection', 'breakpoints', 'phylogenetic incongruence', 'partitioned alignment', 'site-to-site rate variation', 'phylogenetics']
    RETURN_TYPES = ('ALIGNMENT', 'JSON', 'TEXT')
    RETURN_NAMES = ('gard_output', 'gard_output_json', 'gard_md_report')
    REQUIRED_EXECUTABLES = ['HYPHYMPI', 'mpirun']
    DOCUMENTATION_URL = 'https://veg.github.io/hyphy-site/methods/gard/'
    CITATION_DOIS = HYPHY_GARD_CITATION_DOIS
    CITATION_URLS = [f'{DOI_URL}{doi}' for doi in HYPHY_GARD_CITATION_DOIS]
    CITATION_TEXT = HYPHY_GARD_CITATION_TEXT
    VERSION = '2.5.96'
    SHELL = True
    GENETIC_CODES = HyPhyABSRELNode.GENETIC_CODES
    INPUT_EXTENSIONS = HyPhyABSRELNode.INPUT_EXTENSIONS
    DATATYPES = ['nucleotide', 'amino-acid', 'codon']
    AMINO_ACID_MODELS = HyPhyBGMNode.AMINO_ACID_MODELS
    RATE_VARIATION = ['', 'GDD', 'Gamma']
    RUN_MODES = ['Normal', 'Faster']

    @classmethod
    def _input_name(cls, inputs: dict[str, Any]) -> str:
        ext = str(inputs.get('input_ext', 'fasta')).strip().lstrip('.') or 'fasta'
        return f'input.{ext}'

    @staticmethod
    def _mpirun_prefix(threads: Any) -> str:
        return f'${{GALAXY_MPIRUN:-mpirun --allow-run-as-root --oversubscribe -mca orte_tmpdir_base "${{TMPDIR:-.}}" -np {threads}}}'

    @staticmethod
    def _validate_int_range(value: Any, message: str, low: int, high: int) -> str | None:
        try:
            parsed = int(value)
        except (TypeError, ValueError):
            return message
        return message if parsed < low or parsed > high else None

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> str:
        out = _out(inputs)
        input_name = cls._input_name(inputs)
        commands = [_shell_join(['ln', '-s', str(inputs.get('input_file', '')), input_name])]
        datatype = str(inputs.get('datatype', 'nucleotide') or 'nucleotide')
        cmd = ['--alignment', input_name, '--type', datatype]
        if datatype == 'codon':
            cmd.extend(['--code', str(inputs.get('gencodeid', 'Universal') or 'Universal')])
        if datatype == 'amino-acid':
            cmd.extend(['--model', str(inputs.get('model', 'GTR') or 'GTR')])
        rate = str(inputs.get('rate', '') or '')
        if rate:
            cmd.extend(['--rv', rate, '--rate-classes', str(inputs.get('rate_classes', 2))])
        cmd.extend(['--max-breakpoints', str(inputs.get('max_breakpoints', 10000)), '--mode', str(inputs.get('mode', 'Normal') or 'Normal')])
        command = f"""{cls._mpirun_prefix(inputs.get('threads', 4))} HYPHYMPI gard {_shell_join(cmd)} ENV="TOLERATE_NUMERICAL_ERRORS=1;" --output {_shell_join([f'{out}/gard_output.json'])} --output-lf {_shell_join([f'{out}/gard_output.nex'])} > {_shell_join([f'{out}/gard_stdout.md'])}"""
        commands.append(command)
        return ' && '.join(commands)

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        out = Path(output_dir) / cls.NODE_ID
        out.mkdir(parents=True, exist_ok=True)
        return [out / 'gard_output.nex', out / 'gard_output.json', out / 'gard_stdout.md']

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        if not str(inputs.get('input_file', '')).strip():
            return 'HyPhy-GARD alignment input is required'
        input_ext = str(inputs.get('input_ext', 'fasta') or 'fasta').strip().lstrip('.')
        if input_ext not in cls.INPUT_EXTENSIONS:
            return f'Unsupported HyPhy-GARD input extension: {input_ext}'
        datatype = str(inputs.get('datatype', 'nucleotide') or 'nucleotide')
        if datatype not in cls.DATATYPES:
            return f'Unsupported HyPhy-GARD data type: {datatype}'
        if datatype == 'amino-acid':
            model = str(inputs.get('model', 'GTR') or 'GTR')
            if model not in cls.AMINO_ACID_MODELS:
                return f'Unsupported HyPhy-GARD amino-acid substitution model: {model}'
        if datatype == 'codon':
            gencodeid = str(inputs.get('gencodeid', 'Universal') or 'Universal')
            if gencodeid not in cls.GENETIC_CODES:
                return f'Unsupported HyPhy genetic code: {gencodeid}'
        rate = str(inputs.get('rate', '') or '')
        if rate not in cls.RATE_VARIATION:
            return f'Unsupported HyPhy-GARD rate variation setting: {rate}'
        if rate:
            message = cls._validate_int_range(inputs.get('rate_classes', 2), 'HyPhy-GARD rate classes must be between 2 and 6', 2, 6)
            if message:
                return message
        message = cls._validate_int_range(inputs.get('max_breakpoints', 10000), 'HyPhy-GARD maximum breakpoints must be between 1 and 10000', 1, 10000)
        if message:
            return message
        mode = str(inputs.get('mode', 'Normal') or 'Normal')
        if mode not in cls.RUN_MODES:
            return f'Unsupported HyPhy-GARD run mode: {mode}'
        try:
            threads = int(inputs.get('threads', 4))
        except (TypeError, ValueError):
            return 'HyPhy-GARD threads must be a positive integer'
        if threads < 1:
            return 'HyPhy-GARD threads must be a positive integer'
        return True

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {'required': {'input_file': ('FASTA', {'description': 'Sequence alignment in FASTA, compressed FASTA, or NEXUS format'})}, 'optional': {'input_ext': ('STRING', {'default': 'fasta', 'options': cls.INPUT_EXTENSIONS, 'advanced': True}), 'datatype': ('STRING', {'default': 'nucleotide', 'options': cls.DATATYPES, 'description': 'Alignment data type'}), 'model': ('STRING', {'default': 'GTR', 'options': cls.AMINO_ACID_MODELS, 'description': 'Amino-acid substitution model used for protein alignments'}), 'gencodeid': ('STRING', {'default': 'Universal', 'options': cls.GENETIC_CODES, 'description': 'HyPhy genetic code used for codon alignments'}), 'rate': ('STRING', {'default': '', 'options': cls.RATE_VARIATION, 'description': 'Site-to-site rate variation model'}), 'rate_classes': ('INT', {'default': 2, 'min': 2, 'max': 6, 'description': 'Discrete rate classes for GDD or Gamma'}), 'max_breakpoints': ('INT', {'default': 10000, 'min': 1, 'max': 10000, 'description': 'Maximum number of breakpoints to consider', 'advanced': True}), 'mode': ('STRING', {'default': 'Normal', 'options': cls.RUN_MODES, 'description': 'Run mode for optimization and convergence settings', 'advanced': True}), 'threads': ('INT', {'default': 4, 'min': 1, 'max': 128})}, 'hidden': {'output': ('STRING', {})}}


class HyPhyInferStasisClustersNode(CommandNode):
    """Identify regional footprints of extreme purifying selection from B-STILL results."""
    NODE_ID = 'hyphy_infer_stasis_clusters'
    DISPLAY_NAME = 'HyPhy-Infer Stasis Clusters'
    REQUIRED_CONDA_PACKAGES = ['python', 'numpy', 'scipy']
    CATEGORY = 'phylogeny'
    DESCRIPTION = 'Identify regional footprints of extreme purifying selection from B-STILL results.'
    SEARCH_ALIASES = [BIONODULO_BUILTIN_ALIAS, 'HyPhy', 'B-STILL', 'Infer Stasis Clusters', 'stasis clusters', 'purifying selection', 'Empirical Bayes Factor', 'hypergeometric scan statistic', 'family-wise error rate', 'protein domains']
    RETURN_TYPES = ('JSON', 'TEXT')
    RETURN_NAMES = ('output_json', 'output_log')
    REQUIRED_EXECUTABLES = ['python3']
    DOCUMENTATION_URL = 'https://github.com/galaxyproject/tools-iuc/tree/main/tools/hyphy'
    CITATION_DOIS = [HYPHY_CITATION_DOI]
    CITATION_URLS = [f'{DOI_URL}{HYPHY_CITATION_DOI}']
    CITATION_TEXT = HYPHY_CITATION_TEXT
    VERSION = '2.5.96'
    SHELL = True

    @staticmethod
    def _default_script_path() -> str:
        return str(Path(__file__).resolve().parents[1] / 'scripts' / 'infer_stasis_clusters.py')

    @classmethod
    def _script_path(cls, inputs: dict[str, Any]) -> str:
        return str(inputs.get('script_path') or cls._default_script_path())

    @staticmethod
    def _validate_float_range(value: Any, message: str, low: float, high: float) -> str | None:
        try:
            parsed = float(value)
        except (TypeError, ValueError):
            return message
        return message if parsed < low or parsed > high else None

    @staticmethod
    def _validate_int_range(value: Any, message: str, low: int, high: int) -> str | None:
        try:
            parsed = int(value)
        except (TypeError, ValueError):
            return message
        return message if parsed < low or parsed > high else None

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> str:
        out = _out(inputs)
        cmd = ['python3', cls._script_path(inputs), str(inputs.get('input_json', '')), '--ebf', str(inputs.get('ebf', 10.0)), '--permutations', str(inputs.get('permutations', 10000)), '--alpha', str(inputs.get('alpha', 0.05)), '--max-cluster', str(inputs.get('max_cluster', 30)), '--merge', str(inputs.get('merge', 15)), '--output', f'{out}/output_json.json', '>', f'{out}/output_log.txt']
        return _shell_join(cmd)

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        out = Path(output_dir) / cls.NODE_ID
        out.mkdir(parents=True, exist_ok=True)
        return [out / 'output_json.json', out / 'output_log.txt']

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        if not str(inputs.get('input_json', '')).strip():
            return 'HyPhy-Infer Stasis Clusters B-STILL JSON input is required'
        message = cls._validate_float_range(inputs.get('ebf', 10.0), 'HyPhy-Infer Stasis Clusters EBF threshold must be between 0 and 10000', 0, 10000)
        if message:
            return message
        message = cls._validate_int_range(inputs.get('permutations', 10000), 'HyPhy-Infer Stasis Clusters permutations must be between 100 and 100000', 100, 100000)
        if message:
            return message
        message = cls._validate_float_range(inputs.get('alpha', 0.05), 'HyPhy-Infer Stasis Clusters alpha must be between 0.001 and 0.5', 0.001, 0.5)
        if message:
            return message
        message = cls._validate_int_range(inputs.get('max_cluster', 30), 'HyPhy-Infer Stasis Clusters maximum cluster size must be between 3 and 100', 3, 100)
        if message:
            return message
        message = cls._validate_int_range(inputs.get('merge', 15), 'HyPhy-Infer Stasis Clusters merge distance must be between 0 and 100', 0, 100)
        if message:
            return message
        return True

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {'required': {'input_json': ('JSON', {'description': 'JSON output file from HyPhy B-STILL analysis'})}, 'optional': {'ebf': ('FLOAT', {'default': 10.0, 'min': 0, 'max': 10000, 'description': 'Empirical Bayes Factor threshold for identifying stasis sites'}), 'permutations': ('INT', {'default': 10000, 'min': 100, 'max': 100000, 'description': 'Permutations for family-wise error rate control'}), 'alpha': ('FLOAT', {'default': 0.05, 'min': 0.001, 'max': 0.5, 'description': 'Family-wise error rate threshold'}), 'max_cluster': ('INT', {'default': 30, 'min': 3, 'max': 100, 'description': 'Maximum number of stasis sites per interval scan', 'advanced': True}), 'merge': ('INT', {'default': 15, 'min': 0, 'max': 100, 'description': 'Distance in codons to merge adjacent clusters', 'advanced': True}), 'script_path': ('FILE', {'default': cls._default_script_path(), 'description': 'Path to the Galaxy infer_stasis_clusters.py helper script', 'advanced': True})}, 'hidden': {'output': ('STRING', {})}}


class HyPhyMEMENode(CommandNode):
    """Detect pervasive or episodic site-level diversifying selection with HyPhy MEME."""
    NODE_ID = 'hyphy_meme'
    DISPLAY_NAME = 'HyPhy-MEME'
    REQUIRED_CONDA_PACKAGES = ['hyphy']
    CATEGORY = 'phylogeny'
    DESCRIPTION = 'Detect pervasive or episodic site-level diversifying selection with HyPhy MEME.'
    SEARCH_ALIASES = [BIONODULO_BUILTIN_ALIAS, 'HyPhy', 'MEME', 'Mixed Effects Model of Evolution', 'episodic diversifying selection', 'pervasive selection', 'site-level selection', 'positive selection', 'multiple nucleotide substitutions', 'imputed states', 'phylogenetics']
    RETURN_TYPES = ('JSON', 'TEXT')
    RETURN_NAMES = ('meme_output', 'meme_md_report')
    REQUIRED_EXECUTABLES = ['HYPHYMPI', 'mpirun']
    DOCUMENTATION_URL = 'http://hyphy.org/methods/selection-methods/#MEME'
    CITATION_DOIS = HYPHY_MEME_CITATION_DOIS
    CITATION_URLS = [f'{DOI_URL}{doi}' for doi in HYPHY_MEME_CITATION_DOIS]
    CITATION_TEXT = HYPHY_MEME_CITATION_TEXT
    VERSION = '2.5.96'
    SHELL = True
    GENETIC_CODES = HyPhyABSRELNode.GENETIC_CODES
    INPUT_EXTENSIONS = HyPhyABSRELNode.INPUT_EXTENSIONS
    BRANCH_SELECTIONS = HyPhyABSRELNode.BRANCH_SELECTIONS
    MULTIPLE_HITS = HyPhyABSRELNode.MULTIPLE_HITS
    SITE_MULTIHIT = ['Estimate', 'No']
    PRECISION_OPTIONS = ['standard', 'reduced']
    KILL_ZERO_LENGTHS = HyPhyABSRELNode.KILL_ZERO_LENGTHS

    @classmethod
    def _input_name(cls, inputs: dict[str, Any]) -> str:
        ext = str(inputs.get('input_ext', 'fasta')).strip().lstrip('.') or 'fasta'
        return f'input.{ext}'

    @classmethod
    def _branch_arg(cls, inputs: dict[str, Any]) -> str:
        branch_sel = str(inputs.get('branch_sel', 'All') or 'All')
        if branch_sel == 'specify':
            return str(inputs.get('branch_label', '')).strip()
        return branch_sel

    @staticmethod
    def _bool_value(value: Any) -> bool:
        if isinstance(value, str):
            return value.lower() in {'true', 'yes', '1', 'on'}
        return bool(value)

    @staticmethod
    def _yes_no(value: Any) -> str:
        return 'Yes' if HyPhyMEMENode._bool_value(value) else 'No'

    @staticmethod
    def _mpirun_prefix(threads: Any) -> str:
        return f'${{GALAXY_MPIRUN:-mpirun --allow-run-as-root --oversubscribe -mca orte_tmpdir_base "${{TMPDIR:-.}}" -np {threads}}}'

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> str:
        out = _out(inputs)
        input_name = cls._input_name(inputs)
        commands: list[str] = []
        if str(inputs.get('input_nhx', '')).strip():
            commands.append(_shell_join(['ln', '-s', str(inputs.get('input_nhx', '')), 'input.nhx']))
        commands.append(_shell_join(['ln', '-s', str(inputs.get('input_file', '')), input_name]))
        cmd = ['--alignment', f'./{input_name}']
        if str(inputs.get('input_nhx', '')).strip():
            cmd.extend(['--tree', 'input.nhx'])
        cmd.extend(['--code', str(inputs.get('gencodeid', 'Universal') or 'Universal'), '--branches', cls._branch_arg(inputs), '--pvalue', str(inputs.get('p_value', 0.1)), '--resample', str(inputs.get('resample', 0)), '--rates', str(inputs.get('rates', 2)), '--multiple-hits', str(inputs.get('multiple_hits', 'None') or 'None')])
        if str(inputs.get('multiple_hits', 'None') or 'None') != 'None':
            cmd.extend(['--site-multihit', str(inputs.get('site_multihit', 'Estimate') or 'Estimate')])
        cmd.extend(['--impute-states', cls._yes_no(inputs.get('impute_states', False)), '--precision', str(inputs.get('precision', 'standard') or 'standard'), '--kill-zero-lengths', str(inputs.get('kill_zero_lengths', 'Yes') or 'Yes')])
        if cls._bool_value(inputs.get('restrict_sites', False)):
            cmd.extend(['--limit-to-sites', str(inputs.get('limit_to_sites', '') or ''), '--save-lf-for-sites', str(inputs.get('save_lf_for_sites', '') or '')])
        cmd.extend(['--output', f'{out}/meme_output.json', '--full-model', cls._yes_no(inputs.get('full_model', True)), '>', f'{out}/meme_stdout.md'])
        commands.append(f"{cls._mpirun_prefix(inputs.get('threads', 4))} HYPHYMPI meme {_shell_join(cmd)}")
        return ' && '.join(commands)

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        out = Path(output_dir) / cls.NODE_ID
        out.mkdir(parents=True, exist_ok=True)
        return [out / 'meme_output.json', out / 'meme_stdout.md']

    @staticmethod
    def _validate_float_range(value: Any, message: str, low: float, high: float) -> str | None:
        try:
            parsed = float(value)
        except (TypeError, ValueError):
            return message
        return message if parsed < low or parsed > high else None

    @staticmethod
    def _validate_int_range(value: Any, message: str, low: int, high: int) -> str | None:
        try:
            parsed = int(value)
        except (TypeError, ValueError):
            return message
        return message if parsed < low or parsed > high else None

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        if not str(inputs.get('input_file', '')).strip():
            return 'HyPhy-MEME alignment input is required'
        input_ext = str(inputs.get('input_ext', 'fasta') or 'fasta').strip().lstrip('.')
        if input_ext not in cls.INPUT_EXTENSIONS:
            return f'Unsupported HyPhy-MEME input extension: {input_ext}'
        gencodeid = str(inputs.get('gencodeid', 'Universal') or 'Universal')
        if gencodeid not in cls.GENETIC_CODES:
            return f'Unsupported HyPhy genetic code: {gencodeid}'
        branch_sel = str(inputs.get('branch_sel', 'All') or 'All')
        if branch_sel not in cls.BRANCH_SELECTIONS:
            return f'Unsupported HyPhy-MEME branch selection: {branch_sel}'
        if branch_sel == 'specify' and (not str(inputs.get('branch_label', '')).strip()):
            return 'HyPhy-MEME custom branch selection requires a branch label'
        message = cls._validate_float_range(inputs.get('p_value', 0.1), 'HyPhy-MEME p-value threshold must be between 0 and 1', 0, 1)
        if message:
            return message
        message = cls._validate_int_range(inputs.get('resample', 0), 'HyPhy-MEME resampling replicates must be between 0 and 1000', 0, 1000)
        if message:
            return message
        message = cls._validate_int_range(inputs.get('rates', 2), 'HyPhy-MEME omega rate classes must be between 2 and 4', 2, 4)
        if message:
            return message
        multiple_hits = str(inputs.get('multiple_hits', 'None') or 'None')
        if multiple_hits not in cls.MULTIPLE_HITS:
            return f'Unsupported HyPhy-MEME multiple-hits mode: {multiple_hits}'
        if multiple_hits != 'None':
            site_multihit = str(inputs.get('site_multihit', 'Estimate') or 'Estimate')
            if site_multihit not in cls.SITE_MULTIHIT:
                return f'Unsupported HyPhy-MEME site-multihit mode: {site_multihit}'
        precision = str(inputs.get('precision', 'standard') or 'standard')
        if precision not in cls.PRECISION_OPTIONS:
            return f'Unsupported HyPhy-MEME optimization precision: {precision}'
        kill_zero_lengths = str(inputs.get('kill_zero_lengths', 'Yes') or 'Yes')
        if kill_zero_lengths not in cls.KILL_ZERO_LENGTHS:
            return f'Unsupported HyPhy-MEME zero-length branch handling: {kill_zero_lengths}'
        try:
            threads = int(inputs.get('threads', 4))
        except (TypeError, ValueError):
            return 'HyPhy-MEME threads must be a positive integer'
        if threads < 1:
            return 'HyPhy-MEME threads must be a positive integer'
        return True

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {'required': {'input_file': ('FASTA', {'description': 'Codon alignment in FASTA, compressed FASTA, or NEXUS format'})}, 'optional': {'input_nhx': ('FILE', {'default': '', 'description': 'Optional Newick/NHX phylogenetic tree'}), 'input_ext': ('STRING', {'default': 'fasta', 'options': cls.INPUT_EXTENSIONS, 'advanced': True}), 'gencodeid': ('STRING', {'default': 'Universal', 'options': cls.GENETIC_CODES, 'description': 'HyPhy genetic code for codon interpretation'}), 'branch_sel': ('STRING', {'default': 'All', 'options': cls.BRANCH_SELECTIONS, 'description': 'Branches to test for episodic diversifying selection'}), 'branch_label': ('STRING', {'default': '', 'description': 'Custom branch label when branch selection is specify'}), 'p_value': ('FLOAT', {'default': 0.1, 'min': 0, 'max': 1, 'description': 'P-value threshold'}), 'resample': ('INT', {'default': 0, 'min': 0, 'max': 1000, 'description': 'Parametric bootstrap resampling replicates per site', 'advanced': True}), 'rates': ('INT', {'default': 2, 'min': 2, 'max': 4, 'description': 'Number of omega rate classes'}), 'multiple_hits': ('STRING', {'default': 'None', 'options': cls.MULTIPLE_HITS, 'description': 'Multiple-hit correction mode', 'advanced': True}), 'site_multihit': ('STRING', {'default': 'Estimate', 'options': cls.SITE_MULTIHIT, 'description': 'Estimate multiple-hit rates for each site when multiple hits are enabled', 'advanced': True}), 'impute_states': ('BOOLEAN', {'default': False, 'description': 'Impute likely character states for each sequence'}), 'precision': ('STRING', {'default': 'standard', 'options': cls.PRECISION_OPTIONS, 'description': 'Optimization precision for preliminary fits', 'advanced': True}), 'kill_zero_lengths': ('STRING', {'default': 'Yes', 'options': cls.KILL_ZERO_LENGTHS, 'description': 'Zero-length branch handling', 'advanced': True}), 'restrict_sites': ('BOOLEAN', {'default': False, 'description': 'Restrict MEME analysis to a subset of sites'}), 'limit_to_sites': ('STRING', {'default': '', 'description': 'Comma-separated 1-based site indices to analyze'}), 'save_lf_for_sites': ('STRING', {'default': '', 'description': 'Comma-separated sites for likelihood-function snapshots'}), 'full_model': ('BOOLEAN', {'default': True, 'description': 'Perform branch length re-optimization under the full codon model', 'advanced': True}), 'threads': ('INT', {'default': 4, 'min': 1, 'max': 128})}, 'hidden': {'output': ('STRING', {})}}


class HyPhyPRIMENode(CommandNode):
    """Model site-level physicochemical selection with HyPhy PRIME."""
    NODE_ID = 'hyphy_prime'
    DISPLAY_NAME = 'HyPhy-PRIME'
    REQUIRED_CONDA_PACKAGES = ['hyphy']
    CATEGORY = 'phylogeny'
    DESCRIPTION = 'Model site-level physicochemical selection with HyPhy PRIME.'
    SEARCH_ALIASES = [BIONODULO_BUILTIN_ALIAS, 'HyPhy', 'PRIME', 'Property Informed Models of Evolution', 'PRoperty Informed Models of Evolution', 'physicochemical selection', 'biochemical properties', 'amino-acid properties', 'property-informed codon model', 'site-level constraints', 'protein evolution', 'phylogenetics']
    RETURN_TYPES = ('JSON', 'TEXT', 'JSON')
    RETURN_NAMES = ('prime_output', 'prime_md_report', 'intermediate_fits')
    REQUIRED_EXECUTABLES = ['HYPHYMPI', 'mpirun']
    DOCUMENTATION_URL = 'http://hyphy.org/methods/selection-methods/#PRIME'
    CITATION_DOIS = HYPHY_PRIME_CITATION_DOIS
    CITATION_URLS = [f'{DOI_URL}{doi}' for doi in HYPHY_PRIME_CITATION_DOIS]
    CITATION_TEXT = HYPHY_PRIME_CITATION_TEXT
    VERSION = '2.5.96'
    SHELL = True
    GENETIC_CODES = HyPhyABSRELNode.GENETIC_CODES
    INPUT_EXTENSIONS = HyPhyABSRELNode.INPUT_EXTENSIONS
    BRANCH_SELECTIONS = HyPhyABSRELNode.BRANCH_SELECTIONS
    KILL_ZERO_LENGTHS = HyPhyABSRELNode.KILL_ZERO_LENGTHS
    PROPERTY_SOURCE_TYPES = ['builtin', 'custom']
    PROPERTY_SETS = ['Atchley', '2PROP', '3PROP', '4PROP', '5PROP', 'Random-2', 'Random-3', 'Random-4', 'Random-5']

    @classmethod
    def _input_name(cls, inputs: dict[str, Any]) -> str:
        ext = str(inputs.get('input_ext', 'fasta')).strip().lstrip('.') or 'fasta'
        return f'input.{ext}'

    @classmethod
    def _branch_arg(cls, inputs: dict[str, Any]) -> str:
        branch_sel = str(inputs.get('branch_sel', 'All') or 'All')
        if branch_sel == 'specify':
            return str(inputs.get('branch_label', '')).strip()
        return branch_sel

    @staticmethod
    def _bool_value(value: Any) -> bool:
        if isinstance(value, str):
            return value.lower() in {'true', 'yes', '1', 'on'}
        return bool(value)

    @staticmethod
    def _yes_no(value: Any) -> str:
        return 'Yes' if HyPhyPRIMENode._bool_value(value) else 'No'

    @staticmethod
    def _mpirun_prefix(threads: Any) -> str:
        return f'${{GALAXY_MPIRUN:-mpirun --allow-run-as-root --oversubscribe -mca orte_tmpdir_base "${{TMPDIR:-.}}" -np {threads}}}'

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> str:
        out = _out(inputs)
        input_name = cls._input_name(inputs)
        commands: list[str] = []
        if str(inputs.get('input_nhx', '')).strip():
            commands.append(_shell_join(['ln', '-s', str(inputs.get('input_nhx', '')), 'input.nhx']))
        commands.append(_shell_join(['ln', '-s', str(inputs.get('input_file', '')), input_name]))
        cmd = ['--alignment', f'./{input_name}']
        if str(inputs.get('input_nhx', '')).strip():
            cmd.extend(['--tree', 'input.nhx'])
        cmd.extend(['--code', str(inputs.get('gencodeid', 'Universal') or 'Universal'), '--branches', cls._branch_arg(inputs)])
        if str(inputs.get('prop_source_type', 'builtin') or 'builtin') == 'custom':
            cmd.extend(['--property-set', 'Custom', '--property-file', str(inputs.get('property_file', ''))])
        else:
            cmd.extend(['--property-set', str(inputs.get('prop_set', '3PROP') or '3PROP')])
        cmd.extend(['--pvalue', str(inputs.get('p_value', 0.1)), '--impute-states', cls._yes_no(inputs.get('impute_states', False))])
        if cls._bool_value(inputs.get('save_intermediate', False)):
            cmd.extend(['--intermediate-fits', f'{out}/intermediate_fits.json'])
        cmd.extend(['--kill-zero-lengths', str(inputs.get('kill_zero_lengths', 'Yes') or 'Yes'), '--output', f'{out}/prime_output.json', '>', f'{out}/prime_stdout.md'])
        commands.append(f"{cls._mpirun_prefix(inputs.get('threads', 4))} HYPHYMPI prime {_shell_join(cmd)}")
        return ' && '.join(commands)

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        out = Path(output_dir) / cls.NODE_ID
        out.mkdir(parents=True, exist_ok=True)
        outputs = [out / 'prime_output.json', out / 'prime_stdout.md']
        if cls._bool_value(inputs.get('save_intermediate', False)):
            outputs.append(out / 'intermediate_fits.json')
        return outputs

    @staticmethod
    def _validate_float_range(value: Any, message: str, low: float, high: float) -> str | None:
        try:
            parsed = float(value)
        except (TypeError, ValueError):
            return message
        return message if parsed < low or parsed > high else None

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        if not str(inputs.get('input_file', '')).strip():
            return 'HyPhy-PRIME alignment input is required'
        input_ext = str(inputs.get('input_ext', 'fasta') or 'fasta').strip().lstrip('.')
        if input_ext not in cls.INPUT_EXTENSIONS:
            return f'Unsupported HyPhy-PRIME input extension: {input_ext}'
        gencodeid = str(inputs.get('gencodeid', 'Universal') or 'Universal')
        if gencodeid not in cls.GENETIC_CODES:
            return f'Unsupported HyPhy genetic code: {gencodeid}'
        branch_sel = str(inputs.get('branch_sel', 'All') or 'All')
        if branch_sel not in cls.BRANCH_SELECTIONS:
            return f'Unsupported HyPhy-PRIME branch selection: {branch_sel}'
        if branch_sel == 'specify' and (not str(inputs.get('branch_label', '')).strip()):
            return 'HyPhy-PRIME custom branch selection requires a branch label'
        prop_source_type = str(inputs.get('prop_source_type', 'builtin') or 'builtin')
        if prop_source_type not in cls.PROPERTY_SOURCE_TYPES:
            return f'Unsupported HyPhy-PRIME property source: {prop_source_type}'
        if prop_source_type == 'custom':
            if not str(inputs.get('property_file', '')).strip():
                return 'HyPhy-PRIME custom property source requires a property JSON file'
        else:
            prop_set = str(inputs.get('prop_set', '3PROP') or '3PROP')
            if prop_set not in cls.PROPERTY_SETS:
                return f'Unsupported HyPhy-PRIME property set: {prop_set}'
        message = cls._validate_float_range(inputs.get('p_value', 0.1), 'HyPhy-PRIME p-value threshold must be between 0 and 1', 0, 1)
        if message:
            return message
        kill_zero_lengths = str(inputs.get('kill_zero_lengths', 'Yes') or 'Yes')
        if kill_zero_lengths not in cls.KILL_ZERO_LENGTHS:
            return f'Unsupported HyPhy-PRIME zero-length branch handling: {kill_zero_lengths}'
        try:
            threads = int(inputs.get('threads', 4))
        except (TypeError, ValueError):
            return 'HyPhy-PRIME threads must be a positive integer'
        if threads < 1:
            return 'HyPhy-PRIME threads must be a positive integer'
        return True

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {'required': {'input_file': ('FASTA', {'description': 'Codon alignment in FASTA, compressed FASTA, or NEXUS format'})}, 'optional': {'input_nhx': ('FILE', {'default': '', 'description': 'Optional Newick/NHX phylogenetic tree'}), 'input_ext': ('STRING', {'default': 'fasta', 'options': cls.INPUT_EXTENSIONS, 'advanced': True}), 'gencodeid': ('STRING', {'default': 'Universal', 'options': cls.GENETIC_CODES, 'description': 'HyPhy genetic code for codon interpretation'}), 'branch_sel': ('STRING', {'default': 'All', 'options': cls.BRANCH_SELECTIONS, 'description': 'Branches to test for property-informed selection'}), 'branch_label': ('STRING', {'default': '', 'description': 'Custom branch label when branch selection is specify'}), 'prop_source_type': ('STRING', {'default': 'builtin', 'options': cls.PROPERTY_SOURCE_TYPES, 'description': 'Source of amino-acid property definitions'}), 'prop_set': ('STRING', {'default': '3PROP', 'options': cls.PROPERTY_SETS, 'description': 'Built-in biochemical property set'}), 'property_file': ('JSON', {'default': '', 'description': 'Custom amino-acid property JSON file'}), 'p_value': ('FLOAT', {'default': 0.1, 'min': 0, 'max': 1, 'description': 'P-value threshold'}), 'impute_states': ('BOOLEAN', {'default': False, 'description': 'Impute likely character states for each sequence'}), 'save_intermediate': ('BOOLEAN', {'default': False, 'description': 'Save intermediate PRIME model fits as JSON', 'advanced': True}), 'kill_zero_lengths': ('STRING', {'default': 'Yes', 'options': cls.KILL_ZERO_LENGTHS, 'description': 'Zero-length branch handling', 'advanced': True}), 'threads': ('INT', {'default': 4, 'min': 1, 'max': 128})}, 'hidden': {'output': ('STRING', {})}}


class HyPhyRELAXNode(CommandNode):
    """Detect relaxed or intensified selection with HyPhy RELAX."""
    NODE_ID = 'hyphy_relax'
    DISPLAY_NAME = 'HyPhy-RELAX'
    REQUIRED_CONDA_PACKAGES = ['hyphy']
    CATEGORY = 'phylogeny'
    DESCRIPTION = 'Detect relaxed or intensified selection in a codon-based phylogenetic framework with HyPhy RELAX.'
    SEARCH_ALIASES = [BIONODULO_BUILTIN_ALIAS, 'HyPhy', 'RELAX', 'relaxed selection', 'intensified selection', 'selection intensity', 'phylogenetic framework', 'test branches', 'reference branches', 'group mode', 'multiple alignments', 'synonymous rate variation', 'phylogenetics']
    RETURN_TYPES = ('JSON', 'TEXT')
    RETURN_NAMES = ('relax_output', 'relax_md_report')
    REQUIRED_EXECUTABLES = ['hyphy']
    DOCUMENTATION_URL = 'http://hyphy.org/methods/selection-methods/#RELAX'
    CITATION_DOIS = HYPHY_RELAX_CITATION_DOIS
    CITATION_URLS = [f'{DOI_URL}{doi}' for doi in HYPHY_RELAX_CITATION_DOIS]
    CITATION_TEXT = HYPHY_RELAX_CITATION_TEXT
    VERSION = '2.5.96'
    SHELL = True
    GENETIC_CODES = HyPhyABSRELNode.GENETIC_CODES
    INPUT_EXTENSIONS = HyPhyABSRELNode.INPUT_EXTENSIONS
    MULTIPLE_HITS = HyPhyABSRELNode.MULTIPLE_HITS
    KILL_ZERO_LENGTHS = HyPhyABSRELNode.KILL_ZERO_LENGTHS
    INPUT_TYPES_OPTIONS = ['single', 'multiple']
    MODEL_OPTIONS = ['All', 'Minimal']
    MODE_OPTIONS = ['Classic mode', 'Group mode']
    SRV_OPTIONS = ['No', 'Yes', 'Branch-site', 'HMM']

    @classmethod
    def _input_name(cls, inputs: dict[str, Any]) -> str:
        ext = str(inputs.get('input_ext', 'fasta')).strip().lstrip('.') or 'fasta'
        return f'input.{ext}'

    @staticmethod
    def _bool_value(value: Any) -> bool:
        if isinstance(value, str):
            return value.lower() in {'true', 'yes', '1', 'on'}
        return bool(value)

    @classmethod
    def _multiple_inputs(cls, inputs: dict[str, Any]) -> list[dict[str, str]]:
        raw = inputs.get('input_data_and_tree')
        if isinstance(raw, list):
            normalized = []
            for item in raw:
                if not isinstance(item, dict):
                    continue
                normalized.append({'input_file': str(item.get('input_file', '')), 'input_ext': str(item.get('input_ext', item.get('ext', 'fasta')) or 'fasta').strip().lstrip('.'), 'input_nhx': str(item.get('input_nhx', item.get('input_tree', '')) or '')})
            return normalized
        input_files = _as_list(inputs.get('input_files'))
        input_exts = _as_list(inputs.get('input_exts'))
        input_trees = _as_list(inputs.get('input_trees'))
        normalized = []
        for index, input_file in enumerate(input_files):
            normalized.append({'input_file': input_file, 'input_ext': input_exts[index] if index < len(input_exts) else 'fasta', 'input_nhx': input_trees[index] if index < len(input_trees) else ''})
        return normalized

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> str:
        out = _out(inputs)
        commands: list[str] = []
        cmd = ['hyphy', 'relax']
        input_type = str(inputs.get('input_type', 'single') or 'single')
        if input_type == 'multiple':
            for index, input_data in enumerate(cls._multiple_inputs(inputs)):
                input_name = f"input_{index}.{input_data['input_ext']}"
                commands.append(_shell_join(['ln', '-s', input_data['input_file'], input_name]))
                if input_data['input_nhx'].strip():
                    commands.append(_shell_join(['ln', '-s', input_data['input_nhx'], f'input_{index}.nhx']))
                commands.append(_shell_join(['echo', input_name, '>>', 'filelist.txt']))
            cmd.extend(['--multiple-files', 'Yes', '--filelist', 'filelist.txt'])
            for index, input_data in enumerate(cls._multiple_inputs(inputs)):
                if input_data['input_nhx'].strip():
                    cmd.extend(['--tree', f'input_{index}.nhx'])
        else:
            input_name = cls._input_name(inputs)
            if str(inputs.get('input_nhx', '')).strip():
                commands.append(_shell_join(['ln', '-s', str(inputs.get('input_nhx', '')), 'input.nhx']))
            commands.append(_shell_join(['ln', '-s', str(inputs.get('input_file', '')), input_name]))
            cmd.extend(['--alignment', input_name])
            if str(inputs.get('input_nhx', '')).strip():
                cmd.extend(['--tree', 'input.nhx'])
        cmd.extend(['--models', str(inputs.get('models', 'All') or 'All'), '--code', str(inputs.get('gencodeid', 'Universal') or 'Universal'), '--test', str(inputs.get('test', 'Unlabeled branches') or 'Unlabeled branches')])
        if str(inputs.get('reference', '')).strip():
            cmd.extend(['--reference', str(inputs.get('reference', ''))])
        mode = str(inputs.get('mode', 'Classic mode') or 'Classic mode')
        cmd.extend(['--mode', mode])
        if mode == 'Group mode' and str(inputs.get('reference_group', '')).strip():
            cmd.extend(['--reference-group', str(inputs.get('reference_group', ''))])
        cmd.extend(['--grid-size', str(inputs.get('grid_size', 250)), '--starting-points', str(inputs.get('starting_points', 1)), '--syn-rates', str(inputs.get('syn_rates', 3)), '--rates', str(inputs.get('rates', 3)), '--srv', str(inputs.get('srv', 'No') or 'No')])
        multiple_hits = str(inputs.get('multiple_hits', 'None') or 'None')
        if multiple_hits != 'None':
            cmd.extend(['--multiple-hits', multiple_hits])
        cmd.extend(['--kill-zero-lengths', str(inputs.get('kill_zero_lengths', 'Yes') or 'Yes'), '--output', f'{out}/relax_output.json', '>', f'{out}/relax_stdout.md'])
        threads = inputs.get('threads', 1)
        commands.append(f'export OMP_NUM_THREADS="${{GALAXY_SLOTS:-{threads}}}"')
        commands.append(_shell_join(cmd))
        return ' && '.join(commands)

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        out = Path(output_dir) / cls.NODE_ID
        out.mkdir(parents=True, exist_ok=True)
        return [out / 'relax_output.json', out / 'relax_stdout.md']

    @staticmethod
    def _validate_int_range(value: Any, message: str, low: int, high: int) -> str | None:
        try:
            parsed = int(value)
        except (TypeError, ValueError):
            return message
        return message if parsed < low or parsed > high else None

    @classmethod
    def _validate_alignment_inputs(cls, inputs: dict[str, Any]) -> str | None:
        input_type = str(inputs.get('input_type', 'single') or 'single')
        if input_type == 'single':
            if not str(inputs.get('input_file', '')).strip():
                return 'HyPhy-RELAX alignment input is required'
            input_ext = str(inputs.get('input_ext', 'fasta') or 'fasta').strip().lstrip('.')
            if input_ext not in cls.INPUT_EXTENSIONS:
                return f'Unsupported HyPhy-RELAX input extension: {input_ext}'
            return None
        input_data_and_tree = cls._multiple_inputs(inputs)
        if not input_data_and_tree:
            return 'HyPhy-RELAX multiple-input mode requires at least one alignment'
        for input_data in input_data_and_tree:
            if not input_data['input_file'].strip():
                return 'HyPhy-RELAX multiple-input mode requires non-empty alignment files'
            input_ext = str(input_data['input_ext'] or 'fasta').strip().lstrip('.')
            if input_ext not in cls.INPUT_EXTENSIONS:
                return f'Unsupported HyPhy-RELAX input extension: {input_ext}'
        return None

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        input_type = str(inputs.get('input_type', 'single') or 'single')
        if input_type not in cls.INPUT_TYPES_OPTIONS:
            return f'Unsupported HyPhy-RELAX input type: {input_type}'
        message = cls._validate_alignment_inputs(inputs)
        if message:
            return message
        gencodeid = str(inputs.get('gencodeid', 'Universal') or 'Universal')
        if gencodeid not in cls.GENETIC_CODES:
            return f'Unsupported HyPhy genetic code: {gencodeid}'
        models = str(inputs.get('models', 'All') or 'All')
        if models not in cls.MODEL_OPTIONS:
            return f'Unsupported HyPhy-RELAX analysis type: {models}'
        if not str(inputs.get('test', 'Unlabeled branches') or '').strip():
            return 'HyPhy-RELAX test branch label is required'
        mode = str(inputs.get('mode', 'Classic mode') or 'Classic mode')
        if mode not in cls.MODE_OPTIONS:
            return f'Unsupported HyPhy-RELAX run mode: {mode}'
        for key, default, low, high, label in [('grid_size', 250, 1, 5000, 'grid size'), ('starting_points', 1, 1, 1000, 'starting points'), ('syn_rates', 3, 1, 10, 'synonymous rate classes'), ('rates', 3, 2, 10, 'non-synonymous rate classes')]:
            message = cls._validate_int_range(inputs.get(key, default), f'HyPhy-RELAX {label} must be between {low} and {high}', low, high)
            if message:
                return message
        srv = str(inputs.get('srv', 'No') or 'No')
        if srv not in cls.SRV_OPTIONS:
            return f'Unsupported HyPhy-RELAX synonymous rate variation setting: {srv}'
        multiple_hits = str(inputs.get('multiple_hits', 'None') or 'None')
        if multiple_hits not in cls.MULTIPLE_HITS:
            return f'Unsupported HyPhy-RELAX multiple-hits mode: {multiple_hits}'
        kill_zero_lengths = str(inputs.get('kill_zero_lengths', 'Yes') or 'Yes')
        if kill_zero_lengths not in cls.KILL_ZERO_LENGTHS:
            return f'Unsupported HyPhy-RELAX zero-length branch handling: {kill_zero_lengths}'
        try:
            threads = int(inputs.get('threads', 1))
        except (TypeError, ValueError):
            return 'HyPhy-RELAX threads must be a positive integer'
        if threads < 1:
            return 'HyPhy-RELAX threads must be a positive integer'
        return True

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {'required': {'input_file': ('FASTA', {'description': 'Codon alignment in FASTA, compressed FASTA, or NEXUS format'})}, 'optional': {'input_type': ('STRING', {'default': 'single', 'options': cls.INPUT_TYPES_OPTIONS, 'description': 'Use a single alignment or multiple alignment/tree pairs'}), 'input_nhx': ('FILE', {'default': '', 'description': 'Optional Newick/NHX phylogenetic tree'}), 'input_ext': ('STRING', {'default': 'fasta', 'options': cls.INPUT_EXTENSIONS, 'advanced': True}), 'input_data_and_tree': ('JSON', {'default': [], 'description': 'Galaxy repeat-style list of alignment/tree dictionaries for multiple mode'}), 'input_files': ('FILE', {'default': [], 'multiple': True, 'description': 'Alignment files for multiple mode'}), 'input_trees': ('FILE', {'default': [], 'multiple': True, 'description': 'Optional Newick/NHX trees matching input_files'}), 'input_exts': ('STRING', {'default': [], 'multiple': True, 'options': cls.INPUT_EXTENSIONS, 'description': 'File extensions matching input_files'}), 'gencodeid': ('STRING', {'default': 'Universal', 'options': cls.GENETIC_CODES, 'description': 'HyPhy genetic code for codon interpretation'}), 'models': ('STRING', {'default': 'All', 'options': cls.MODEL_OPTIONS, 'description': 'Fit all RELAX models or the faster minimal test'}), 'test': ('STRING', {'default': 'Unlabeled branches', 'description': 'Branch label used as the RELAX test set'}), 'reference': ('STRING', {'default': '', 'description': 'Optional branch label used as the RELAX reference set'}), 'mode': ('STRING', {'default': 'Classic mode', 'options': cls.MODE_OPTIONS, 'description': 'RELAX classic test/reference mode or group comparison mode'}), 'reference_group': ('STRING', {'default': '', 'description': 'Reference branch group for group mode'}), 'grid_size': ('INT', {'default': 250, 'min': 1, 'max': 5000, 'description': 'Points in the initial distributional guess'}), 'starting_points': ('INT', {'default': 1, 'min': 1, 'max': 1000, 'description': 'Initial random guesses for rate optimization'}), 'syn_rates': ('INT', {'default': 3, 'min': 1, 'max': 10, 'description': 'Synonymous rate classes'}), 'rates': ('INT', {'default': 3, 'min': 2, 'max': 10, 'description': 'Non-synonymous omega rate classes'}), 'srv': ('STRING', {'default': 'No', 'options': cls.SRV_OPTIONS, 'description': 'Synonymous rate variation model'}), 'multiple_hits': ('STRING', {'default': 'None', 'options': cls.MULTIPLE_HITS, 'description': 'Multiple-hit correction mode', 'advanced': True}), 'kill_zero_lengths': ('STRING', {'default': 'Yes', 'options': cls.KILL_ZERO_LENGTHS, 'description': 'Zero-length branch handling', 'advanced': True}), 'threads': ('INT', {'default': 1, 'min': 1, 'max': 128})}, 'hidden': {'output': ('STRING', {})}}


class HyPhySLACNode(CommandNode):
    """Detect pervasive site-level selection with HyPhy SLAC."""
    NODE_ID = 'hyphy_slac'
    DISPLAY_NAME = 'HyPhy-SLAC'
    REQUIRED_CONDA_PACKAGES = ['hyphy']
    CATEGORY = 'phylogeny'
    DESCRIPTION = 'Detect pervasive site-level selection with HyPhy SLAC.'
    SEARCH_ALIASES = [BIONODULO_BUILTIN_ALIAS, 'HyPhy', 'SLAC', 'Single Likelihood Ancestor Counting', 'pervasive selection', 'site-level selection', 'ancestral state reconstruction', 'synonymous substitutions', 'nonsynonymous substitutions', 'positive selection', 'purifying selection', 'phylogenetics']
    RETURN_TYPES = ('TEXT', 'JSON')
    RETURN_NAMES = ('slac_md_report', 'slac_output')
    REQUIRED_EXECUTABLES = ['hyphy']
    DOCUMENTATION_URL = 'http://hyphy.org/methods/selection-methods/#SLAC'
    CITATION_DOIS = HYPHY_SLAC_CITATION_DOIS
    CITATION_URLS = [f'{DOI_URL}{doi}' for doi in HYPHY_SLAC_CITATION_DOIS]
    CITATION_TEXT = HYPHY_SLAC_CITATION_TEXT
    VERSION = '2.5.96'
    SHELL = True
    GENETIC_CODES = HyPhyABSRELNode.GENETIC_CODES
    INPUT_EXTENSIONS = HyPhyABSRELNode.INPUT_EXTENSIONS
    BRANCH_SELECTIONS = HyPhyABSRELNode.BRANCH_SELECTIONS
    KILL_ZERO_LENGTHS = HyPhyABSRELNode.KILL_ZERO_LENGTHS

    @classmethod
    def _input_name(cls, inputs: dict[str, Any]) -> str:
        ext = str(inputs.get('input_ext', 'fasta')).strip().lstrip('.') or 'fasta'
        return f'input.{ext}'

    @classmethod
    def _branch_arg(cls, inputs: dict[str, Any]) -> str:
        branch_sel = str(inputs.get('branch_sel', 'All') or 'All')
        if branch_sel == 'specify':
            return str(inputs.get('branch_label', '')).strip()
        return branch_sel

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> str:
        out = _out(inputs)
        input_name = cls._input_name(inputs)
        commands: list[str] = []
        if str(inputs.get('input_nhx', '')).strip():
            commands.append(_shell_join(['ln', '-s', str(inputs.get('input_nhx', '')), 'input.nhx']))
        commands.append(_shell_join(['ln', '-s', str(inputs.get('input_file', '')), input_name]))
        cmd = ['hyphy', f"CPU={inputs.get('threads', 4)}", 'slac', '--alignment', f'./{input_name}']
        if str(inputs.get('input_nhx', '')).strip():
            cmd.extend(['--tree', 'input.nhx'])
        cmd.extend(['--code', str(inputs.get('gencodeid', 'Universal') or 'Universal'), '--branches', cls._branch_arg(inputs), '--samples', str(inputs.get('number_of_samples', 0)), '--pvalue', str(inputs.get('p_value', 0.1)), '--output', f'{out}/slac_output.json', '--kill-zero-lengths', str(inputs.get('kill_zero_lengths', 'Yes') or 'Yes'), '>', f'{out}/slac_stdout.md'])
        commands.append(_shell_join(cmd))
        return ' && '.join(commands)

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        out = Path(output_dir) / cls.NODE_ID
        out.mkdir(parents=True, exist_ok=True)
        return [out / 'slac_stdout.md', out / 'slac_output.json']

    @staticmethod
    def _validate_unit_float(value: Any, message: str) -> str | None:
        try:
            parsed = float(value)
        except (TypeError, ValueError):
            return message
        return message if parsed < 0 or parsed > 1 else None

    @staticmethod
    def _validate_int_range(value: Any, message: str, low: int, high: int) -> str | None:
        try:
            parsed = int(value)
        except (TypeError, ValueError):
            return message
        return message if parsed < low or parsed > high else None

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        if not str(inputs.get('input_file', '')).strip():
            return 'HyPhy-SLAC alignment input is required'
        input_ext = str(inputs.get('input_ext', 'fasta') or 'fasta').strip().lstrip('.')
        if input_ext not in cls.INPUT_EXTENSIONS:
            return f'Unsupported HyPhy-SLAC input extension: {input_ext}'
        gencodeid = str(inputs.get('gencodeid', 'Universal') or 'Universal')
        if gencodeid not in cls.GENETIC_CODES:
            return f'Unsupported HyPhy genetic code: {gencodeid}'
        branch_sel = str(inputs.get('branch_sel', 'All') or 'All')
        if branch_sel not in cls.BRANCH_SELECTIONS:
            return f'Unsupported HyPhy-SLAC branch selection: {branch_sel}'
        if branch_sel == 'specify' and (not str(inputs.get('branch_label', '')).strip()):
            return 'HyPhy-SLAC custom branch selection requires a branch label'
        message = cls._validate_unit_float(inputs.get('p_value', 0.1), 'HyPhy-SLAC p-value threshold must be between 0 and 1')
        if message:
            return message
        message = cls._validate_int_range(inputs.get('number_of_samples', 0), 'HyPhy-SLAC ancestral reconstruction samples must be between 0 and 10000', 0, 10000)
        if message:
            return message
        kill_zero_lengths = str(inputs.get('kill_zero_lengths', 'Yes') or 'Yes')
        if kill_zero_lengths not in cls.KILL_ZERO_LENGTHS:
            return f'Unsupported HyPhy-SLAC zero-length branch handling: {kill_zero_lengths}'
        try:
            threads = int(inputs.get('threads', 4))
        except (TypeError, ValueError):
            return 'HyPhy-SLAC threads must be a positive integer'
        if threads < 1:
            return 'HyPhy-SLAC threads must be a positive integer'
        return True

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {'required': {'input_file': ('FASTA', {'description': 'Codon alignment in FASTA, compressed FASTA, or NEXUS format'})}, 'optional': {'input_nhx': ('FILE', {'default': '', 'description': 'Optional Newick/NHX phylogenetic tree'}), 'input_ext': ('STRING', {'default': 'fasta', 'options': cls.INPUT_EXTENSIONS, 'advanced': True}), 'gencodeid': ('STRING', {'default': 'Universal', 'options': cls.GENETIC_CODES, 'description': 'HyPhy genetic code for codon interpretation'}), 'branch_sel': ('STRING', {'default': 'All', 'options': cls.BRANCH_SELECTIONS, 'description': 'Branches to include in SLAC calculations'}), 'branch_label': ('STRING', {'default': '', 'description': 'Custom branch label when branch selection is specify'}), 'p_value': ('FLOAT', {'default': 0.1, 'min': 0, 'max': 1, 'description': 'P-value threshold'}), 'number_of_samples': ('INT', {'default': 0, 'min': 0, 'max': 10000, 'description': 'Alternative ancestral reconstructions to sample for uncertainty'}), 'kill_zero_lengths': ('STRING', {'default': 'Yes', 'options': cls.KILL_ZERO_LENGTHS, 'description': 'Zero-length branch handling', 'advanced': True}), 'threads': ('INT', {'default': 4, 'min': 1, 'max': 128})}, 'hidden': {'output': ('STRING', {})}}


class HyPhySM2019Node(CommandNode):
    """Partition trees using the modified Slatkin-Maddison test."""
    NODE_ID = 'hyphy_sm19'
    DISPLAY_NAME = 'HyPhy-SM2019'
    REQUIRED_CONDA_PACKAGES = ['hyphy']
    CATEGORY = 'phylogeny'
    DESCRIPTION = 'Partition trees using the modified Slatkin-Maddison test with HyPhy SM2019.'
    SEARCH_ALIASES = [BIONODULO_BUILTIN_ALIAS, 'HyPhy', 'SM2019', 'SM19', 'Structured Slatkin-Maddison', 'Modified Slatkin-Maddison Test', 'population segregation', 'gene flow', 'migration events', 'compartmentalization', 'phylogenetics']
    RETURN_TYPES = ('JSON', 'TEXT')
    RETURN_NAMES = ('sm19_output', 'sm19_md_report')
    REQUIRED_EXECUTABLES = ['hyphy']
    DOCUMENTATION_URL = 'https://github.com/veg/hyphy-analyses/tree/master/SlatkinMaddison'
    CITATION_DOIS = HYPHY_SM19_CITATION_DOIS
    CITATION_URLS = [f'{DOI_URL}{doi}' for doi in HYPHY_SM19_CITATION_DOIS]
    CITATION_TEXT = HYPHY_SM19_CITATION_TEXT
    VERSION = '2.5.96'
    SHELL = True
    DEFAULT_PARTITIONS = [{'label': 'Partition 1', 'regex': 'P1[0-9]+'}, {'label': 'Partition 2', 'regex': 'P2[0-9]+'}]

    @classmethod
    def _partitions(cls, inputs: dict[str, Any]) -> list[dict[str, str]]:
        raw_partitions = inputs.get('partitions', cls.DEFAULT_PARTITIONS)
        if not isinstance(raw_partitions, (list, tuple)):
            return []
        partitions: list[dict[str, str]] = []
        for partition in raw_partitions:
            if not isinstance(partition, dict):
                return []
            partitions.append({'label': str(partition.get('label', '')).strip(), 'regex': str(partition.get('regex', '')).strip()})
        return partitions

    @classmethod
    def _yes_no(cls, value: Any) -> str:
        if isinstance(value, str):
            return 'Yes' if value.lower() in {'true', 'yes', '1', 'on'} else 'No'
        return 'Yes' if bool(value) else 'No'

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> str:
        out = _out(inputs)
        partitions = cls._partitions(inputs)
        commands = [_shell_join(['ln', '-s', str(inputs.get('input_file', '')), 'sm19_input.nhx'])]
        cmd = ['hyphy', f"CPU={inputs.get('threads', 4)}", 'sm', '--tree', './sm19_input.nhx', '--groups', str(len(partitions))]
        for index, partition in enumerate(partitions, start=1):
            cmd.extend([f'--description-{index}', partition['label'], f'--regexp-{index}', partition['regex']])
        cmd.extend(['--replicates', str(inputs.get('replicates', 100)), '--weight', str(inputs.get('weight', 0.2)), '--use-bootstrap', cls._yes_no(inputs.get('use_bootstrap', True)), '--output', f'{out}/sm19_output.json', '>', f'{out}/sm19_stdout.md'])
        commands.append(_shell_join(cmd))
        return ' && '.join(commands)

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        out = Path(output_dir) / cls.NODE_ID
        out.mkdir(parents=True, exist_ok=True)
        return [out / 'sm19_output.json', out / 'sm19_stdout.md']

    @staticmethod
    def _validate_int_range(value: Any, message: str, low: int, high: int) -> str | None:
        try:
            parsed = int(value)
        except (TypeError, ValueError):
            return message
        return message if parsed < low or parsed > high else None

    @staticmethod
    def _validate_unit_float(value: Any, message: str) -> str | None:
        try:
            parsed = float(value)
        except (TypeError, ValueError):
            return message
        return message if parsed < 0 or parsed > 1 else None

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        if not str(inputs.get('input_file', '')).strip():
            return 'HyPhy-SM2019 input tree is required'
        partitions = cls._partitions(inputs)
        if len(partitions) < 2 or len(partitions) > 50:
            return 'HyPhy-SM2019 requires between 2 and 50 partitions'
        if any((not partition['label'] or not partition['regex'] for partition in partitions)):
            return 'HyPhy-SM2019 partition labels and regular expressions are required'
        message = cls._validate_int_range(inputs.get('replicates', 100), 'HyPhy-SM2019 bootstrap replicates must be between 1 and 1000000', 1, 1000000)
        if message:
            return message
        message = cls._validate_unit_float(inputs.get('weight', 0.2), 'HyPhy-SM2019 structured permutation weight must be between 0 and 1')
        if message:
            return message
        try:
            threads = int(inputs.get('threads', 4))
        except (TypeError, ValueError):
            return 'HyPhy-SM2019 threads must be a positive integer'
        if threads < 1:
            return 'HyPhy-SM2019 threads must be a positive integer'
        return True

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {'required': {'input_file': ('PHYLOGENY_TREE', {'description': 'Newick, NHX, or NEXUS tree whose leaf names can be partitioned by regular expression'}), 'partitions': ('JSON', {'default': cls.DEFAULT_PARTITIONS, 'min_items': 2, 'max_items': 50, 'description': 'List of partition objects with label and regex fields'})}, 'optional': {'replicates': ('INT', {'default': 100, 'min': 1, 'max': 1000000, 'description': 'Number of bootstrap replicates'}), 'weight': ('FLOAT', {'default': 0.2, 'min': 0, 'max': 1, 'description': 'Probability of branch selection for structured permutation'}), 'use_bootstrap': ('BOOLEAN', {'default': True, 'description': 'Use bootstrap weights to respect well supported clades'}), 'threads': ('INT', {'default': 4, 'min': 1, 'max': 128})}, 'hidden': {'output': ('STRING', {})}}


class HyPhyStrikeAmbigsNode(CommandNode):
    """Replace ambiguous codons in a FASTA alignment with gap codons."""
    NODE_ID = 'hyphy_strike_ambigs'
    DISPLAY_NAME = 'Replace ambiguous codons'
    REQUIRED_CONDA_PACKAGES = ['hyphy']
    CATEGORY = 'phylogeny'
    DESCRIPTION = 'Replace ambiguous codons in an in-frame alignment using HyPhy.'
    SEARCH_ALIASES = [BIONODULO_BUILTIN_ALIAS, 'HyPhy', 'Strike-Ambigs', 'Replace ambiguous codons', 'ambiguous codons', 'codon alignment', 'FASTA', 'gap codons', 'sequencing ambiguity', 'phylogenetics']
    RETURN_TYPES = ('FASTA', 'TEXT')
    RETURN_NAMES = ('output', 'strike_ambigs_md_report')
    REQUIRED_EXECUTABLES = ['hyphy']
    DOCUMENTATION_URL = 'https://github.com/veg/hyphy/blob/master/res/TemplateBatchFiles'
    CITATION_DOIS = HYPHY_STRIKE_AMBIGS_CITATION_DOIS
    CITATION_URLS = [f'{DOI_URL}{doi}' for doi in HYPHY_STRIKE_AMBIGS_CITATION_DOIS]
    CITATION_TEXT = HYPHY_STRIKE_AMBIGS_CITATION_TEXT
    VERSION = '2.5.96'
    SHELL = True
    GENETIC_CODES = HyPhyABSRELNode.GENETIC_CODES

    @classmethod
    def _batch_file(cls, inputs: dict[str, Any]) -> str:
        return str(inputs.get('batch_file', '${HYPHY_STRIKE_AMBIGS_BF:-strike-ambigs.bf}') or 'strike-ambigs.bf')

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> str:
        out = _out(inputs)
        batch_file = cls._batch_file(inputs)
        batch_file_arg = batch_file if batch_file.startswith('${') else shlex.quote(batch_file)
        cmd = ['--alignment', str(inputs.get('alignment', '')), '--code', str(inputs.get('gencodeid', 'Universal') or 'Universal'), '--output', f'{out}/output.fasta', '>', f'{out}/strike_ambigs_stdout.md']
        return f'hyphy {batch_file_arg} {_shell_join(cmd)}'

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        out = Path(output_dir) / cls.NODE_ID
        out.mkdir(parents=True, exist_ok=True)
        return [out / 'output.fasta', out / 'strike_ambigs_stdout.md']

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        if not str(inputs.get('alignment', '')).strip():
            return 'HyPhy Strike-Ambigs alignment input is required'
        gencodeid = str(inputs.get('gencodeid', 'Universal') or 'Universal')
        if gencodeid not in cls.GENETIC_CODES:
            return f'Unsupported HyPhy genetic code: {gencodeid}'
        return True

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {'required': {'alignment': ('FASTA', {'description': 'In-frame codon alignment in FASTA format'})}, 'optional': {'gencodeid': ('STRING', {'default': 'Universal', 'options': cls.GENETIC_CODES, 'description': 'HyPhy genetic code for codon interpretation'})}, 'hidden': {'output': ('STRING', {})}}


class HyPhyBUSTEDNode(CommandNode):
    """Detect gene-wide episodic diversifying selection with HyPhy BUSTED."""
    NODE_ID = 'hyphy_busted'
    DISPLAY_NAME = 'HyPhy-BUSTED'
    REQUIRED_CONDA_PACKAGES = ['hyphy']
    CATEGORY = 'phylogeny'
    DESCRIPTION = 'Detect gene-wide episodic diversifying selection with HyPhy BUSTED.'
    SEARCH_ALIASES = [BIONODULO_BUILTIN_ALIAS, 'HyPhy', 'BUSTED', 'Branch-site Unrestricted Statistical Test', 'Bayesian UnresTricted Test of Episodic Diversification', 'episodic diversifying selection', 'gene-wide selection', 'positive selection', 'synonymous rate variation', 'multiple synonymous rate classes', 'phylogenetics']
    RETURN_TYPES = ('JSON', 'TEXT', 'PHYLOGENY_TREE')
    RETURN_NAMES = ('busted_output', 'busted_md_report', 'alternative_model')
    REQUIRED_EXECUTABLES = ['hyphy']
    DOCUMENTATION_URL = 'http://hyphy.org/methods/selection-methods/#busted'
    CITATION_DOIS = HYPHY_BUSTED_CITATION_DOIS
    CITATION_URLS = [f'{DOI_URL}{doi}' for doi in HYPHY_BUSTED_CITATION_DOIS]
    CITATION_TEXT = HYPHY_BUSTED_CITATION_TEXT
    VERSION = '2.5.96'
    SHELL = True
    GENETIC_CODES = HyPhyABSRELNode.GENETIC_CODES
    INPUT_EXTENSIONS = HyPhyABSRELNode.INPUT_EXTENSIONS
    BRANCH_SELECTIONS = HyPhyABSRELNode.BRANCH_SELECTIONS
    MULTIPLE_HITS = HyPhyABSRELNode.MULTIPLE_HITS
    KILL_ZERO_LENGTHS = HyPhyABSRELNode.KILL_ZERO_LENGTHS
    MSS_TYPES = ['Full', 'SynREV', 'SynREV2', 'SynREV2g', 'SynREVCodon', 'Random', 'Empirical', 'File', 'Codon-file']
    MSS_FILE_TYPES = {'Empirical', 'File', 'Codon-file'}
    MSS_NEUTRAL_TYPES = {'File', 'Codon-file'}

    @classmethod
    def _input_name(cls, inputs: dict[str, Any]) -> str:
        ext = str(inputs.get('input_ext', 'fasta')).strip().lstrip('.') or 'fasta'
        return f'input.{ext}'

    @classmethod
    def _branch_arg(cls, inputs: dict[str, Any]) -> str:
        branch_sel = str(inputs.get('branch_sel', 'All') or 'All')
        if branch_sel == 'specify':
            return str(inputs.get('branch_label', '')).strip()
        return branch_sel

    @staticmethod
    def _bool_value(value: Any) -> bool:
        if isinstance(value, str):
            return value.lower() in {'true', 'yes', '1', 'on'}
        return bool(value)

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> str:
        out = _out(inputs)
        input_name = cls._input_name(inputs)
        commands: list[str] = []
        if str(inputs.get('input_nhx', '')).strip():
            commands.append(_shell_join(['ln', '-s', str(inputs.get('input_nhx', '')), 'input.nhx']))
        commands.append(_shell_join(['ln', '-s', str(inputs.get('input_file', '')), input_name]))
        cmd = ['TOLERATE_NUMERICAL_ERRORS=1', 'hyphy', f"CPU={inputs.get('threads', 4)}", 'busted', '--alignment', f'./{input_name}']
        if str(inputs.get('input_nhx', '')).strip():
            cmd.extend(['--tree', 'input.nhx'])
        cmd.extend(['--code', str(inputs.get('gencodeid', 'Universal') or 'Universal'), '--branches', cls._branch_arg(inputs), '--output', f'{out}/busted_output.json', '--syn-rates', str(inputs.get('syn_rates', 3)), '--rates', str(inputs.get('rates', 3)), '--grid-size', str(inputs.get('grid_size', 250)), '--starting-points', str(inputs.get('starting_points', 1))])
        multiple_hits = str(inputs.get('multiple_hits', 'None') or 'None')
        if multiple_hits != 'None':
            cmd.extend(['--multiple-hits', multiple_hits])
        if cls._bool_value(inputs.get('error_sink', True)):
            cmd.extend(['--error-sink', 'Yes'])
        if cls._bool_value(inputs.get('save_alternative_model', False)):
            cmd.extend(['--save-fit', f'{out}/alternative_model.nhx'])
        if cls._bool_value(inputs.get('mss_enabled', False)):
            mss_type = str(inputs.get('mss_type', 'Full') or 'Full')
            cmd.extend(['--mss', 'Yes', '--mss-type', mss_type])
            if mss_type == 'Random':
                cmd.extend(['--mss-classes', str(inputs.get('mss_classes', 2))])
            if mss_type in cls.MSS_FILE_TYPES:
                cmd.extend(['--mss-file', str(inputs.get('mss_file', ''))])
            if mss_type in cls.MSS_NEUTRAL_TYPES:
                cmd.extend(['--mss-neutral', str(inputs.get('mss_neutral', 'neutral') or 'neutral')])
        cmd.extend(['--kill-zero-lengths', str(inputs.get('kill_zero_lengths', 'Yes') or 'Yes'), '>', f'{out}/busted_stdout.md'])
        commands.append(_shell_join(cmd))
        return ' && '.join(commands)

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        out = Path(output_dir) / cls.NODE_ID
        out.mkdir(parents=True, exist_ok=True)
        outputs = [out / 'busted_output.json', out / 'busted_stdout.md']
        if cls._bool_value(inputs.get('save_alternative_model', False)):
            outputs.append(out / 'alternative_model.nhx')
        return outputs

    @classmethod
    def _validate_int_range(cls, inputs: dict[str, Any], key: str, default: int, low: int, high: int, label: str) -> str | None:
        try:
            value = int(inputs.get(key, default))
        except (TypeError, ValueError):
            return f'HyPhy-BUSTED {label} must be between {low} and {high}'
        if value < low or value > high:
            return f'HyPhy-BUSTED {label} must be between {low} and {high}'
        return None

    @staticmethod
    def _validate_positive_int(value: Any, message: str) -> str | None:
        try:
            parsed = int(value)
        except (TypeError, ValueError):
            return message
        return message if parsed < 1 else None

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        if not str(inputs.get('input_file', '')).strip():
            return 'HyPhy-BUSTED alignment input is required'
        gencodeid = str(inputs.get('gencodeid', 'Universal') or 'Universal')
        if gencodeid not in cls.GENETIC_CODES:
            return f'Unsupported HyPhy genetic code: {gencodeid}'
        branch_sel = str(inputs.get('branch_sel', 'All') or 'All')
        if branch_sel not in cls.BRANCH_SELECTIONS:
            return f'Unsupported HyPhy-BUSTED branch selection: {branch_sel}'
        if branch_sel == 'specify' and (not str(inputs.get('branch_label', '')).strip()):
            return 'HyPhy-BUSTED custom branch selection requires a branch label'
        for key, default, low, high, label in [('syn_rates', 3, 1, 10, 'synonymous rate classes'), ('rates', 3, 2, 10, 'non-synonymous rate classes'), ('grid_size', 250, 1, 5000, 'grid size'), ('starting_points', 1, 1, 1000, 'starting points')]:
            message = cls._validate_int_range(inputs, key, default, low, high, label)
            if message:
                return message
        multiple_hits = str(inputs.get('multiple_hits', 'None') or 'None')
        if multiple_hits not in cls.MULTIPLE_HITS:
            return f'Unsupported HyPhy-BUSTED multiple-hits mode: {multiple_hits}'
        kill_zero_lengths = str(inputs.get('kill_zero_lengths', 'Yes') or 'Yes')
        if kill_zero_lengths not in cls.KILL_ZERO_LENGTHS:
            return f'Unsupported HyPhy-BUSTED zero-length branch handling: {kill_zero_lengths}'
        if cls._bool_value(inputs.get('mss_enabled', False)):
            if multiple_hits != 'None':
                return 'HyPhy-BUSTED MSS cannot be combined with multiple-hit correction'
            mss_type = str(inputs.get('mss_type', 'Full') or 'Full')
            if mss_type not in cls.MSS_TYPES:
                return f'Unsupported HyPhy-BUSTED MSS type: {mss_type}'
            if mss_type == 'Random':
                message = cls._validate_positive_int(inputs.get('mss_classes', 2), 'HyPhy-BUSTED MSS classes must be a positive integer')
                if message:
                    return message
            if mss_type in cls.MSS_FILE_TYPES and (not str(inputs.get('mss_file', '')).strip()):
                return f'HyPhy-BUSTED MSS file is required for {mss_type}'
            if mss_type in cls.MSS_NEUTRAL_TYPES and (not str(inputs.get('mss_neutral', 'neutral') or '').strip()):
                return 'HyPhy-BUSTED MSS neutral class is required'
        try:
            threads = int(inputs.get('threads', 4))
        except (TypeError, ValueError):
            return 'HyPhy-BUSTED threads must be a positive integer'
        if threads < 1:
            return 'HyPhy-BUSTED threads must be a positive integer'
        return True

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {'required': {'input_file': ('FASTA', {'description': 'Codon alignment in FASTA, compressed FASTA, or NEXUS format'})}, 'optional': {'input_nhx': ('FILE', {'default': '', 'description': 'Optional Newick/NHX phylogenetic tree'}), 'input_ext': ('STRING', {'default': 'fasta', 'options': cls.INPUT_EXTENSIONS, 'advanced': True}), 'gencodeid': ('STRING', {'default': 'Universal', 'options': cls.GENETIC_CODES, 'description': 'HyPhy genetic code for codon interpretation'}), 'branch_sel': ('STRING', {'default': 'All', 'options': cls.BRANCH_SELECTIONS, 'description': 'Branches to test for episodic diversifying selection'}), 'branch_label': ('STRING', {'default': '', 'description': 'Custom branch label when branch selection is specify'}), 'syn_rates': ('INT', {'default': 3, 'min': 1, 'max': 10, 'description': 'Synonymous rate classes'}), 'rates': ('INT', {'default': 3, 'min': 2, 'max': 10, 'description': 'Non-synonymous omega rate classes'}), 'grid_size': ('INT', {'default': 250, 'min': 1, 'max': 5000, 'description': 'Points in the initial distributional guess'}), 'starting_points': ('INT', {'default': 1, 'min': 1, 'max': 1000, 'description': 'Initial random guesses for rate optimization'}), 'multiple_hits': ('STRING', {'default': 'None', 'options': cls.MULTIPLE_HITS, 'description': 'Multiple-hit correction mode', 'advanced': True}), 'error_sink': ('BOOLEAN', {'default': True, 'description': 'Include a rate class for misalignment artifacts', 'advanced': True}), 'save_alternative_model': ('BOOLEAN', {'default': False, 'description': 'Save the alternative BUSTED model fit'}), 'mss_enabled': ('BOOLEAN', {'default': False, 'description': 'Enable multiple synonymous rate class substitution models', 'advanced': True}), 'mss_type': ('STRING', {'default': 'Full', 'options': cls.MSS_TYPES, 'description': 'Multiple synonymous substitution model type', 'advanced': True}), 'mss_classes': ('INT', {'default': 2, 'min': 1, 'description': 'Number of codon rate classes for Random MSS'}), 'mss_file': ('FILE', {'default': '', 'description': 'TSV file defining empirical rates or model partitions'}), 'mss_neutral': ('STRING', {'default': 'neutral', 'description': 'Neutral class designation for file-based MSS models'}), 'kill_zero_lengths': ('STRING', {'default': 'Yes', 'options': cls.KILL_ZERO_LENGTHS, 'description': 'Zero-length branch handling', 'advanced': True}), 'threads': ('INT', {'default': 4, 'min': 1, 'max': 128})}, 'hidden': {'output': ('STRING', {})}}


class HyPhyCFELNode(CommandNode):
    """Compare site-wise selective pressures among branch sets with HyPhy Contrast-FEL."""
    NODE_ID = 'hyphy_cfel'
    DISPLAY_NAME = 'HyPhy-CFEL'
    REQUIRED_CONDA_PACKAGES = ['hyphy']
    CATEGORY = 'phylogeny'
    DESCRIPTION = 'Test for site-wise selective pressure differences among clades or branch sets with HyPhy Contrast-FEL.'
    SEARCH_ALIASES = [BIONODULO_BUILTIN_ALIAS, 'HyPhy', 'CFEL', 'Contrast-FEL', 'Fixed Effects Likelihood', 'Contrast-FEL branch sets', 'branch sets', 'clade selection', 'selective pressure differences', 'site-wise selection', 'phylogenetics']
    RETURN_TYPES = ('JSON', 'TEXT')
    RETURN_NAMES = ('cfel_output', 'cfel_md_report')
    REQUIRED_EXECUTABLES = ['HYPHYMPI', 'mpirun']
    DOCUMENTATION_URL = 'http://www.hyphy.org/methods/other/contrast-fel/'
    CITATION_DOIS = HYPHY_CFEL_CITATION_DOIS
    CITATION_URLS = [f'{DOI_URL}{doi}' for doi in HYPHY_CFEL_CITATION_DOIS]
    CITATION_TEXT = HYPHY_CFEL_CITATION_TEXT
    VERSION = '2.5.96'
    SHELL = True
    GENETIC_CODES = HyPhyABSRELNode.GENETIC_CODES
    INPUT_EXTENSIONS = HyPhyABSRELNode.INPUT_EXTENSIONS
    KILL_ZERO_LENGTHS = HyPhyABSRELNode.KILL_ZERO_LENGTHS
    SRV_OPTIONS = ['Yes', 'No']

    @classmethod
    def _input_name(cls, inputs: dict[str, Any]) -> str:
        ext = str(inputs.get('input_ext', 'fasta')).strip().lstrip('.') or 'fasta'
        return f'input.{ext}'

    @staticmethod
    def _bool_yes_no(value: Any) -> str:
        if isinstance(value, str):
            return 'Yes' if value.lower() in {'true', 'yes', '1', 'on'} else 'No'
        return 'Yes' if bool(value) else 'No'

    @staticmethod
    def _mpirun_prefix(threads: Any) -> str:
        return f'${{GALAXY_MPIRUN:-mpirun --allow-run-as-root --oversubscribe -mca orte_tmpdir_base "${{TMPDIR:-.}}" -np {threads}}}'

    @classmethod
    def _branch_sets(cls, inputs: dict[str, Any]) -> list[str]:
        values = _as_list(inputs.get('branch_sets', inputs.get('branch_labels', ['Test'])))
        return values or ['Test']

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> str:
        out = _out(inputs)
        input_name = cls._input_name(inputs)
        commands: list[str] = []
        if str(inputs.get('input_nhx', '')).strip():
            commands.append(_shell_join(['ln', '-s', str(inputs.get('input_nhx', '')), 'input.nhx']))
        commands.append(_shell_join(['ln', '-s', str(inputs.get('input_file', '')), input_name]))
        cmd = ['--alignment', input_name]
        if str(inputs.get('input_nhx', '')).strip():
            cmd.extend(['--tree', 'input.nhx'])
        cmd.extend(['--code', str(inputs.get('gencodeid', 'Universal') or 'Universal')])
        for branch_set in cls._branch_sets(inputs):
            cmd.extend(['--branch-set', branch_set])
        cmd.extend(['--srv', str(inputs.get('srv', 'Yes') or 'Yes'), '--permutations', cls._bool_yes_no(inputs.get('permutations', False)), '--pvalue', str(inputs.get('pvalue', 0.05)), '--qvalue', str(inputs.get('qvalue', 0.2))])
        _add_if_value(cmd, '--limit-to-sites', inputs.get('limit_to_sites'))
        _add_if_value(cmd, '--save-lf-for-sites', inputs.get('save_lf_for_sites'))
        if cls._bool_yes_no(inputs.get('intermediate_fits', False)) == 'Yes':
            cmd.extend(['--intermediate-fits', f'{out}/intermediate_fits.json'])
        cmd.extend(['--kill-zero-lengths', str(inputs.get('kill_zero_lengths', 'Yes') or 'Yes'), '--output', f'{out}/cfel_output.json', '>', f'{out}/cfel_stdout.md'])
        commands.append(f"{cls._mpirun_prefix(inputs.get('threads', 4))} HYPHYMPI contrast-fel {_shell_join(cmd)}")
        return ' && '.join(commands)

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        out = Path(output_dir) / cls.NODE_ID
        out.mkdir(parents=True, exist_ok=True)
        return [out / 'cfel_output.json', out / 'cfel_stdout.md']

    @staticmethod
    def _validate_unit_float(value: Any, message: str) -> str | None:
        try:
            parsed = float(value)
        except (TypeError, ValueError):
            return message
        return message if parsed < 0 or parsed > 1 else None

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        if not str(inputs.get('input_file', '')).strip():
            return 'HyPhy-CFEL alignment input is required'
        gencodeid = str(inputs.get('gencodeid', 'Universal') or 'Universal')
        if gencodeid not in cls.GENETIC_CODES:
            return f'Unsupported HyPhy genetic code: {gencodeid}'
        raw_branch_sets = inputs.get('branch_sets', inputs.get('branch_labels', ['Test']))
        branch_sets = [str(value) for value in raw_branch_sets] if isinstance(raw_branch_sets, (list, tuple)) else _as_list(raw_branch_sets)
        if not branch_sets:
            return 'HyPhy-CFEL requires at least one branch set'
        if any((not branch_set.strip() for branch_set in branch_sets)):
            return 'HyPhy-CFEL branch set labels must be non-empty'
        srv = str(inputs.get('srv', 'Yes') or 'Yes')
        if srv not in cls.SRV_OPTIONS:
            return f'Unsupported HyPhy-CFEL synonymous rate variation setting: {srv}'
        message = cls._validate_unit_float(inputs.get('pvalue', 0.05), 'HyPhy-CFEL p-value threshold must be between 0 and 1')
        if message:
            return message
        message = cls._validate_unit_float(inputs.get('qvalue', 0.2), 'HyPhy-CFEL q-value threshold must be between 0 and 1')
        if message:
            return message
        kill_zero_lengths = str(inputs.get('kill_zero_lengths', 'Yes') or 'Yes')
        if kill_zero_lengths not in cls.KILL_ZERO_LENGTHS:
            return f'Unsupported HyPhy-CFEL zero-length branch handling: {kill_zero_lengths}'
        try:
            threads = int(inputs.get('threads', 4))
        except (TypeError, ValueError):
            return 'HyPhy-CFEL threads must be a positive integer'
        if threads < 1:
            return 'HyPhy-CFEL threads must be a positive integer'
        return True

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {'required': {'input_file': ('FASTA', {'description': 'Codon alignment in FASTA, compressed FASTA, or NEXUS format'})}, 'optional': {'input_nhx': ('FILE', {'default': '', 'description': 'Optional Newick/NHX phylogenetic tree'}), 'input_ext': ('STRING', {'default': 'fasta', 'options': cls.INPUT_EXTENSIONS, 'advanced': True}), 'gencodeid': ('STRING', {'default': 'Universal', 'options': cls.GENETIC_CODES, 'description': 'HyPhy genetic code for codon interpretation'}), 'branch_sets': ('STRING', {'default': ['Test'], 'multiple': True, 'description': 'Branch-set labels to compare, including tree labels or built-in branch sets'}), 'pvalue': ('FLOAT', {'default': 0.05, 'min': 0, 'max': 1, 'description': 'Significance threshold for site tests'}), 'qvalue': ('FLOAT', {'default': 0.2, 'min': 0, 'max': 1, 'description': 'False discovery rate reporting threshold'}), 'srv': ('STRING', {'default': 'Yes', 'options': cls.SRV_OPTIONS, 'description': 'Include synonymous rate variation'}), 'permutations': ('BOOLEAN', {'default': False, 'description': 'Perform permutation significance tests'}), 'limit_to_sites': ('STRING', {'default': '', 'description': 'Comma/range list of 1-based sites to analyze'}), 'save_lf_for_sites': ('STRING', {'default': '', 'description': 'Comma/range list of sites for likelihood-function snapshots'}), 'intermediate_fits': ('BOOLEAN', {'default': False, 'description': 'Save intermediate initial-guess model fits'}), 'kill_zero_lengths': ('STRING', {'default': 'Yes', 'options': cls.KILL_ZERO_LENGTHS, 'description': 'Zero-length branch handling', 'advanced': True}), 'threads': ('INT', {'default': 4, 'min': 1, 'max': 128})}, 'hidden': {'output': ('STRING', {})}}


class HyPhyCONVNode(CommandNode):
    """Translate in-frame codon alignments to protein alignments with HyPhy CONV."""
    NODE_ID = 'hyphy_conv'
    DISPLAY_NAME = 'HyPhy-Conv'
    REQUIRED_CONDA_PACKAGES = ['hyphy']
    CATEGORY = 'phylogeny'
    DESCRIPTION = 'Translate an in-frame codon alignment to proteins with HyPhy CONV.'
    SEARCH_ALIASES = [BIONODULO_BUILTIN_ALIAS, 'HyPhy', 'CONV', 'CodonToProtein', 'codon to protein', 'translate codon alignment', 'amino acid translation', 'CodonToProtein amino acid translation', 'protein alignment', 'keep deletions', 'skip deletions', 'phylogenetics']
    RETURN_TYPES = ('FILE',)
    RETURN_NAMES = ('proteins',)
    REQUIRED_EXECUTABLES = ['hyphy']
    DOCUMENTATION_URL = 'https://github.com/veg/hyphy/blob/master/res/TemplateBatchFiles/CodonToProtein.bf'
    CITATION_DOIS = [HYPHY_CITATION_DOI]
    CITATION_URLS = [f'{DOI_URL}{HYPHY_CITATION_DOI}']
    CITATION_TEXT = HYPHY_CITATION_TEXT
    VERSION = '2.5.96'
    SHELL = True
    GENETIC_CODES = HyPhyABSRELNode.GENETIC_CODES
    DELETION_MODES = ['Keep Deletions', 'Skip Deletions']

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> str:
        out = _out(inputs)
        deletions = str(inputs.get('deletions', 'Skip Deletions') or 'Skip Deletions')
        commands = [_shell_join(['cp', str(inputs.get('input_file', '')), 'conv_input.fa'])]
        cmd = ['hyphy', 'conv', str(inputs.get('gencodeid', 'Universal') or 'Universal'), deletions, 'conv_input.fa', f'{out}/proteins.nex']
        commands.append("ENV='TOLERATE_NUMERICAL_ERRORS=1;' " + _shell_join(cmd))
        return ' && '.join(commands)

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        out = Path(output_dir) / cls.NODE_ID
        out.mkdir(parents=True, exist_ok=True)
        return [out / 'proteins.nex']

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        if not str(inputs.get('input_file', '')).strip():
            return 'HyPhy-Conv codon alignment input is required'
        gencodeid = str(inputs.get('gencodeid', 'Universal') or 'Universal')
        if gencodeid not in cls.GENETIC_CODES:
            return f'Unsupported HyPhy genetic code: {gencodeid}'
        deletions = str(inputs.get('deletions', 'Skip Deletions') or 'Skip Deletions')
        if deletions not in cls.DELETION_MODES:
            return f'Unsupported HyPhy-Conv deletion handling: {deletions}'
        return True

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {'required': {'input_file': ('FASTA', {'description': 'In-frame codon alignment in FASTA format'})}, 'optional': {'gencodeid': ('STRING', {'default': 'Universal', 'options': cls.GENETIC_CODES, 'description': 'HyPhy genetic code for codon interpretation'}), 'deletions': ('STRING', {'default': 'Skip Deletions', 'options': cls.DELETION_MODES, 'description': 'Whether translated deletion sites are retained in the protein alignment'})}, 'hidden': {'output': ('STRING', {})}}


class HyPhyCLNNode(CommandNode):
    """Clean and normalize codon alignments with HyPhy CLN."""
    NODE_ID = 'hyphy_cln'
    DISPLAY_NAME = 'HyPhy-CLN'
    REQUIRED_CONDA_PACKAGES = ['hyphy']
    CATEGORY = 'phylogeny'
    DESCRIPTION = 'Clean and normalize codon alignments with HyPhy CLN.'
    SEARCH_ALIASES = [BIONODULO_BUILTIN_ALIAS, 'HyPhy', 'CLN', 'CleanStopCodons', 'CleanStopCodons duplicate sequences', 'clean alignment', 'normalize alignment', 'duplicate sequences', 'gap-only sites', 'stop codons', 'sequence identifiers', 'phylogenetics']
    RETURN_TYPES = ('FASTA',)
    RETURN_NAMES = ('cleaned_alignment',)
    REQUIRED_EXECUTABLES = ['hyphy']
    DOCUMENTATION_URL = 'https://github.com/veg/hyphy/blob/master/res/TemplateBatchFiles/CleanStopCodons.bf'
    CITATION_DOIS = [HYPHY_CITATION_DOI]
    CITATION_URLS = [f'{DOI_URL}{HYPHY_CITATION_DOI}']
    CITATION_TEXT = HYPHY_CITATION_TEXT
    VERSION = '2.5.96'
    SHELL = True
    GENETIC_CODES = HyPhyABSRELNode.GENETIC_CODES
    INPUT_EXTENSIONS = ['fasta', 'fasta.gz', 'nex', 'nexus', 'phylip', 'mega']
    FILTERING_METHODS = ['No/No', 'No/Yes', 'Yes/No', 'Yes/Yes', 'Disallow stops']

    @classmethod
    def _input_name(cls, inputs: dict[str, Any]) -> str:
        ext = str(inputs.get('input_ext', 'fasta')).strip().lstrip('.') or 'fasta'
        return f'input.{ext}'

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> str:
        out = _out(inputs)
        input_name = cls._input_name(inputs)
        commands = [_shell_join(['ln', '-s', str(inputs.get('input_file', '')), input_name])]
        cmd = ['hyphy', f"CPU={inputs.get('threads', 4)}", 'cln', '--alignment', input_name, '--code', str(inputs.get('gencodeid', 'Universal') or 'Universal'), '--filtering-method', str(inputs.get('filtering_method', 'No/No') or 'No/No'), '--output', f'{out}/cleaned_alignment.fasta']
        commands.append(_shell_join(cmd))
        return ' && '.join(commands)

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        out = Path(output_dir) / cls.NODE_ID
        out.mkdir(parents=True, exist_ok=True)
        return [out / 'cleaned_alignment.fasta']

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        if not str(inputs.get('input_file', '')).strip():
            return 'HyPhy-CLN alignment input is required'
        input_ext = str(inputs.get('input_ext', 'fasta') or 'fasta').strip().lstrip('.')
        if input_ext not in cls.INPUT_EXTENSIONS:
            return f'Unsupported HyPhy-CLN input extension: {input_ext}'
        gencodeid = str(inputs.get('gencodeid', 'Universal') or 'Universal')
        if gencodeid not in cls.GENETIC_CODES:
            return f'Unsupported HyPhy genetic code: {gencodeid}'
        filtering_method = str(inputs.get('filtering_method', 'No/No') or 'No/No')
        if filtering_method not in cls.FILTERING_METHODS:
            return f'Unsupported HyPhy-CLN filtering method: {filtering_method}'
        try:
            threads = int(inputs.get('threads', 4))
        except (TypeError, ValueError):
            return 'HyPhy-CLN threads must be a positive integer'
        if threads < 1:
            return 'HyPhy-CLN threads must be a positive integer'
        return True

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {'required': {'input_file': ('FASTA', {'description': 'In-frame codon alignment in FASTA, compressed FASTA, NEXUS, PHYLIP, or MEGA format'})}, 'optional': {'input_ext': ('STRING', {'default': 'fasta', 'options': cls.INPUT_EXTENSIONS, 'advanced': True}), 'gencodeid': ('STRING', {'default': 'Universal', 'options': cls.GENETIC_CODES, 'description': 'HyPhy genetic code for codon interpretation'}), 'filtering_method': ('STRING', {'default': 'No/No', 'options': cls.FILTERING_METHODS, 'description': 'How to filter duplicate sequences, gap-only sites, and stop codons'}), 'threads': ('INT', {'default': 4, 'min': 1, 'max': 128})}, 'hidden': {'output': ('STRING', {})}}
