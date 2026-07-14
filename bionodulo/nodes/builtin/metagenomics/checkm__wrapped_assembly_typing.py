"""checkm — metagenomics node(s). One tool per file (extracted from wrapped_assembly_typing.py)."""
from __future__ import annotations
from bionodulo.nodes.builtin._wrapped_tool_utils import *


class CheckMLineageWFNode(CommandNode):
    """Assess genome-bin quality with CheckM lineage-specific marker sets."""
    NODE_ID = 'checkm_lineage_wf'
    DISPLAY_NAME = 'CheckM lineage_wf'
    REQUIRED_CONDA_PACKAGES = ['checkm-genome']
    CATEGORY = 'metagenomics'
    DESCRIPTION = 'Assess genome-bin completeness and contamination using lineage-specific marker sets.'
    SEARCH_ALIASES = [BIONODULO_BUILTIN_ALIAS, 'checkm', 'CheckM', 'lineage_wf', 'lineage-specific marker sets', 'genome bin quality', 'MAG quality', 'SAG quality', 'completeness contamination']
    RETURN_TYPES = ('TSV', 'FILE', 'TSV', 'DIRECTORY', 'FASTA', 'PHYLOXML', 'DIRECTORY', 'JSON', 'DIRECTORY', 'DIRECTORY', 'DIRECTORY', 'TSV', 'DIRECTORY', 'TSV', 'FILE', 'DIRECTORY', 'TSV', 'TSV')
    RETURN_NAMES = ('results', 'phylo_hmm_info', 'bin_stats_tree', 'hmmer_tree', 'concatenated_fasta', 'concatenated_tre', 'hmmer_tree_ali', 'concatenated_pplacer_json', 'genes_fna', 'genes_faa', 'genes_gff', 'marker_file', 'hmmer_analyze', 'bin_stats_analyze', 'checkm_hmm_info', 'hmmer_analyze_ali', 'bin_stats_ext', 'marker_gene_stats')
    REQUIRED_EXECUTABLES = ['checkm']
    DOCUMENTATION_URL = 'https://github.com/Ecogenomics/CheckM'
    CITATION_DOIS = ['10.1101/gr.186072.114']
    CITATION_URLS = [f'{DOI_URL}10.1101/gr.186072.114']
    CITATION_TEXT = 'CheckM assesses genome completeness and contamination using lineage-specific marker sets.'
    VERSION = '1.2.5+galaxy0'
    SHELL = True
    INPUT_MODES = ['individual', 'collection']
    EXTRA_OUTPUT_OPTIONS = ['phylo_hmm_info', 'bin_stats_tree', 'hmmer_tree', 'concatenated_tre', 'concatenated_fasta', 'hmmer_tree_ali', 'concatenate_pplacer_json', 'genes_fna', 'genes_faa', 'genes_gff', 'marker_file', 'hmmer_analyze', 'bin_stats_analyze', 'checkm_hmm_info', 'hmmer_analyze_ali', 'bin_stats_ext', 'marker_gene_stats']
    PLAN_OUTPUT_ORDER = ['phylo_hmm_info', 'bin_stats_tree', 'hmmer_tree', 'concatenated_fasta', 'concatenated_tre', 'hmmer_tree_ali', 'concatenate_pplacer_json', 'genes_fna', 'genes_faa', 'genes_gff', 'marker_file', 'hmmer_analyze', 'bin_stats_analyze', 'checkm_hmm_info', 'hmmer_analyze_ali', 'bin_stats_ext', 'marker_gene_stats']
    OPTIONAL_OUTPUT_PATHS = {'phylo_hmm_info': ('phylo_hmm_info', ('output', 'storage', 'phylo_hmm_info.pkl.gz')), 'bin_stats_tree': ('bin_stats_tree', ('output', 'storage', 'bin_stats.tree.tsv')), 'hmmer_tree': ('hmmer_tree', ('output', 'bins', 'hmmer_tree')), 'concatenated_fasta': ('concatenated_fasta', ('output', 'storage', 'tree', 'concatenated.fasta')), 'concatenated_tre': ('concatenated_tre', ('output', 'storage', 'tree', 'concatenated.tre')), 'hmmer_tree_ali': ('hmmer_tree_ali', ('output', 'bins', 'hmmer_tree_ali')), 'concatenate_pplacer_json': ('concatenated_pplacer_json', ('output', 'storage', 'tree', 'concatenated.pplacer.json')), 'genes_fna': ('genes_fna', ('output', 'bins', 'genes_fna')), 'genes_faa': ('genes_faa', ('output', 'bins', 'genes_faa')), 'genes_gff': ('genes_gff', ('output', 'bins', 'genes_gff')), 'marker_file': ('marker_file', ('output', 'lineage.ms')), 'hmmer_analyze': ('hmmer_analyze', ('output', 'bins', 'hmmer_analyze')), 'bin_stats_analyze': ('bin_stats_analyze', ('output', 'storage', 'bin_stats.analyze.tsv')), 'checkm_hmm_info': ('checkm_hmm_info', ('output', 'storage', 'checkm_hmm_info.pkl.gz')), 'hmmer_analyze_ali': ('hmmer_analyze_ali', ('output', 'bins', 'hmmer_analyze_ali')), 'bin_stats_ext': ('bin_stats_ext', ('output', 'storage', 'bin_stats_ext.tsv')), 'marker_gene_stats': ('marker_gene_stats', ('output', 'storage', 'marker_gene_stats.tsv'))}
    DIRECTORY_OUTPUTS = {'hmmer_tree', 'hmmer_tree_ali', 'genes_fna', 'genes_faa', 'genes_gff', 'hmmer_analyze', 'hmmer_analyze_ali'}

    @classmethod
    def _input_files(cls, inputs: dict[str, Any]) -> list[str]:
        return _as_list(inputs.get('bins', inputs.get('bins_ind', inputs.get('bins_coll', inputs.get('input')))))

    @classmethod
    def _extra_outputs(cls, inputs: dict[str, Any]) -> list[str]:
        raw = inputs.get('extra_outputs', [])
        if isinstance(raw, str):
            return [part.strip() for part in raw.split(',') if part.strip()]
        if isinstance(raw, (list, tuple)):
            return [str(value) for value in raw if str(value)]
        return []

    @classmethod
    def _element_identifiers(cls, inputs: dict[str, Any], input_files: list[str]) -> list[str]:
        raw = inputs.get('element_identifiers', inputs.get('identifiers', inputs.get('labels')))
        if isinstance(raw, (list, tuple)):
            identifiers = [str(identifier) if identifier is not None else '' for identifier in raw]
        elif raw is None or raw == '':
            identifiers = []
        else:
            identifiers = [str(raw)]
        input_mode = str(inputs.get('input_mode', inputs.get('select', 'individual')) or 'individual')
        resolved: list[str] = []
        for index, input_file in enumerate(input_files):
            identifier = identifiers[index] if index < len(identifiers) else ''
            if input_mode == 'collection' and identifier:
                resolved.append(_safe_identifier(identifier))
            else:
                resolved.append(_safe_name(input_file))
        return resolved

    @classmethod
    def _link_name(cls, input_mode: str, identifier: str) -> str:
        if input_mode == 'collection':
            return f'{identifier}.fasta'
        return f'{identifier}.fasta'

    @classmethod
    def _add_bool(cls, cmd: list[str], inputs: dict[str, Any], name: str, flag: str) -> None:
        if inputs.get(name):
            cmd.append(flag)

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        out = _out(inputs)
        bins_dir = f'{out}/bins'
        checkm_out = f'{out}/output'
        input_files = cls._input_files(inputs)
        input_mode = str(inputs.get('input_mode', inputs.get('select', 'individual')) or 'individual')
        identifiers = cls._element_identifiers(inputs, input_files)
        cmd = ['mkdir', '-p', bins_dir, checkm_out]
        for input_file, identifier in zip(input_files, identifiers, strict=True):
            cmd.extend(['&&', 'ln', '-sf', input_file, f'{bins_dir}/{cls._link_name(input_mode, identifier)}'])
        cmd.extend(['&&', 'checkm', 'lineage_wf', bins_dir, checkm_out])
        for name, flag in [('reduced_tree', '--reduced_tree'), ('ali', '--ali'), ('nt', '--nt'), ('genes', '--genes')]:
            cls._add_bool(cmd, inputs, name, flag)
        cmd.extend(['--unique', str(inputs.get('unique', 10)), '--multi', str(inputs.get('multi', 10))])
        for name, flag in [('force_domain', '--force_domain'), ('no_refinement', '--no_refinement'), ('individual_markers', '--individual_markers'), ('skip_adj_correction', '--skip_adj_correction'), ('skip_pseudogene_correction', '--skip_pseudogene_correction')]:
            cls._add_bool(cmd, inputs, name, flag)
        cmd.extend(['--aai_strain', str(inputs.get('aai_strain', 0.9))])
        cls._add_bool(cmd, inputs, 'ignore_thresholds', '--ignore_thresholds')
        threads = str(inputs.get('threads', 1))
        cmd.extend(['--e_value', str(inputs.get('e_value', '1e-10')), '--length', str(inputs.get('length', 0.7)), '--file', f'{out}/results.tsv', '--tab_table', '--extension', 'fasta', '--threads', threads, '--pplacer_threads', threads])
        return cmd

    @classmethod
    def _include_optional_output(cls, option: str, inputs: dict[str, Any]) -> bool:
        if option in {'hmmer_tree_ali', 'hmmer_analyze_ali'} and (not inputs.get('ali')):
            return False
        if option == 'genes_fna' and (inputs.get('genes') or not inputs.get('nt')):
            return False
        if option == 'genes_gff' and inputs.get('genes'):
            return False
        return True

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        out = Path(output_dir) / cls.NODE_ID
        out.mkdir(parents=True, exist_ok=True)
        outputs = [out / 'results.tsv']
        selected = cls._extra_outputs(inputs)
        for option in cls.PLAN_OUTPUT_ORDER:
            if option not in selected or not cls._include_optional_output(option, inputs):
                continue
            output_name, parts = cls.OPTIONAL_OUTPUT_PATHS[option]
            path = out.joinpath(*parts)
            if output_name in cls.DIRECTORY_OUTPUTS:
                path.mkdir(parents=True, exist_ok=True)
            else:
                path.parent.mkdir(parents=True, exist_ok=True)
            outputs.append(path)
        return outputs

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {'required': {'bins': ('FASTA_LIST', {'multiple': True, 'min_items': 1, 'description': 'Genome-bin FASTA files to assess'})}, 'optional': {'input_mode': ('STRING', {'default': 'individual', 'options': cls.INPUT_MODES, 'description': 'Galaxy bin input structure used for naming symlinks'}), 'element_identifiers': ('STRING_LIST', {'default': [], 'multiple': True, 'description': 'Optional Galaxy collection element identifiers for bins'}), 'reduced_tree': ('BOOLEAN', {'default': False, 'description': 'Use the reduced reference tree for lineage placement'}), 'ali': ('BOOLEAN', {'default': False, 'description': 'Generate HMMER alignment files'}), 'nt': ('BOOLEAN', {'default': False, 'description': 'Generate nucleotide gene sequences'}), 'genes': ('BOOLEAN', {'default': False, 'description': 'Input bins contain amino-acid genes instead of nucleotide contigs'}), 'unique': ('INT', {'default': 10, 'min': 0, 'description': 'Minimum unique phylogenetic markers for lineage-specific marker sets'}), 'multi': ('INT', {'default': 10, 'min': 0, 'description': 'Maximum multi-copy phylogenetic markers before using domain-level marker sets'}), 'force_domain': ('BOOLEAN', {'default': False, 'description': 'Use domain-level marker sets for all bins'}), 'no_refinement': ('BOOLEAN', {'default': False, 'description': 'Disable lineage-specific marker set refinement'}), 'individual_markers': ('BOOLEAN', {'default': False, 'description': 'Treat marker genes as independent during QA'}), 'skip_adj_correction': ('BOOLEAN', {'default': False, 'description': 'Do not exclude adjacent marker genes when estimating contamination'}), 'skip_pseudogene_correction': ('BOOLEAN', {'default': False, 'description': 'Skip pseudogene identification and filtering'}), 'aai_strain': ('FLOAT', {'default': 0.9, 'min': 0, 'max': 1, 'description': 'AAI threshold used to identify strain heterogeneity'}), 'ignore_thresholds': ('BOOLEAN', {'default': False, 'description': 'Ignore model-specific score thresholds'}), 'e_value': ('FLOAT', {'default': 1e-10, 'min': 0, 'max': 1, 'description': 'E-value cutoff'}), 'length': ('FLOAT', {'default': 0.7, 'min': 0, 'max': 1, 'description': 'Minimum target-query overlap fraction'}), 'extra_outputs': ('STRING_LIST', {'default': [], 'options': cls.EXTRA_OUTPUT_OPTIONS, 'multiple': True, 'description': 'Galaxy extra outputs to collect from the workflow'}), 'threads': ('INT', {'default': 1, 'min': 1, 'max': 128, 'display': 'slider'})}, 'hidden': {'output': ('STRING', {})}}

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        if not cls._input_files(inputs):
            return 'at least one bins value is required'
        input_mode = str(inputs.get('input_mode', inputs.get('select', 'individual')) or 'individual')
        if input_mode not in cls.INPUT_MODES:
            return f"input_mode must be one of: {', '.join(cls.INPUT_MODES)}"
        for name in ('unique', 'multi'):
            try:
                value = int(inputs.get(name, 10))
            except (TypeError, ValueError):
                return f'{name} must be an integer'
            if value < 0:
                return f'{name} must be >= 0'
        for name, default in {'aai_strain': 0.9, 'e_value': 1e-10, 'length': 0.7}.items():
            try:
                value = float(inputs.get(name, default))
            except (TypeError, ValueError):
                return f'{name} must be a number'
            if value < 0 or value > 1:
                return f'{name} must be between 0 and 1'
        try:
            threads = int(inputs.get('threads', 1))
        except (TypeError, ValueError):
            return 'threads must be an integer'
        if threads < 1:
            return 'threads must be >= 1'
        unknown = [value for value in cls._extra_outputs(inputs) if value not in cls.EXTRA_OUTPUT_OPTIONS]
        if unknown:
            return f"extra_outputs values must be one of: {', '.join(cls.EXTRA_OUTPUT_OPTIONS)}"
        return True


