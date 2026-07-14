"""vsearch — metagenomics node(s). One tool per file (extracted from wrapped_amplicon_trimming.py)."""
from __future__ import annotations
from bionodulo.nodes.builtin._wrapped_tool_utils import *


class VSearchSearchNode(CommandNode):
    """Search query sequences against a FASTA database with VSEARCH."""
    NODE_ID = 'vsearch_search'
    DISPLAY_NAME = 'VSEARCH Search'
    REQUIRED_CONDA_PACKAGES = ['vsearch']
    CATEGORY = 'metagenomics'
    DESCRIPTION = 'Search amplicon or nucleotide sequences against a reference database with VSEARCH.'
    SEARCH_ALIASES = [BIONODULO_BUILTIN_ALIAS, 'vsearch', 'usearch_global', 'search', 'amplicon', 'otu']
    RETURN_TYPES = ('TSV', 'STATS_FILE', 'FASTA')
    RETURN_NAMES = ('matches', 'alignments', 'unmatched')
    REQUIRED_EXECUTABLES = ['vsearch']
    DOCUMENTATION_URL = 'https://github.com/torognes/vsearch'
    CITATION_DOIS = ['10.7717/peerj.2584']
    CITATION_URLS = ['https://doi.org/10.7717/peerj.2584']
    CITATION_TEXT = 'VSEARCH: a versatile open source tool for metagenomics.'
    VERSION = '2.8.3'

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        cmd = ['vsearch', f"--{inputs.get('search_mode', 'usearch_global')}", str(inputs.get('query', '')), '--db', str(inputs.get('database', '')), '--id', str(inputs.get('identity', 0.97)), '--strand', str(inputs.get('strand', 'both')), '--maxaccepts', str(inputs.get('maxaccepts', 1)), '--maxrejects', str(inputs.get('maxrejects', 32)), '--threads', str(inputs.get('threads', 1)), '--blast6out', f'{_out(inputs)}/matches.tsv', '--alnout', f'{_out(inputs)}/alignments.txt', '--notmatched', f'{_out(inputs)}/unmatched.fasta']
        return cmd

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        out = Path(output_dir) / cls.NODE_ID
        out.mkdir(parents=True, exist_ok=True)
        return [out / 'matches.tsv', out / 'alignments.txt', out / 'unmatched.fasta']

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {'required': {'query': ('FASTA', {'description': 'Query sequences'}), 'database': ('FASTA', {'description': 'Reference database FASTA'})}, 'optional': {'search_mode': ('STRING', {'default': 'usearch_global', 'options': ['usearch_global', 'search_exact']}), 'identity': ('FLOAT', {'default': 0.97, 'min': 0, 'max': 1}), 'strand': ('STRING', {'default': 'both', 'options': ['plus', 'both']}), 'maxaccepts': ('INT', {'default': 1, 'min': 0, 'advanced': True}), 'maxrejects': ('INT', {'default': 32, 'min': 0, 'advanced': True}), 'threads': ('INT', {'default': 1, 'min': 1, 'max': 128, 'display': 'slider'})}, 'hidden': {'output': ('STRING', {})}}