class CheckMTreeNode(CommandNode):
    """Place genome bins in the CheckM reference genome tree."""
    NODE_ID = 'checkm_tree'
    DISPLAY_NAME = 'CheckM tree'
    REQUIRED_CONDA_PACKAGES = ['checkm-genome']
    CATEGORY = 'metagenomics'
    DESCRIPTION = 'Place genome bins in the CheckM reference genome tree.'
    SEARCH_ALIASES = [BIONODULO_BUILTIN_ALIAS, 'checkm', 'CheckM', 'checkm tree', 'genome tree', 'phylogenetic placement', 'phylogenetic marker', 'pplacer']
    RETURN_TYPES = ('FILE', 'TSV', 'DIRECTORY', 'FASTA', 'PHYLOXML', 'DIRECTORY', 'JSON', 'DIRECTORY', 'DIRECTORY', 'DIRECTORY')
    RETURN_NAMES = ('phylo_hmm_info', 'bin_stats_tree', 'hmmer_tree', 'concatenated_fasta', 'concatenated_tre', 'hmmer_tree_ali', 'concatenated_pplacer_json', 'genes_fna', 'genes_faa', 'genes_gff')
    REQUIRED_EXECUTABLES = ['checkm']
    DOCUMENTATION_URL = 'https://github.com/Ecogenomics/CheckM'
    CITATION_DOIS = ['10.1101/gr.186072.114']
    CITATION_URLS = [f'{DOI_URL}10.1101/gr.186072.114']
    CITATION_TEXT = 'CheckM assesses genome completeness and contamination using lineage-specific marker sets.'
    VERSION = '1.2.5+galaxy0'
    SHELL = True
    INPUT_MODES = CheckMLineageWFNode.INPUT_MODES
    EXTRA_OUTPUT_OPTIONS = ['hmmer_tree_ali', 'concatenate_pplacer_json', 'genes_fna', 'genes_faa', 'genes_gff']
    PLAN_OUTPUT_ORDER = ['hmmer_tree_ali', 'concatenate_pplacer_json', 'genes_fna', 'genes_faa', 'genes_gff']
    DEFAULT_OUTPUT_PATHS = [('phylo_hmm_info', ('output', 'storage', 'phylo_hmm_info.pkl.gz')), ('bin_stats_tree', ('output', 'storage', 'bin_stats.tree.tsv')), ('hmmer_tree', ('output', 'bins', 'hmmer_tree')), ('concatenated_fasta', ('output', 'storage', 'tree', 'concatenated.fasta')), ('concatenated_tre', ('output', 'storage', 'tree', 'concatenated.tre'))]
    OPTIONAL_OUTPUT_PATHS = {key: CheckMLineageWFNode.OPTIONAL_OUTPUT_PATHS[key] for key in PLAN_OUTPUT_ORDER}
    DIRECTORY_OUTPUTS = CheckMLineageWFNode.DIRECTORY_OUTPUTS

    @classmethod
    def _input_files(cls, inputs: dict[str, Any]) -> list[str]:
        return CheckMLineageWFNode._input_files(inputs)

    @classmethod
    def _extra_outputs(cls, inputs: dict[str, Any]) -> list[str]:
        return CheckMLineageWFNode._extra_outputs(inputs)

    @classmethod
    def _element_identifiers(cls, inputs: dict[str, Any], input_files: list[str]) -> list[str]:
        return CheckMLineageWFNode._element_identifiers(inputs, input_files)

    @classmethod
    def _link_name(cls, input_mode: str, identifier: str) -> str:
        return CheckMLineageWFNode._link_name(input_mode, identifier)

    @classmethod
    def _add_bool(cls, cmd: list[str], inputs: dict[str, Any], name: str, flag: str) -> None:
        if inputs.get(name):
            cmd.append(flag)

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        out = _out(inputs)
        bins_dir = f'{out}/bins'
        checkm_out = f'{out}/output'
        input_files = cls._input_files(inputs)
        input_mode = str(inputs.get('input_mode', inputs.get('select', 'individual')) or 'individual')
        identifiers = cls._element_identifiers(inputs, input_files)
        cmd = ['mkdir', '-p', bins_dir, checkm_out]
        for input_file, identifier in zip(input_files, identifiers, strict=True):
            cmd.extend(['&&', 'ln', '-sf', input_file, f'{bins_dir}/{cls._link_name(input_mode, identifier)}'])
        cmd.extend(['&&', 'checkm', 'tree', bins_dir, checkm_out])
        for name, flag in [('reduced_tree', '--reduced_tree'), ('ali', '--ali'), ('nt', '--nt'), ('genes', '--genes')]:
            cls._add_bool(cmd, inputs, name, flag)
        threads = str(inputs.get('threads', 1))
        cmd.extend(['--extension', 'fasta', '--threads', threads, '--pplacer_threads', threads])
        return cmd

    @classmethod
    def _include_optional_output(cls, option: str, inputs: dict[str, Any]) -> bool:
        return CheckMLineageWFNode._include_optional_output(option, inputs)

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        out = Path(output_dir) / cls.NODE_ID
        out.mkdir(parents=True, exist_ok=True)
        outputs: list[Path] = []
        for output_name, parts in cls.DEFAULT_OUTPUT_PATHS:
            path = out.joinpath(*parts)
            if output_name in cls.DIRECTORY_OUTPUTS:
                path.mkdir(parents=True, exist_ok=True)
            else:
                path.parent.mkdir(parents=True, exist_ok=True)
            outputs.append(path)
        selected = cls._extra_outputs(inputs)
        for option in cls.PLAN_OUTPUT_ORDER:
            if option not in selected or not cls._include_optional_output(option, inputs):
                continue
            output_name, parts = cls.OPTIONAL_OUTPUT_PATHS[option]
            path = out.joinpath(*parts)
            if output_name in cls.DIRECTORY_OUTPUTS:
                path.mkdir(parents=True, exist_ok=True)
            else:
                path.parent.mkdir(parents=True, exist_ok=True)
            outputs.append(path)
        return outputs

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {'required': {'bins': ('FASTA_LIST', {'multiple': True, 'min_items': 1, 'description': 'Genome-bin FASTA files to place in the CheckM tree'})}, 'optional': {'input_mode': ('STRING', {'default': 'individual', 'options': cls.INPUT_MODES, 'description': 'Galaxy bin input structure used for naming symlinks'}), 'element_identifiers': ('STRING_LIST', {'default': [], 'multiple': True, 'description': 'Optional Galaxy collection element identifiers for bins'}), 'reduced_tree': ('BOOLEAN', {'default': False, 'description': 'Use the reduced reference tree for lineage placement'}), 'ali': ('BOOLEAN', {'default': False, 'description': 'Generate phylogenetic HMMER alignment files'}), 'nt': ('BOOLEAN', {'default': False, 'description': 'Generate nucleotide gene sequences'}), 'genes': ('BOOLEAN', {'default': False, 'description': 'Input bins contain amino-acid genes instead of nucleotide contigs'}), 'extra_outputs': ('STRING_LIST', {'default': [], 'options': cls.EXTRA_OUTPUT_OPTIONS, 'multiple': True, 'description': 'Galaxy extra outputs to collect from CheckM tree'}), 'threads': ('INT', {'default': 1, 'min': 1, 'max': 128, 'display': 'slider'})}, 'hidden': {'output': ('STRING', {})}}

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        if not cls._input_files(inputs):
            return 'at least one bins value is required'
        input_mode = str(inputs.get('input_mode', inputs.get('select', 'individual')) or 'individual')
        if input_mode not in cls.INPUT_MODES:
            return f"input_mode must be one of: {', '.join(cls.INPUT_MODES)}"
        try:
            threads = int(inputs.get('threads', 1))
        except (TypeError, ValueError):
            return 'threads must be an integer'
        if threads < 1:
            return 'threads must be >= 1'
        unknown = [value for value in cls._extra_outputs(inputs) if value not in cls.EXTRA_OUTPUT_OPTIONS]
        if unknown:
            return f"extra_outputs values must be one of: {', '.join(cls.EXTRA_OUTPUT_OPTIONS)}"
        return True


class CheckMTreeQANode(CommandNode):
    """Assess phylogenetic markers and placements in the CheckM genome tree."""
    NODE_ID = 'checkm_tree_qa'
    DISPLAY_NAME = 'CheckM tree_qa'
    REQUIRED_CONDA_PACKAGES = ['checkm-genome']
    CATEGORY = 'metagenomics'
    DESCRIPTION = 'Assess phylogenetic markers and placements in the CheckM genome tree.'
    SEARCH_ALIASES = [BIONODULO_BUILTIN_ALIAS, 'checkm', 'CheckM', 'checkm tree_qa', 'tree qa', 'genome tree placement', 'phylogenetic markers', 'Newick', 'alignment']
    RETURN_TYPES = ('TSV', 'TSV', 'PHYLOGENY_TREE', 'PHYLOGENY_TREE', 'ALIGNMENT')
    RETURN_NAMES = ('output_f1', 'output_f2', 'output_f3', 'output_f4', 'output_f5')
    REQUIRED_EXECUTABLES = ['checkm']
    DOCUMENTATION_URL = 'https://github.com/Ecogenomics/CheckM'
    CITATION_DOIS = ['10.1101/gr.186072.114']
    CITATION_URLS = [f'{DOI_URL}10.1101/gr.186072.114']
    CITATION_TEXT = 'CheckM assesses genome completeness and contamination using lineage-specific marker sets.'
    VERSION = '1.2.5+galaxy0'
    SHELL = True
    OUT_FORMATS = ['1', '2', '3', '4', '5']

    @classmethod
    def _as_csv_list(cls, inputs: dict[str, Any], name: str) -> list[str]:
        return CheckMQANode._as_csv_list(inputs, name)

    @classmethod
    def _hmmer_tree(cls, inputs: dict[str, Any]) -> list[str]:
        return cls._as_csv_list(inputs, 'hmmer_tree')

    @classmethod
    def _element_identifiers(cls, inputs: dict[str, Any], files: list[str]) -> list[str]:
        return CheckMQANode._element_identifiers(inputs, files)

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        out = _out(inputs)
        inputs_dir = f'{out}/inputs'
        storage = f'{inputs_dir}/storage'
        tree_storage = f'{storage}/tree'
        hmmer_files = cls._hmmer_tree(inputs)
        identifiers = cls._element_identifiers(inputs, hmmer_files)
        out_format = str(inputs.get('out_format', '1'))
        cmd = ['mkdir', '-p', storage, '&&', 'ln', '-sf', str(inputs.get('phylo_hmm_info', '')), f'{storage}/phylo_hmm_info.pkl.gz', '&&', 'ln', '-sf', str(inputs.get('bin_stats_tree', '')), f'{storage}/bin_stats.tree.tsv']
        for input_file, identifier in zip(hmmer_files, identifiers, strict=True):
            bin_dir = f'{inputs_dir}/bins/{identifier}'
            cmd.extend(['&&', 'mkdir', '-p', bin_dir, '&&', 'ln', '-sf', input_file, f'{bin_dir}/hmmer.tree.txt'])
        cmd.extend(['&&', 'mkdir', '-p', tree_storage, '&&', 'ln', '-sf'])
        if out_format == '5':
            cmd.extend([str(inputs.get('concatenated_fasta', '')), f'{tree_storage}/concatenated.fasta'])
        else:
            cmd.extend([str(inputs.get('concatenated_tre', '')), f'{tree_storage}/concatenated.tre'])
        cmd.extend(['&&', 'checkm', 'tree_qa', inputs_dir, '--out_format', out_format, '--tab_table', '--file', f'{out}/output_file'])
        return cmd

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        out = Path(output_dir) / cls.NODE_ID
        out.mkdir(parents=True, exist_ok=True)
        out_format = str(inputs.get('out_format', '1'))
        if out_format in {'3', '4'}:
            return [out / f'output_f{out_format}.nwk']
        if out_format == '5':
            return [out / 'output_f5.aln.fasta']
        return [out / f'output_f{out_format}.tsv']

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {'required': {'phylo_hmm_info': ('FILE', {'description': 'Phylogenetic HMM model info from CheckM tree'}), 'bin_stats_tree': ('TSV', {'description': 'Phylogenetic bin stats from CheckM tree'}), 'hmmer_tree': ('TXT', {'multiple': True, 'description': 'Phylogenetic HMM hits collection from CheckM tree'})}, 'optional': {'element_identifiers': ('STRING_LIST', {'default': [], 'multiple': True, 'description': 'Optional identifiers for hmmer_tree entries'}), 'out_format': ('STRING', {'default': '1', 'options': cls.OUT_FORMATS, 'description': 'CheckM tree_qa report format to emit'}), 'concatenated_tre': ('PHYLOGENY_TREE', {'default': '', 'description': 'Concatenated tree from CheckM tree for out_format 1-4'}), 'concatenated_fasta': ('FASTA', {'default': '', 'description': 'Concatenated masked sequences from CheckM tree for out_format 5'})}, 'hidden': {'output': ('STRING', {})}}

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        for required in ('phylo_hmm_info', 'bin_stats_tree'):
            if not str(inputs.get(required, '')).strip():
                return f'{required} is required'
        if not cls._hmmer_tree(inputs):
            return 'at least one hmmer_tree value is required'
        out_format = str(inputs.get('out_format', '1'))
        if out_format not in cls.OUT_FORMATS:
            return f"out_format must be one of: {', '.join(cls.OUT_FORMATS)}"
        if out_format == '5':
            if not str(inputs.get('concatenated_fasta', '')).strip():
                return 'concatenated_fasta is required when out_format is 5'
        elif not str(inputs.get('concatenated_tre', '')).strip():
            return 'concatenated_tre is required unless out_format is 5'
        return True