class VSearchClusterNode(CommandNode):
    """Cluster sequences into centroids and UC cluster assignments with VSEARCH."""
    NODE_ID = 'vsearch_cluster'
    DISPLAY_NAME = 'VSEARCH Cluster'
    REQUIRED_CONDA_PACKAGES = ['vsearch']
    CATEGORY = 'metagenomics'
    DESCRIPTION = 'Cluster amplicon sequences with VSEARCH cluster_fast or cluster_size modes.'
    SEARCH_ALIASES = [BIONODULO_BUILTIN_ALIAS, 'vsearch', 'cluster_fast', 'cluster_size', 'otu clustering', 'centroids']
    RETURN_TYPES = ('FASTA', 'TSV')
    RETURN_NAMES = ('centroids', 'clusters_uc')
    REQUIRED_EXECUTABLES = ['vsearch']
    DOCUMENTATION_URL = 'https://github.com/torognes/vsearch'
    CITATION_DOIS = ['10.7717/peerj.2584']
    CITATION_URLS = ['https://doi.org/10.7717/peerj.2584']
    CITATION_TEXT = 'VSEARCH: a versatile open source tool for metagenomics.'
    VERSION = '2.8.3'

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        cmd = ['vsearch', f"--{inputs.get('cluster_mode', 'cluster_fast')}", str(inputs.get('sequences', '')), '--id', str(inputs.get('identity', 0.97)), '--strand', str(inputs.get('strand', 'plus'))]
        if inputs.get('sizein'):
            cmd.append('--sizein')
        if inputs.get('sizeout'):
            cmd.append('--sizeout')
        cmd.extend(['--threads', str(inputs.get('threads', 1)), '--centroids', f'{_out(inputs)}/centroids.fasta', '--uc', f'{_out(inputs)}/clusters.uc'])
        return cmd

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        out = Path(output_dir) / cls.NODE_ID
        out.mkdir(parents=True, exist_ok=True)
        return [out / 'centroids.fasta', out / 'clusters.uc']

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {'required': {'sequences': ('FASTA', {'description': 'Sequences to cluster'})}, 'optional': {'cluster_mode': ('STRING', {'default': 'cluster_fast', 'options': ['cluster_fast', 'cluster_size', 'cluster_smallmem']}), 'identity': ('FLOAT', {'default': 0.97, 'min': 0, 'max': 1}), 'strand': ('STRING', {'default': 'plus', 'options': ['plus', 'both']}), 'sizein': ('BOOLEAN', {'default': False, 'advanced': True}), 'sizeout': ('BOOLEAN', {'default': False, 'advanced': True}), 'threads': ('INT', {'default': 1, 'min': 1, 'max': 128, 'display': 'slider'})}, 'hidden': {'output': ('STRING', {})}}


class VSearchDereplicationNode(CommandNode):
    """Dereplicate identical FASTA sequences with VSEARCH."""
    NODE_ID = 'vsearch_dereplication'
    DISPLAY_NAME = 'VSEARCH Dereplication'
    REQUIRED_CONDA_PACKAGES = ['vsearch']
    CATEGORY = 'metagenomics'
    DESCRIPTION = 'Dereplicate identical FASTA sequences with VSEARCH derep_fulllength and optional abundance filters.'
    SEARCH_ALIASES = [BIONODULO_BUILTIN_ALIAS, 'vsearch', 'dereplication', 'derep_fulllength', 'amplicon dereplication', 'unique sequences', 'abundance']
    RETURN_TYPES = ('FASTA', 'TSV')
    RETURN_NAMES = ('dereplicated_sequences', 'uclust_output')
    REQUIRED_EXECUTABLES = ['vsearch']
    DOCUMENTATION_URL = 'https://github.com/torognes/vsearch'
    CITATION_DOIS = ['10.7717/peerj.2584']
    CITATION_URLS = ['https://doi.org/10.7717/peerj.2584']
    CITATION_TEXT = 'VSEARCH: a versatile open source tool for metagenomics.'
    VERSION = '2.8.3'

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        cmd = ['vsearch', '--threads', str(inputs.get('threads', 4)), '--notrunclabels', '--derep_fulllength', str(inputs.get('infile', inputs.get('sequences', '')))]
        _add_if_value(cmd, '--maxuniquesize', inputs.get('maxuniquesize'))
        _add_if_value(cmd, '--minuniquesize', inputs.get('minuniquesize'))
        cmd.extend(['--output', f'{_out(inputs)}/dereplicated.fasta'])
        if inputs.get('sizein'):
            cmd.append('--sizein')
        if inputs.get('sizeout'):
            cmd.append('--sizeout')
        cmd.extend(['--strand', str(inputs.get('strand', 'plus'))])
        _add_if_value(cmd, '--topn', inputs.get('topn'))
        if inputs.get('uc'):
            cmd.extend(['--uc', f'{_out(inputs)}/dereplication.uc'])
        return cmd

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        out = Path(output_dir) / cls.NODE_ID
        out.mkdir(parents=True, exist_ok=True)
        outputs = [out / 'dereplicated.fasta']
        if inputs.get('uc'):
            outputs.append(out / 'dereplication.uc')
        return outputs

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {'required': {'infile': ('FASTA', {'description': 'FASTA sequences to dereplicate'})}, 'optional': {'topn': ('INT', {'default': '', 'min': 1, 'description': 'Output only the n most abundant sequences'}), 'sizein': ('BOOLEAN', {'default': False, 'description': 'Read abundance annotations from input'}), 'sizeout': ('BOOLEAN', {'default': False, 'description': 'Write abundance annotations to output'}), 'strand': ('STRING', {'default': 'plus', 'options': ['plus', 'both']}), 'uc': ('BOOLEAN', {'default': False, 'description': 'Write UCLUST-like dereplication assignments'}), 'minuniquesize': ('INT', {'default': '', 'min': 1, 'description': 'Minimum abundance to output'}), 'maxuniquesize': ('INT', {'default': '', 'min': 1, 'description': 'Maximum abundance to output'}), 'threads': ('INT', {'default': 4, 'min': 1, 'max': 128, 'display': 'slider'})}, 'hidden': {'output': ('STRING', {})}}