class CheckMLineageSetNode(CommandNode):
    """Infer lineage-specific marker sets for each genome bin."""
    NODE_ID = 'checkm_lineage_set'
    DISPLAY_NAME = 'CheckM lineage_set'
    REQUIRED_CONDA_PACKAGES = ['checkm-genome']
    CATEGORY = 'metagenomics'
    DESCRIPTION = 'Infer lineage-specific marker sets for each genome bin.'
    SEARCH_ALIASES = [BIONODULO_BUILTIN_ALIAS, 'checkm', 'CheckM', 'checkm lineage_set', 'lineage set', 'lineage-specific marker sets', 'marker genes', 'bin marker set']
    RETURN_TYPES = ('TSV',)
    RETURN_NAMES = ('marker',)
    REQUIRED_EXECUTABLES = ['checkm']
    DOCUMENTATION_URL = 'https://github.com/Ecogenomics/CheckM'
    CITATION_DOIS = ['10.1101/gr.186072.114']
    CITATION_URLS = [f'{DOI_URL}10.1101/gr.186072.114']
    CITATION_TEXT = 'CheckM assesses genome completeness and contamination using lineage-specific marker sets.'
    VERSION = '1.2.5+galaxy0'
    SHELL = True

    @classmethod
    def _hmmer_tree(cls, inputs: dict[str, Any]) -> list[str]:
        return CheckMTreeQANode._hmmer_tree(inputs)

    @classmethod
    def _element_identifiers(cls, inputs: dict[str, Any], files: list[str]) -> list[str]:
        return CheckMTreeQANode._element_identifiers(inputs, files)

    @classmethod
    def _add_bool(cls, cmd: list[str], inputs: dict[str, Any], name: str, flag: str) -> None:
        if inputs.get(name):
            cmd.append(flag)

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        out = _out(inputs)
        inputs_dir = f'{out}/inputs'
        storage = f'{inputs_dir}/storage'
        tree_storage = f'{storage}/tree'
        hmmer_files = cls._hmmer_tree(inputs)
        identifiers = cls._element_identifiers(inputs, hmmer_files)
        cmd = ['mkdir', '-p', storage, '&&', 'ln', '-sf', str(inputs.get('phylo_hmm_info', '')), f'{storage}/phylo_hmm_info.pkl.gz', '&&', 'ln', '-sf', str(inputs.get('bin_stats_tree', '')), f'{storage}/bin_stats.tree.tsv']
        for input_file, identifier in zip(hmmer_files, identifiers, strict=True):
            bin_dir = f'{inputs_dir}/bins/{identifier}'
            cmd.extend(['&&', 'mkdir', '-p', bin_dir, '&&', 'ln', '-sf', input_file, f'{bin_dir}/hmmer.tree.txt'])
        cmd.extend(['&&', 'mkdir', '-p', tree_storage, '&&', 'ln', '-sf', str(inputs.get('concatenated_tre', '')), f'{tree_storage}/concatenated.tre', '&&', 'checkm', 'lineage_set', inputs_dir, f'{out}/marker.tsv', '--unique', str(inputs.get('unique', 10)), '--multi', str(inputs.get('multi', 10))])
        cls._add_bool(cmd, inputs, 'force_domain', '--force_domain')
        cls._add_bool(cmd, inputs, 'no_refinement', '--no_refinement')
        return cmd

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        out = Path(output_dir) / cls.NODE_ID
        out.mkdir(parents=True, exist_ok=True)
        return [out / 'marker.tsv']

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {'required': {'phylo_hmm_info': ('FILE', {'description': 'Phylogenetic HMM model info from CheckM tree'}), 'bin_stats_tree': ('TSV', {'description': 'Phylogenetic bin stats from CheckM tree'}), 'hmmer_tree': ('TXT', {'multiple': True, 'description': 'Phylogenetic HMM hits collection from CheckM tree'}), 'concatenated_tre': ('PHYLOGENY_TREE', {'description': 'Concatenated tree from CheckM tree'})}, 'optional': {'element_identifiers': ('STRING_LIST', {'default': [], 'multiple': True, 'description': 'Optional identifiers for hmmer_tree entries'}), 'unique': ('INT', {'default': 10, 'min': 0, 'description': 'Minimum unique phylogenetic markers for lineage-specific marker sets'}), 'multi': ('INT', {'default': 10, 'min': 0, 'description': 'Maximum multi-copy phylogenetic markers before using domain-level marker sets'}), 'force_domain': ('BOOLEAN', {'default': False, 'description': 'Use domain-level marker sets for all bins'}), 'no_refinement': ('BOOLEAN', {'default': False, 'description': 'Disable lineage-specific marker set refinement'})}, 'hidden': {'output': ('STRING', {})}}

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        for required in ('phylo_hmm_info', 'bin_stats_tree'):
            if not str(inputs.get(required, '')).strip():
                return f'{required} is required'
        if not cls._hmmer_tree(inputs):
            return 'at least one hmmer_tree value is required'
        if not str(inputs.get('concatenated_tre', '')).strip():
            return 'concatenated_tre is required'
        for name in ('unique', 'multi'):
            try:
                value = int(inputs.get(name, 10))
            except (TypeError, ValueError):
                return f'{name} must be an integer'
            if value < 0:
                return f'{name} must be >= 0'
        return True


class CheckMTaxonSetNode(CommandNode):
    """Generate a taxonomic-specific CheckM marker set."""
    NODE_ID = 'checkm_taxon_set'
    DISPLAY_NAME = 'CheckM taxon_set'
    REQUIRED_CONDA_PACKAGES = ['checkm-genome']
    CATEGORY = 'metagenomics'
    DESCRIPTION = 'Generate a taxonomic-specific CheckM marker set.'
    SEARCH_ALIASES = [BIONODULO_BUILTIN_ALIAS, 'checkm', 'CheckM', 'checkm taxon_set', 'taxon set', 'taxonomic marker set', 'marker genes', 'Prokaryote']
    RETURN_TYPES = ('TSV',)
    RETURN_NAMES = ('marker',)
    REQUIRED_EXECUTABLES = ['checkm']
    DOCUMENTATION_URL = 'https://github.com/Ecogenomics/CheckM'
    CITATION_DOIS = ['10.1101/gr.186072.114']
    CITATION_URLS = [f'{DOI_URL}10.1101/gr.186072.114']
    CITATION_TEXT = 'CheckM assesses genome completeness and contamination using lineage-specific marker sets.'
    VERSION = '1.2.5+galaxy0'
    SHELL = True
    RANKS = ['life', 'domain', 'phylum', 'order', 'family', 'genus', 'species']
    DOMAIN_TAXA = ['Archaea', 'Bacteria']

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        out = _out(inputs)
        return ['checkm', 'taxon_set', str(inputs.get('rank', '')), str(inputs.get('taxon', '')), f'{out}/marker.tsv']

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        out = Path(output_dir) / cls.NODE_ID
        out.mkdir(parents=True, exist_ok=True)
        return [out / 'marker.tsv']

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {'required': {'rank': ('STRING', {'default': 'life', 'options': cls.RANKS, 'description': 'Taxonomic rank for the CheckM marker set'}), 'taxon': ('STRING', {'default': 'Prokaryote', 'description': 'Taxon value supported by CheckM for the selected rank'})}, 'optional': {}, 'hidden': {'output': ('STRING', {})}}

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        rank = str(inputs.get('rank', '')).strip()
        if not rank:
            return 'rank is required'
        if rank not in cls.RANKS:
            return f"rank must be one of: {', '.join(cls.RANKS)}"
        taxon = str(inputs.get('taxon', '')).strip()
        if not taxon:
            return 'taxon is required'
        if rank == 'life' and taxon != 'Prokaryote':
            return 'taxon for rank life must be Prokaryote'
        if rank == 'domain' and taxon not in cls.DOMAIN_TAXA:
            return f"taxon for rank domain must be one of: {', '.join(cls.DOMAIN_TAXA)}"
        return True