class VSearchMaskingNode(CommandNode):
    """Mask FASTA sequences with VSEARCH."""
    NODE_ID = 'vsearch_masking'
    DISPLAY_NAME = 'VSEARCH Masking'
    REQUIRED_CONDA_PACKAGES = ['vsearch']
    CATEGORY = 'metagenomics'
    DESCRIPTION = 'Mask FASTA sequences with VSEARCH maskfasta using dust, soft, or no qmask modes and optional hard masking.'
    SEARCH_ALIASES = [BIONODULO_BUILTIN_ALIAS, 'vsearch', 'masking', 'maskfasta', 'qmask', 'hardmask', 'soft masking', 'dust masking']
    RETURN_TYPES = ('FASTA',)
    RETURN_NAMES = ('masked_sequences',)
    REQUIRED_EXECUTABLES = ['vsearch']
    DOCUMENTATION_URL = 'https://github.com/torognes/vsearch'
    CITATION_DOIS = ['10.7717/peerj.2584']
    CITATION_URLS = ['https://doi.org/10.7717/peerj.2584']
    CITATION_TEXT = 'VSEARCH: a versatile open source tool for metagenomics.'
    VERSION = '2.8.3'

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        cmd = ['vsearch', '--threads', str(inputs.get('threads', 4)), '--notrunclabels']
        qmask = str(inputs.get('qmask', 'dust'))
        if qmask != 'none':
            cmd.extend(['--qmask', qmask])
        if inputs.get('hardmask'):
            cmd.append('--hardmask')
        cmd.extend(['--maskfasta', str(inputs.get('infile', inputs.get('sequences', ''))), '--output', f'{_out(inputs)}/masked.fasta'])
        return cmd

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        out = Path(output_dir) / cls.NODE_ID
        out.mkdir(parents=True, exist_ok=True)
        return [out / 'masked.fasta']

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {'required': {'infile': ('FASTA', {'description': 'FASTA sequences to mask'})}, 'optional': {'qmask': ('STRING', {'default': 'dust', 'options': ['none', 'dust', 'soft'], 'description': 'Masking mode'}), 'hardmask': ('BOOLEAN', {'default': False, 'description': 'Replace masked bases with N instead of lowercase'}), 'threads': ('INT', {'default': 4, 'min': 1, 'max': 128, 'display': 'slider'})}, 'hidden': {'output': ('STRING', {})}}


class VSearchShufflingNode(CommandNode):
    """Shuffle FASTA sequence order with VSEARCH."""
    NODE_ID = 'vsearch_shuffling'
    DISPLAY_NAME = 'VSEARCH Shuffling'
    REQUIRED_CONDA_PACKAGES = ['vsearch']
    CATEGORY = 'metagenomics'
    DESCRIPTION = 'Shuffle FASTA sequence order pseudo-randomly with VSEARCH, using an explicit random seed and optional top-N limit.'
    SEARCH_ALIASES = [BIONODULO_BUILTIN_ALIAS, 'vsearch', 'shuffling', 'shuffle', 'random sequence order', 'randseed', 'topn']
    RETURN_TYPES = ('FASTA',)
    RETURN_NAMES = ('shuffled_sequences',)
    REQUIRED_EXECUTABLES = ['vsearch']
    DOCUMENTATION_URL = 'https://github.com/torognes/vsearch'
    CITATION_DOIS = ['10.7717/peerj.2584']
    CITATION_URLS = ['https://doi.org/10.7717/peerj.2584']
    CITATION_TEXT = 'VSEARCH: a versatile open source tool for metagenomics.'
    VERSION = '2.8.3'

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        cmd = ['vsearch', '--threads', str(inputs.get('threads', 4)), '--notrunclabels', '--output', f'{_out(inputs)}/shuffled.fasta', '--randseed', str(inputs.get('randseed', 0)), '--shuffle', str(inputs.get('infile', inputs.get('sequences', '')))]
        _add_if_value(cmd, '--topn', inputs.get('topn'))
        return cmd

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        out = Path(output_dir) / cls.NODE_ID
        out.mkdir(parents=True, exist_ok=True)
        return [out / 'shuffled.fasta']

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {'required': {'infile': ('FASTA', {'description': 'FASTA sequences to shuffle'})}, 'optional': {'randseed': ('INT', {'default': 0, 'min': 0, 'description': 'Random seed; zero uses a random data source'}), 'topn': ('INT', {'default': '', 'min': 1, 'description': 'Output only the first n sequences after shuffling'}), 'threads': ('INT', {'default': 4, 'min': 1, 'max': 128, 'display': 'slider'})}, 'hidden': {'output': ('STRING', {})}}


class VSearchSortingNode(CommandNode):
    """Sort FASTA sequences by length or abundance with VSEARCH."""
    NODE_ID = 'vsearch_sorting'
    DISPLAY_NAME = 'VSEARCH Sorting'
    REQUIRED_CONDA_PACKAGES = ['vsearch']
    CATEGORY = 'metagenomics'
    DESCRIPTION = 'Sort FASTA sequences by length or abundance with VSEARCH, with optional abundance filters, relabeling, size annotations, and top-N output.'
    SEARCH_ALIASES = [BIONODULO_BUILTIN_ALIAS, 'vsearch', 'sorting', 'sortbylength', 'sortbysize', 'sort by abundance', 'sizeout', 'relabel']
    RETURN_TYPES = ('FASTA',)
    RETURN_NAMES = ('sorted_sequences',)
    REQUIRED_EXECUTABLES = ['vsearch']
    DOCUMENTATION_URL = 'https://github.com/torognes/vsearch'
    CITATION_DOIS = ['10.7717/peerj.2584']
    CITATION_URLS = ['https://doi.org/10.7717/peerj.2584']
    CITATION_TEXT = 'VSEARCH: a versatile open source tool for metagenomics.'
    VERSION = '2.8.3'

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        cmd = ['vsearch', '--threads', str(inputs.get('threads', 4)), '--notrunclabels']
        sorting_mode = str(inputs.get('sorting_mode', inputs.get('sorting_mode_select', 'sortbylength')))
        if sorting_mode == 'sortbylength':
            cmd.extend(['--sortbylength', str(inputs.get('infile', inputs.get('sequences', '')))])
        else:
            cmd.extend(['--sortbysize', str(inputs.get('infile', inputs.get('sequences', '')))])
            _add_if_value(cmd, '--minsize', inputs.get('minsize'))
            _add_if_value(cmd, '--maxsize', inputs.get('maxsize'))
        cmd.extend(['--output', f'{_out(inputs)}/sorted.fasta'])
        _add_if_value(cmd, '--relabel', inputs.get('relabel'))
        if inputs.get('sizeout'):
            cmd.append('--sizeout')
        _add_if_value(cmd, '--topn', inputs.get('topn'))
        return cmd

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        out = Path(output_dir) / cls.NODE_ID
        out.mkdir(parents=True, exist_ok=True)
        return [out / 'sorted.fasta']

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {'required': {'infile': ('FASTA', {'description': 'FASTA sequences to sort'})}, 'optional': {'sorting_mode': ('STRING', {'default': 'sortbylength', 'options': ['sortbylength', 'sortbyabundance']}), 'minsize': ('INT', {'default': '', 'min': 1, 'description': 'Minimum abundance for sort-by-size mode'}), 'maxsize': ('INT', {'default': '', 'min': 1, 'description': 'Maximum abundance for sort-by-size mode'}), 'relabel': ('STRING', {'default': '', 'description': 'Prefix used to relabel sequences after sorting'}), 'sizeout': ('BOOLEAN', {'default': False, 'description': 'Add abundance annotations to output'}), 'topn': ('INT', {'default': '', 'min': 1, 'description': 'Output only the top n sorted sequences'}), 'threads': ('INT', {'default': 4, 'min': 1, 'max': 128, 'display': 'slider'})}, 'hidden': {'output': ('STRING', {})}}