class CheckMTaxonomyWFNode(CommandNode):
    """Analyze genome bins with a shared taxonomic-specific CheckM marker set."""
    NODE_ID = 'checkm_taxonomy_wf'
    DISPLAY_NAME = 'CheckM taxonomy_wf'
    REQUIRED_CONDA_PACKAGES = ['checkm-genome']
    CATEGORY = 'metagenomics'
    DESCRIPTION = 'Analyze genome bins with a shared taxonomic-specific marker set.'
    SEARCH_ALIASES = [BIONODULO_BUILTIN_ALIAS, 'checkm', 'CheckM', 'checkm taxonomy_wf', 'taxonomy_wf', 'taxonomic marker set', 'genome bin quality', 'completeness contamination']
    RETURN_TYPES = ('TSV', 'TSV', 'DIRECTORY', 'TSV', 'FILE', 'DIRECTORY', 'TSV', 'TSV')
    RETURN_NAMES = ('results', 'marker_file', 'hmmer_analyze', 'bin_stats_analyze', 'checkm_hmm_info', 'hmmer_analyze_ali', 'bin_stats_ext', 'marker_gene_stats')
    REQUIRED_EXECUTABLES = ['checkm']
    DOCUMENTATION_URL = 'https://github.com/Ecogenomics/CheckM'
    CITATION_DOIS = ['10.1101/gr.186072.114']
    CITATION_URLS = [f'{DOI_URL}10.1101/gr.186072.114']
    CITATION_TEXT = 'CheckM assesses genome completeness and contamination using lineage-specific marker sets.'
    VERSION = '1.2.5+galaxy0'
    SHELL = True
    INPUT_MODES = CheckMLineageWFNode.INPUT_MODES
    RANKS = CheckMTaxonSetNode.RANKS
    DOMAIN_TAXA = CheckMTaxonSetNode.DOMAIN_TAXA
    EXTRA_OUTPUT_OPTIONS = ['marker_file', 'hmmer_analyze', 'bin_stats_analyze', 'checkm_hmm_info', 'hmmer_analyze_ali', 'bin_stats_ext', 'marker_gene_stats']
    OPTIONAL_OUTPUT_PATHS = {'marker_file': ('marker_file', ('output', 'taxon.ms')), 'hmmer_analyze': ('hmmer_analyze', ('output', 'bins', 'hmmer_analyze')), 'bin_stats_analyze': ('bin_stats_analyze', ('output', 'storage', 'bin_stats.analyze.tsv')), 'checkm_hmm_info': ('checkm_hmm_info', ('output', 'storage', 'checkm_hmm_info.pkl.gz')), 'hmmer_analyze_ali': ('hmmer_analyze_ali', ('output', 'bins', 'hmmer_analyze_ali')), 'bin_stats_ext': ('bin_stats_ext', ('output', 'storage', 'bin_stats_ext.tsv')), 'marker_gene_stats': ('marker_gene_stats', ('output', 'storage', 'marker_gene_stats.tsv'))}
    DIRECTORY_OUTPUTS = {'hmmer_analyze', 'hmmer_analyze_ali'}

    @classmethod
    def _input_files(cls, inputs: dict[str, Any]) -> list[str]:
        return CheckMLineageWFNode._input_files(inputs)

    @classmethod
    def _extra_outputs(cls, inputs: dict[str, Any]) -> list[str]:
        return CheckMLineageWFNode._extra_outputs(inputs)

    @classmethod
    def _element_identifiers(cls, inputs: dict[str, Any], input_files: list[str]) -> list[str]:
        return CheckMLineageWFNode._element_identifiers(inputs, input_files)

    @classmethod
    def _link_name(cls, input_mode: str, identifier: str) -> str:
        return CheckMLineageWFNode._link_name(input_mode, identifier)

    @classmethod
    def _add_bool(cls, cmd: list[str], inputs: dict[str, Any], name: str, flag: str) -> None:
        CheckMLineageWFNode._add_bool(cmd, inputs, name, flag)

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        out = _out(inputs)
        bins_dir = f'{out}/bins'
        checkm_out = f'{out}/output'
        input_files = cls._input_files(inputs)
        input_mode = str(inputs.get('input_mode', inputs.get('select', 'individual')) or 'individual')
        identifiers = cls._element_identifiers(inputs, input_files)
        cmd = ['mkdir', '-p', bins_dir, checkm_out]
        for input_file, identifier in zip(input_files, identifiers, strict=True):
            cmd.extend(['&&', 'ln', '-sf', input_file, f'{bins_dir}/{cls._link_name(input_mode, identifier)}'])
        cmd.extend(['&&', 'checkm', 'taxonomy_wf', str(inputs.get('rank', '')), str(inputs.get('taxon', '')), bins_dir, checkm_out])
        for name, flag in [('ali', '--ali'), ('nt', '--nt'), ('genes', '--genes')]:
            cls._add_bool(cmd, inputs, name, flag)
        for name, flag in [('individual_markers', '--individual_markers'), ('skip_adj_correction', '--skip_adj_correction'), ('skip_pseudogene_correction', '--skip_pseudogene_correction')]:
            cls._add_bool(cmd, inputs, name, flag)
        cmd.extend(['--aai_strain', str(inputs.get('aai_strain', 0.9))])
        cls._add_bool(cmd, inputs, 'ignore_thresholds', '--ignore_thresholds')
        cmd.extend(['--e_value', str(inputs.get('e_value', '1e-10')), '--length', str(inputs.get('length', 0.7)), '--file', f'{out}/results.tsv', '--tab_table', '--extension', 'fasta', '--threads', str(inputs.get('threads', 1))])
        return cmd

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        out = Path(output_dir) / cls.NODE_ID
        out.mkdir(parents=True, exist_ok=True)
        outputs = [out / 'results.tsv']
        selected = cls._extra_outputs(inputs)
        for option in cls.EXTRA_OUTPUT_OPTIONS:
            if option not in selected:
                continue
            if option == 'hmmer_analyze_ali' and (not inputs.get('ali')):
                continue
            output_name, parts = cls.OPTIONAL_OUTPUT_PATHS[option]
            path = out.joinpath(*parts)
            if output_name in cls.DIRECTORY_OUTPUTS:
                path.mkdir(parents=True, exist_ok=True)
            else:
                path.parent.mkdir(parents=True, exist_ok=True)
            outputs.append(path)
        return outputs

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {'required': {'rank': ('STRING', {'default': 'life', 'options': cls.RANKS, 'description': 'Taxonomic rank for the CheckM marker set'}), 'taxon': ('STRING', {'default': 'Prokaryote', 'description': 'Taxon value supported by CheckM for the selected rank'}), 'bins': ('FASTA_LIST', {'multiple': True, 'min_items': 1, 'description': 'Genome-bin FASTA files to analyze'})}, 'optional': {'input_mode': ('STRING', {'default': 'individual', 'options': cls.INPUT_MODES, 'description': 'Galaxy bin input structure used for naming symlinks'}), 'element_identifiers': ('STRING_LIST', {'default': [], 'multiple': True, 'description': 'Optional Galaxy collection element identifiers for bins'}), 'ali': ('BOOLEAN', {'default': False, 'description': 'Generate HMMER alignment files'}), 'nt': ('BOOLEAN', {'default': False, 'description': 'Generate nucleotide gene sequences'}), 'genes': ('BOOLEAN', {'default': False, 'description': 'Input bins contain amino-acid genes instead of nucleotide contigs'}), 'individual_markers': ('BOOLEAN', {'default': False, 'description': 'Treat marker genes as independent during QA'}), 'skip_adj_correction': ('BOOLEAN', {'default': False, 'description': 'Do not exclude adjacent marker genes when estimating contamination'}), 'skip_pseudogene_correction': ('BOOLEAN', {'default': False, 'description': 'Skip pseudogene identification and filtering'}), 'aai_strain': ('FLOAT', {'default': 0.9, 'min': 0, 'max': 1, 'description': 'AAI threshold for strain heterogeneity'}), 'ignore_thresholds': ('BOOLEAN', {'default': False, 'description': 'Ignore model-specific score thresholds'}), 'e_value': ('FLOAT', {'default': 1e-10, 'min': 0, 'max': 1, 'description': 'E-value cutoff'}), 'length': ('FLOAT', {'default': 0.7, 'min': 0, 'max': 1, 'description': 'Minimum target-query overlap fraction'}), 'extra_outputs': ('STRING_LIST', {'default': [], 'options': cls.EXTRA_OUTPUT_OPTIONS, 'multiple': True, 'description': 'Galaxy extra outputs to collect from the taxonomy workflow'}), 'threads': ('INT', {'default': 1, 'min': 1, 'max': 128, 'display': 'slider'})}, 'hidden': {'output': ('STRING', {})}}

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        rank = str(inputs.get('rank', '')).strip()
        if not rank:
            return 'rank is required'
        if rank not in cls.RANKS:
            return f"rank must be one of: {', '.join(cls.RANKS)}"
        taxon = str(inputs.get('taxon', '')).strip()
        if not taxon:
            return 'taxon is required'
        if rank == 'life' and taxon != 'Prokaryote':
            return 'taxon for rank life must be Prokaryote'
        if rank == 'domain' and taxon not in cls.DOMAIN_TAXA:
            return f"taxon for rank domain must be one of: {', '.join(cls.DOMAIN_TAXA)}"
        if not cls._input_files(inputs):
            return 'at least one bins value is required'
        input_mode = str(inputs.get('input_mode', inputs.get('select', 'individual')) or 'individual')
        if input_mode not in cls.INPUT_MODES:
            return f"input_mode must be one of: {', '.join(cls.INPUT_MODES)}"
        for name, default in {'aai_strain': 0.9, 'e_value': 1e-10, 'length': 0.7}.items():
            try:
                value = float(inputs.get(name, default))
            except (TypeError, ValueError):
                return f'{name} must be a number'
            if value < 0 or value > 1:
                return f'{name} must be between 0 and 1'
        try:
            threads = int(inputs.get('threads', 1))
        except (TypeError, ValueError):
            return 'threads must be an integer'
        if threads < 1:
            return 'threads must be >= 1'
        unknown = [value for value in cls._extra_outputs(inputs) if value not in cls.EXTRA_OUTPUT_OPTIONS]
        if unknown:
            return f"extra_outputs values must be one of: {', '.join(cls.EXTRA_OUTPUT_OPTIONS)}"
        return True


class CheckMTetraNode(CommandNode):
    """Calculate tetranucleotide signatures for FASTA sequences."""
    NODE_ID = 'checkm_tetra'
    DISPLAY_NAME = 'CheckM tetra'
    REQUIRED_CONDA_PACKAGES = ['checkm-genome']
    CATEGORY = 'metagenomics'
    DESCRIPTION = 'Calculate tetranucleotide signatures for FASTA sequences.'
    SEARCH_ALIASES = [BIONODULO_BUILTIN_ALIAS, 'checkm', 'CheckM', 'checkm tetra', 'tetra', 'tetranucleotide', 'tetranucleotide signatures', 'sequence composition']
    RETURN_TYPES = ('TSV',)
    RETURN_NAMES = ('tetra_profile',)
    REQUIRED_EXECUTABLES = ['checkm']
    DOCUMENTATION_URL = 'https://github.com/Ecogenomics/CheckM'
    CITATION_DOIS = ['10.1101/gr.186072.114']
    CITATION_URLS = [f'{DOI_URL}10.1101/gr.186072.114']
    CITATION_TEXT = 'CheckM assesses genome completeness and contamination using lineage-specific marker sets.'
    VERSION = '1.2.5+galaxy0'
    SHELL = True

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        out = _out(inputs)
        return ['checkm', 'tetra', str(inputs.get('seq_file', '')), f'{out}/tetra_profile.tsv', '--threads', str(inputs.get('threads', 1))]

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        out = Path(output_dir) / cls.NODE_ID
        out.mkdir(parents=True, exist_ok=True)
        return [out / 'tetra_profile.tsv']

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {'required': {'seq_file': ('FASTA', {'description': 'Sequences used to generate tetranucleotide signatures'})}, 'optional': {'threads': ('INT', {'default': 1, 'min': 1, 'max': 128, 'display': 'slider'})}, 'hidden': {'output': ('STRING', {})}}

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        if not str(inputs.get('seq_file', '')).strip():
            return 'seq_file is required'
        try:
            threads = int(inputs.get('threads', 1))
        except (TypeError, ValueError):
            return 'threads must be an integer'
        if threads < 1:
            return 'threads must be >= 1'
        return True


class CheckMAnalyzeNode(CommandNode):
    """Identify marker genes in genome bins with CheckM analyze."""
    NODE_ID = 'checkm_analyze'
    DISPLAY_NAME = 'CheckM analyze'
    REQUIRED_CONDA_PACKAGES = ['checkm-genome']
    CATEGORY = 'metagenomics'
    DESCRIPTION = 'Identify marker genes in genome bins and calculate genome statistics.'
    SEARCH_ALIASES = [BIONODULO_BUILTIN_ALIAS, 'checkm', 'CheckM', 'checkm analyze', 'marker genes', 'genome bin statistics', 'MAG quality', 'completeness contamination']
    RETURN_TYPES = ('DIRECTORY', 'TSV', 'FILE', 'DIRECTORY')
    RETURN_NAMES = ('hmmer_analyze', 'bin_stats_analyze', 'checkm_hmm_info', 'hmmer_analyze_ali')
    REQUIRED_EXECUTABLES = ['checkm']
    DOCUMENTATION_URL = 'https://github.com/Ecogenomics/CheckM'
    CITATION_DOIS = ['10.1101/gr.186072.114']
    CITATION_URLS = [f'{DOI_URL}10.1101/gr.186072.114']
    CITATION_TEXT = 'CheckM assesses genome completeness and contamination using lineage-specific marker sets.'
    VERSION = '1.2.5+galaxy0'
    SHELL = True
    INPUT_MODES = CheckMLineageWFNode.INPUT_MODES
    EXTRA_OUTPUT_OPTIONS = ['hmmer_analyze_ali']

    @classmethod
    def _input_files(cls, inputs: dict[str, Any]) -> list[str]:
        return CheckMLineageWFNode._input_files(inputs)

    @classmethod
    def _extra_outputs(cls, inputs: dict[str, Any]) -> list[str]:
        raw = inputs.get('extra_outputs', [])
        if isinstance(raw, str):
            return [part.strip() for part in raw.split(',') if part.strip()]
        if isinstance(raw, (list, tuple)):
            return [str(value) for value in raw if str(value)]
        return []

    @classmethod
    def _element_identifiers(cls, inputs: dict[str, Any], input_files: list[str]) -> list[str]:
        return CheckMLineageWFNode._element_identifiers(inputs, input_files)

    @classmethod
    def _link_name(cls, input_mode: str, identifier: str) -> str:
        return CheckMLineageWFNode._link_name(input_mode, identifier)

    @classmethod
    def _add_bool(cls, cmd: list[str], inputs: dict[str, Any], name: str, flag: str) -> None:
        if inputs.get(name):
            cmd.append(flag)

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        out = _out(inputs)
        bins_dir = f'{out}/bins'
        checkm_out = f'{out}/output'
        input_files = cls._input_files(inputs)
        input_mode = str(inputs.get('input_mode', inputs.get('select', 'individual')) or 'individual')
        identifiers = cls._element_identifiers(inputs, input_files)
        cmd = ['mkdir', '-p', bins_dir, checkm_out]
        for input_file, identifier in zip(input_files, identifiers, strict=True):
            cmd.extend(['&&', 'ln', '-sf', input_file, f'{bins_dir}/{cls._link_name(input_mode, identifier)}'])
        cmd.extend(['&&', 'checkm', 'analyze', str(inputs.get('marker_file', '')), bins_dir, checkm_out])
        for name, flag in [('ali', '--ali'), ('nt', '--nt'), ('genes', '--genes')]:
            cls._add_bool(cmd, inputs, name, flag)
        cmd.extend(['--extension', 'fasta', '--threads', str(inputs.get('threads', 1))])
        return cmd

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        out = Path(output_dir) / cls.NODE_ID
        hmmer_out = out / 'output' / 'bins' / 'hmmer_analyze'
        hmmer_out.mkdir(parents=True, exist_ok=True)
        storage = out / 'output' / 'storage'
        storage.mkdir(parents=True, exist_ok=True)
        outputs = [hmmer_out, storage / 'bin_stats.analyze.tsv', storage / 'checkm_hmm_info.pkl.gz']
        if inputs.get('ali') and 'hmmer_analyze_ali' in cls._extra_outputs(inputs):
            ali_out = out / 'output' / 'bins' / 'hmmer_analyze_ali'
            ali_out.mkdir(parents=True, exist_ok=True)
            outputs.append(ali_out)
        return outputs

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {'required': {'marker_file': ('TSV', {'description': 'Marker gene set from CheckM lineage_set or taxon_set'}), 'bins': ('FASTA_LIST', {'multiple': True, 'min_items': 1, 'description': 'Genome-bin FASTA files to analyze'})}, 'optional': {'input_mode': ('STRING', {'default': 'individual', 'options': cls.INPUT_MODES, 'description': 'Galaxy bin input structure used for naming symlinks'}), 'element_identifiers': ('STRING_LIST', {'default': [], 'multiple': True, 'description': 'Optional Galaxy collection element identifiers for bins'}), 'ali': ('BOOLEAN', {'default': False, 'description': 'Generate HMMER alignment files'}), 'nt': ('BOOLEAN', {'default': False, 'description': 'Generate nucleotide gene sequences'}), 'genes': ('BOOLEAN', {'default': False, 'description': 'Input bins contain amino-acid genes instead of nucleotide contigs'}), 'extra_outputs': ('STRING_LIST', {'default': [], 'options': cls.EXTRA_OUTPUT_OPTIONS, 'multiple': True, 'description': 'Galaxy extra outputs to collect from the analyze run'}), 'threads': ('INT', {'default': 1, 'min': 1, 'max': 128, 'display': 'slider'})}, 'hidden': {'output': ('STRING', {})}}

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        if not str(inputs.get('marker_file', '')).strip():
            return 'marker_file is required'
        if not cls._input_files(inputs):
            return 'at least one bins value is required'
        input_mode = str(inputs.get('input_mode', inputs.get('select', 'individual')) or 'individual')
        if input_mode not in cls.INPUT_MODES:
            return f"input_mode must be one of: {', '.join(cls.INPUT_MODES)}"
        try:
            threads = int(inputs.get('threads', 1))
        except (TypeError, ValueError):
            return 'threads must be an integer'
        if threads < 1:
            return 'threads must be >= 1'
        unknown = [value for value in cls._extra_outputs(inputs) if value not in cls.EXTRA_OUTPUT_OPTIONS]
        if unknown:
            return f"extra_outputs values must be one of: {', '.join(cls.EXTRA_OUTPUT_OPTIONS)}"
        return True