class VSearchAlignmentNode(CommandNode):
    """Compute all-pairs global alignments with VSEARCH."""
    NODE_ID = 'vsearch_alignment'
    DISPLAY_NAME = 'VSEARCH Alignment'
    REQUIRED_CONDA_PACKAGES = ['vsearch']
    CATEGORY = 'metagenomics'
    DESCRIPTION = 'Compute all-pairs global alignments for FASTA sequences with VSEARCH and optional tabular user fields.'
    SEARCH_ALIASES = [BIONODULO_BUILTIN_ALIAS, 'vsearch', 'alignment', 'allpairs_global', 'pairwise alignment', 'alnout', 'userfields']
    RETURN_TYPES = ('STATS_FILE', 'TSV')
    RETURN_NAMES = ('alignments', 'userfields')
    REQUIRED_EXECUTABLES = ['vsearch']
    DOCUMENTATION_URL = 'https://github.com/torognes/vsearch'
    CITATION_DOIS = ['10.7717/peerj.2584']
    CITATION_URLS = ['https://doi.org/10.7717/peerj.2584']
    CITATION_TEXT = 'VSEARCH: a versatile open source tool for metagenomics.'
    VERSION = '2.8.3'

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        cmd = ['vsearch', '--threads', str(inputs.get('threads', 4)), '--notrunclabels']
        if inputs.get('acceptall'):
            cmd.append('--acceptall')
        cmd.extend(['--id', str(inputs.get('id', inputs.get('identity', 0.97))), '--iddef', str(inputs.get('iddef', 2)), '--allpairs_global', str(inputs.get('infile', inputs.get('sequences', ''))), '--alnout', f'{_out(inputs)}/alignments.txt'])
        _add_if_value(cmd, '--query_cov', inputs.get('query_cov'))
        if inputs.get('userfields_output_select') == 'yes':
            userfields = _as_list(inputs.get('userfields'))
            if not userfields:
                userfields = ['query', 'target']
            cmd.extend(['--userfields', '+'.join(userfields), '--userout', f'{_out(inputs)}/userfields.tsv'])
        return cmd

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        out = Path(output_dir) / cls.NODE_ID
        out.mkdir(parents=True, exist_ok=True)
        outputs = [out / 'alignments.txt']
        if inputs.get('userfields_output_select') == 'yes':
            outputs.append(out / 'userfields.tsv')
        return outputs

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {'required': {'infile': ('FASTA', {'description': 'FASTA sequences for all-pairs global alignment'})}, 'optional': {'id': ('FLOAT', {'default': 0.97, 'min': 0, 'max': 1, 'description': 'Minimum pairwise identity'}), 'iddef': ('STRING', {'default': '2', 'options': ['0', '1', '2', '3', '4'], 'description': 'VSEARCH identity definition'}), 'acceptall': ('BOOLEAN', {'default': False, 'description': 'Output all pairwise alignments'}), 'query_cov': ('FLOAT', {'default': '', 'min': 0, 'max': 1, 'description': 'Minimum aligned query fraction'}), 'userfields_output_select': ('STRING', {'default': 'no', 'options': ['no', 'yes'], 'description': 'Write tabular user fields'}), 'userfields': ('STRING', {'default': ['query', 'target'], 'list': True, 'options': ['aln', 'alnlen', 'bits', 'caln', 'evalue', 'exts', 'gaps', 'id', 'id0', 'id1', 'id2', 'id3', 'id4', 'ids', 'mism', 'opens', 'pairs', 'pctgaps', 'pctpv', 'pv', 'qcov', 'qframe', 'qhi', 'qihi', 'qilo', 'ql', 'qlo', 'qrow', 'qs', 'qstrand', 'query', 'raw', 'target', 'tcov', 'tframe', 'thi', 'tihi', 'tilo', 'tl', 'tlo', 'trow', 'ts', 'tstrand'], 'description': 'Fields for optional tabular VSEARCH output'}), 'threads': ('INT', {'default': 4, 'min': 1, 'max': 128, 'display': 'slider'})}, 'hidden': {'output': ('STRING', {})}}


class VSearchChimeraDetectionNode(CommandNode):
    """Detect chimeric FASTA sequences with VSEARCH UCHIME modes."""
    NODE_ID = 'vsearch_chimera_detection'
    DISPLAY_NAME = 'VSEARCH Chimera Detection'
    REQUIRED_CONDA_PACKAGES = ['vsearch']
    CATEGORY = 'metagenomics'
    DESCRIPTION = 'Detect chimeric FASTA sequences with VSEARCH uchime_denovo or uchime_ref and optional UCHIME reports.'
    SEARCH_ALIASES = [BIONODULO_BUILTIN_ALIAS, 'vsearch', 'chimera', 'chimera detection', 'uchime_denovo', 'uchime_ref', 'uchimeout', 'nonchimeras']
    RETURN_TYPES = ('FASTA', 'FASTA', 'STATS_FILE', 'TSV')
    RETURN_NAMES = ('chimeras', 'nonchimeras', 'uchime_alignments', 'uchimeout')
    REQUIRED_EXECUTABLES = ['vsearch']
    DOCUMENTATION_URL = 'https://github.com/torognes/vsearch'
    CITATION_DOIS = ['10.7717/peerj.2584']
    CITATION_URLS = ['https://doi.org/10.7717/peerj.2584']
    CITATION_TEXT = 'VSEARCH: a versatile open source tool for metagenomics.'
    VERSION = '2.8.3'

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        cmd = ['vsearch', '--threads', str(inputs.get('threads', 4)), '--notrunclabels', '--abskew', str(inputs.get('abskew', 2.0)), '--chimeras', f'{_out(inputs)}/chimeras.fasta', '--dn', str(inputs.get('dn', 1.4)), '--mindiffs', str(inputs.get('mindiffs', 3)), '--mindiv', str(inputs.get('mindiv', 0.8)), '--minh', str(inputs.get('minh', 0.28)), '--xn', str(inputs.get('xn', 8.0))]
        if inputs.get('self_param'):
            cmd.append('--self')
        if inputs.get('selfid_param'):
            cmd.append('--selfid')
        detection_mode = str(inputs.get('detection_mode', inputs.get('detection_mode_select', 'denovo')))
        if detection_mode == 'reference':
            cmd.extend(['--uchime_ref', str(inputs.get('infile_reference', inputs.get('infile', ''))), '--db', str(inputs.get('db', ''))])
        else:
            cmd.extend(['--uchime_denovo', str(inputs.get('infile_denovo', inputs.get('infile', '')))])
        outputs = set(_as_list(inputs.get('outputs')))
        if 'nonchimeras' in outputs:
            cmd.extend(['--nonchimeras', f'{_out(inputs)}/nonchimeras.fasta'])
        if 'uchimealns' in outputs:
            cmd.extend(['--uchimealns', f'{_out(inputs)}/uchime_alignments.txt'])
        if 'uchimeout' in outputs:
            cmd.extend(['--uchimeout', f'{_out(inputs)}/uchimeout.tsv'])
        return cmd

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        out = Path(output_dir) / cls.NODE_ID
        out.mkdir(parents=True, exist_ok=True)
        outputs = [out / 'chimeras.fasta']
        requested = set(_as_list(inputs.get('outputs')))
        if 'nonchimeras' in requested:
            outputs.append(out / 'nonchimeras.fasta')
        if 'uchimealns' in requested:
            outputs.append(out / 'uchime_alignments.txt')
        if 'uchimeout' in requested:
            outputs.append(out / 'uchimeout.tsv')
        return outputs

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {'required': {'detection_mode': ('STRING', {'default': 'denovo', 'options': ['denovo', 'reference'], 'description': 'Galaxy chimera detection mode'}), 'infile_denovo': ('FASTA', {'description': 'Input FASTA for de novo chimera detection'}), 'infile_reference': ('FASTA', {'description': 'Input FASTA for reference-based chimera detection'}), 'db': ('FASTA', {'description': 'Reference database FASTA for uchime_ref mode'})}, 'optional': {'abskew': ('FLOAT', {'default': 2.0, 'min': 0, 'description': 'Minimum abundance ratio of parent versus chimera'}), 'dn': ('FLOAT', {'default': 1.4, 'min': 0, 'description': 'UCHIME no-vote pseudo-count'}), 'xn': ('FLOAT', {'default': 8.0, 'min': 0, 'description': 'UCHIME no-vote weight'}), 'mindiffs': ('INT', {'default': 3, 'min': 0, 'description': 'Minimum differences in segment'}), 'mindiv': ('FLOAT', {'default': 0.8, 'min': 0, 'description': 'Minimum divergence from closest parent'}), 'minh': ('FLOAT', {'default': 0.28, 'min': 0, 'description': 'Minimum chimera score'}), 'self_param': ('BOOLEAN', {'default': False, 'description': 'Exclude identical labels for uchime_ref'}), 'selfid_param': ('BOOLEAN', {'default': False, 'description': 'Exclude identical sequences for uchime_ref'}), 'outputs': ('STRING', {'default': [], 'list': True, 'options': ['nonchimeras', 'uchimealns', 'uchimeout'], 'description': 'Optional Galaxy outputs to request'}), 'threads': ('INT', {'default': 4, 'min': 1, 'max': 128, 'display': 'slider'})}, 'hidden': {'output': ('STRING', {})}}