class CheckMQANode(CommandNode):
    """Assess CheckM analyze results for genome-bin completeness and contamination."""
    NODE_ID = 'checkm_qa'
    DISPLAY_NAME = 'CheckM qa'
    REQUIRED_CONDA_PACKAGES = ['checkm-genome']
    CATEGORY = 'metagenomics'
    DESCRIPTION = 'Assess genome bins for completeness and contamination from CheckM analyze outputs.'
    SEARCH_ALIASES = [BIONODULO_BUILTIN_ALIAS, 'checkm', 'CheckM', 'checkm qa', 'genome completeness', 'genome contamination', 'bin quality', 'marker gene stats']
    RETURN_TYPES = ('TSV', 'TSV', 'TSV')
    RETURN_NAMES = ('output', 'bin_stats_ext', 'marker_gene_stats')
    REQUIRED_EXECUTABLES = ['checkm']
    DOCUMENTATION_URL = 'https://github.com/Ecogenomics/CheckM'
    CITATION_DOIS = ['10.1101/gr.186072.114']
    CITATION_URLS = [f'{DOI_URL}10.1101/gr.186072.114']
    CITATION_TEXT = 'CheckM assesses genome completeness and contamination using lineage-specific marker sets.'
    VERSION = '1.2.5+galaxy0'
    SHELL = True
    OUT_FORMATS = ['1', '2', '3', '4', '5', '6', '7', '8', '9']
    EXTRA_OUTPUT_OPTIONS = ['marker_gene_stats']

    @classmethod
    def _as_csv_list(cls, inputs: dict[str, Any], name: str) -> list[str]:
        raw = inputs.get(name, [])
        if isinstance(raw, str):
            if ',' in raw:
                return [part.strip() for part in raw.split(',') if part.strip()]
            return [raw] if raw else []
        if isinstance(raw, (list, tuple)):
            return [str(value) for value in raw if str(value)]
        return []

    @classmethod
    def _hmmer_analyze(cls, inputs: dict[str, Any]) -> list[str]:
        return cls._as_csv_list(inputs, 'hmmer_analyze')

    @classmethod
    def _extra_outputs(cls, inputs: dict[str, Any]) -> list[str]:
        return cls._as_csv_list(inputs, 'extra_outputs')

    @classmethod
    def _element_identifiers(cls, inputs: dict[str, Any], files: list[str], key: str='element_identifiers') -> list[str]:
        raw = inputs.get(key, inputs.get('identifiers', inputs.get('labels')))
        if isinstance(raw, (list, tuple)):
            identifiers = [str(identifier) if identifier is not None else '' for identifier in raw]
        elif raw is None or raw == '':
            identifiers = []
        else:
            identifiers = [str(raw)]
        return [_safe_identifier(identifiers[index]) if index < len(identifiers) and identifiers[index] else _safe_name(file) for index, file in enumerate(files)]

    @classmethod
    def _stage_collection(cls, cmd: list[str], files: list[str], identifiers: list[str], out: str, filename: str) -> None:
        for input_file, identifier in zip(files, identifiers, strict=True):
            bin_dir = f'{out}/output/bins/{identifier}'
            cmd.extend(['&&', 'mkdir', '-p', bin_dir, '&&', 'cp', input_file, f'{bin_dir}/{filename}'])

    @classmethod
    def _add_bool(cls, cmd: list[str], inputs: dict[str, Any], name: str, flag: str) -> None:
        if inputs.get(name):
            cmd.append(flag)

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        out = _out(inputs)
        checkm_out = f'{out}/output'
        storage = f'{checkm_out}/storage'
        hmmer_files = cls._hmmer_analyze(inputs)
        hmmer_ids = cls._element_identifiers(inputs, hmmer_files)
        cmd = ['mkdir', '-p', storage, '&&', 'cp', str(inputs.get('checkm_hmm_info', '')), f'{storage}/checkm_hmm_info.pkl.gz', '&&', 'cp', str(inputs.get('bin_stats_analyze', '')), f'{storage}/bin_stats.analyze.tsv']
        cls._stage_collection(cmd, hmmer_files, hmmer_ids, out, 'hmmer.analyze.txt')
        if str(inputs.get('out_format', '1')) == '9':
            genes_files = cls._as_csv_list(inputs, 'genes_faa')
            gene_ids = cls._element_identifiers(inputs, genes_files, 'genes_element_identifiers')
            cls._stage_collection(cmd, genes_files, gene_ids, out, 'genes.faa')
        cmd.extend(['&&', 'checkm', 'qa', str(inputs.get('marker_file', '')), checkm_out, '--out_format', str(inputs.get('out_format', '1')), '--tab_table', '--file', f'{out}/output.tsv'])
        _add_if_value(cmd, '--exclude_markers', inputs.get('exclude_markers'))
        for name, flag in [('individual_markers', '--individual_markers'), ('skip_adj_correction', '--skip_adj_correction'), ('skip_pseudogene_correction', '--skip_pseudogene_correction')]:
            cls._add_bool(cmd, inputs, name, flag)
        cmd.extend(['--aai_strain', str(inputs.get('aai_strain', 0.9))])
        cls._add_bool(cmd, inputs, 'ignore_thresholds', '--ignore_thresholds')
        cmd.extend(['--e_value', str(inputs.get('e_value', '1e-10')), '--length', str(inputs.get('length', 0.7))])
        _add_if_value(cmd, '--coverage_file', inputs.get('coverage'))
        cmd.extend(['--threads', str(inputs.get('threads', 1))])
        return cmd

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        out = Path(output_dir) / cls.NODE_ID
        storage = out / 'output' / 'storage'
        storage.mkdir(parents=True, exist_ok=True)
        outputs = [out / 'output.tsv', storage / 'bin_stats_ext.tsv']
        if 'marker_gene_stats' in cls._extra_outputs(inputs):
            outputs.append(storage / 'marker_gene_stats.tsv')
        return outputs

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {'required': {'marker_file': ('TSV', {'description': 'Marker gene set used for CheckM QA'}), 'checkm_hmm_info': ('FILE', {'description': 'Marker gene HMM info from CheckM analyze'}), 'bin_stats_analyze': ('TSV', {'description': 'Marker gene bin stats from CheckM analyze'}), 'hmmer_analyze': ('TXT', {'multiple': True, 'description': 'Marker gene HMM hits collection from CheckM analyze'})}, 'optional': {'element_identifiers': ('STRING_LIST', {'default': [], 'multiple': True, 'description': 'Optional identifiers for hmmer_analyze entries'}), 'out_format': ('STRING', {'default': '1', 'options': cls.OUT_FORMATS, 'description': 'CheckM QA report format to emit'}), 'genes_faa': ('FASTA_LIST', {'default': [], 'multiple': True, 'description': 'Protein gene sequences required when out_format is 9'}), 'genes_element_identifiers': ('STRING_LIST', {'default': [], 'multiple': True, 'description': 'Optional identifiers for genes_faa entries'}), 'exclude_markers': ('FILE', {'default': '', 'description': 'Optional marker IDs to exclude'}), 'individual_markers': ('BOOLEAN', {'default': False, 'description': 'Treat marker genes as independent during QA'}), 'skip_adj_correction': ('BOOLEAN', {'default': False, 'description': 'Do not exclude adjacent marker genes when estimating contamination'}), 'skip_pseudogene_correction': ('BOOLEAN', {'default': False, 'description': 'Skip pseudogene identification and filtering'}), 'aai_strain': ('FLOAT', {'default': 0.9, 'min': 0, 'max': 1, 'description': 'AAI threshold for strain heterogeneity'}), 'ignore_thresholds': ('BOOLEAN', {'default': False, 'description': 'Ignore model-specific score thresholds'}), 'e_value': ('FLOAT', {'default': 1e-10, 'min': 0, 'max': 1, 'description': 'E-value cutoff'}), 'length': ('FLOAT', {'default': 0.7, 'min': 0, 'max': 1, 'description': 'Minimum target-query overlap fraction'}), 'coverage': ('FILE', {'default': '', 'description': 'Optional coverage file generated by CheckM coverage'}), 'extra_outputs': ('STRING_LIST', {'default': [], 'options': cls.EXTRA_OUTPUT_OPTIONS, 'multiple': True, 'description': 'Galaxy extra outputs to collect from CheckM qa'}), 'threads': ('INT', {'default': 1, 'min': 1, 'max': 128, 'display': 'slider'})}, 'hidden': {'output': ('STRING', {})}}

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        for required in ('marker_file', 'checkm_hmm_info', 'bin_stats_analyze'):
            if not str(inputs.get(required, '')).strip():
                return f'{required} is required'
        if not cls._hmmer_analyze(inputs):
            return 'at least one hmmer_analyze value is required'
        out_format = str(inputs.get('out_format', '1'))
        if out_format not in cls.OUT_FORMATS:
            return f"out_format must be one of: {', '.join(cls.OUT_FORMATS)}"
        if out_format == '9' and (not cls._as_csv_list(inputs, 'genes_faa')):
            return 'genes_faa is required when out_format is 9'
        for name, default in {'aai_strain': 0.9, 'e_value': 1e-10, 'length': 0.7}.items():
            try:
                value = float(inputs.get(name, default))
            except (TypeError, ValueError):
                return f'{name} must be a number'
            if value < 0 or value > 1:
                return f'{name} must be between 0 and 1'
        try:
            threads = int(inputs.get('threads', 1))
        except (TypeError, ValueError):
            return 'threads must be an integer'
        if threads < 1:
            return 'threads must be >= 1'
        unknown = [value for value in cls._extra_outputs(inputs) if value not in cls.EXTRA_OUTPUT_OPTIONS]
        if unknown:
            return f"extra_outputs values must be one of: {', '.join(cls.EXTRA_OUTPUT_OPTIONS)}"
        return True
