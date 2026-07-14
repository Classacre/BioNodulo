"""metabat2 — metagenomics node(s). One tool per file (extracted from wrapped_variant_assembly.py)."""
from __future__ import annotations
from bionodulo.nodes.builtin._wrapped_tool_utils import *


class MetaBAT2Node(CommandNode):
    """Bin metagenomic contigs with MetaBAT2."""
    NODE_ID = 'metabat2'
    DISPLAY_NAME = 'MetaBAT2'
    REQUIRED_CONDA_PACKAGES = ['metabat2']
    CATEGORY = 'metagenomics'
    DESCRIPTION = 'Bin metagenome assemblies using MetaBAT2 abundance and tetranucleotide-frequency clustering.'
    SEARCH_ALIASES = [BIONODULO_BUILTIN_ALIAS, 'MetaBAT2', 'MetaBAT 2', 'metagenome binning', 'metabat2 bins', 'contig abundance binning']
    RETURN_TYPES = ('DIRECTORY', 'TSV', 'DIRECTORY', 'FASTA', 'FASTA', 'FASTA', 'TXT')
    RETURN_NAMES = ('bins', 'bin_saveCls', 'bin_onlyLabel', 'lowDepth', 'tooShort', 'unbinned', 'process_log')
    REQUIRED_EXECUTABLES = ['metabat2']
    DOCUMENTATION_URL = 'https://bitbucket.org/berkeleylab/metabat/src/master/'
    CITATION_DOIS = ['10.7717/peerj.7359']
    CITATION_URLS = [f'{DOI_URL}10.7717/peerj.7359']
    CITATION_TEXT = 'MetaBAT 2: an adaptive binning algorithm for robust and efficient genome reconstruction from metagenome assemblies.'
    VERSION = '2.18.23'
    SHELL = True
    EXTRA_OUTPUTS = ['lowDepth', 'tooShort', 'unbinned', 'log']

    @classmethod
    def _extra_outputs(cls, inputs: dict[str, Any]) -> list[str]:
        return _as_list(inputs.get('extra_outputs'))

    @classmethod
    def _base_coverage_depth(cls, inputs: dict[str, Any]) -> str:
        return str(inputs.get('base_coverage_depth', 'no') or 'no')

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> str:
        out = _out(inputs)
        cmd = ['metabat2', '--inFile', str(inputs.get('inFile', '')), '--outFile', 'bins/bin']
        if cls._base_coverage_depth(inputs) == 'yes':
            if inputs.get('abdFile'):
                cmd.extend(['--abdFile', str(inputs.get('abdFile'))])
            elif inputs.get('cvExt'):
                cmd.extend(['--cvExt', str(inputs.get('cvExt'))])
        cmd.extend(['--minContig', str(inputs.get('minContig', 2500)), '--minSmallContig', str(inputs.get('minSmallContig', 1000)), '--maxP', str(inputs.get('maxP', 95)), '--minS', str(inputs.get('minS', 60)), '--maxEdges', str(inputs.get('maxEdges', 200)), '--pTNF', str(inputs.get('pTNF', 0))])
        if inputs.get('noAdd'):
            cmd.append('--noAdd')
        cmd.extend(['--minRecruitingSize', str(inputs.get('minRecruitingSize', 10)), '--minCV', str(inputs.get('minCV', 1.0)), '--minCVSum', str(inputs.get('minCVSum', 1.0)), '--seed', str(inputs.get('seed', 0)), '--minClsSize', str(inputs.get('minClsSize', 200000)), '--numThreads', f"${{GALAXY_SLOTS:-{inputs.get('threads', 4)}}}"])
        if inputs.get('onlyLabel'):
            cmd.append('--onlyLabel')
        if inputs.get('saveCls'):
            if inputs.get('fullHeader'):
                cmd.append('--fullHeader')
            cmd.append('--noBinOut')
        if 'unbinned' in cls._extra_outputs(inputs):
            cmd.append('--unbinned')
        command = _shell_join(cmd).replace("'${GALAXY_SLOTS:-", '${GALAXY_SLOTS:-').replace("}'", '}') + ' > process_log.txt'
        commands = [_shell_join(['mkdir', '-p', 'bins', out]), command]
        extra_outputs = cls._extra_outputs(inputs)
        if 'log' in extra_outputs:
            commands.append(_shell_join(['mv', 'process_log.txt', f'{out}/process_log.txt']))
        if inputs.get('saveCls') and (not inputs.get('onlyLabel')):
            commands.append(_shell_join(['cp', 'bins/bin.MemberMatrix.txt', f'{out}/bin.MemberMatrix.txt']))
        elif inputs.get('onlyLabel'):
            commands.append(_shell_join(['cp', '-r', 'bins', f'{out}/bin_onlyLabel']))
        else:
            commands.append(_shell_join(['cp', '-r', 'bins', f'{out}/bins']))
        for name, filename in [('lowDepth', 'bin.lowDepth.fa'), ('tooShort', 'bin.tooShort.fa'), ('unbinned', 'bin.unbinned.fa')]:
            if name in extra_outputs and (not inputs.get('saveCls')) and (not inputs.get('onlyLabel')):
                commands.append(_shell_join(['cp', f'bins/{filename}', f'{out}/{filename}']))
        return ' && '.join(commands)

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        out = Path(output_dir) / cls.NODE_ID
        out.mkdir(parents=True, exist_ok=True)
        outputs: list[Path]
        if inputs.get('saveCls') and (not inputs.get('onlyLabel')):
            outputs = [out / 'bin.MemberMatrix.txt']
        elif inputs.get('onlyLabel'):
            (out / 'bin_onlyLabel').mkdir(parents=True, exist_ok=True)
            outputs = [out / 'bin_onlyLabel']
        else:
            (out / 'bins').mkdir(parents=True, exist_ok=True)
            outputs = [out / 'bins']
            extra_outputs = cls._extra_outputs(inputs)
            for name, filename in [('lowDepth', 'bin.lowDepth.fa'), ('tooShort', 'bin.tooShort.fa'), ('unbinned', 'bin.unbinned.fa')]:
                if name in extra_outputs:
                    outputs.append(out / filename)
        if 'log' in cls._extra_outputs(inputs):
            outputs.append(out / 'process_log.txt')
        return outputs

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {'required': {'inFile': ('FASTA', {'description': 'FASTA or FASTA.GZ file containing contigs'})}, 'optional': {'base_coverage_depth': ('STRING', {'default': 'no', 'options': ['no', 'yes'], 'description': 'Use a base coverage depth file'}), 'abdFile': ('TSV', {'default': '', 'description': 'Depth matrix with mean and variance of base coverage'}), 'cvExt': ('TSV', {'default': '', 'description': 'Base coverage depth file without variance'}), 'minContig': ('INT', {'default': 2500, 'min': 1500}), 'minSmallContig': ('INT', {'default': 1000, 'min': 500}), 'maxP': ('INT', {'default': 95, 'min': 1, 'max': 100}), 'minS': ('INT', {'default': 60, 'min': 1, 'max': 99}), 'maxEdges': ('INT', {'default': 200, 'min': 1}), 'pTNF': ('INT', {'default': 0, 'min': 0}), 'noAdd': ('BOOLEAN', {'default': False}), 'minRecruitingSize': ('INT', {'default': 10, 'min': 0}), 'minCV': ('FLOAT', {'default': 1.0, 'min': 0}), 'minCVSum': ('FLOAT', {'default': 1.0, 'min': 0}), 'seed': ('INT', {'default': 0, 'min': 0}), 'minClsSize': ('INT', {'default': 200000, 'min': 0}), 'onlyLabel': ('BOOLEAN', {'default': False, 'description': 'Output only sequence labels'}), 'saveCls': ('BOOLEAN', {'default': False, 'description': 'Save cluster memberships as matrix'}), 'fullHeader': ('BOOLEAN', {'default': False, 'description': 'Preserve full FASTA headers when saving cluster matrix'}), 'extra_outputs': ('STRING_LIST', {'default': [], 'options': cls.EXTRA_OUTPUTS, 'description': 'Additional MetaBAT2 outputs'}), 'threads': ('INT', {'default': 4, 'min': 1, 'max': 128, 'display': 'slider'})}, 'hidden': {'output': ('STRING', {})}}

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        if not str(inputs.get('inFile', '')).strip():
            return 'inFile is required'
        base = cls._base_coverage_depth(inputs)
        if base not in {'no', 'yes'}:
            return 'base_coverage_depth must be one of: no, yes'
        if base == 'yes' and (not str(inputs.get('abdFile', '')).strip()) and (not str(inputs.get('cvExt', '')).strip()):
            return 'abdFile or cvExt is required when base_coverage_depth is yes'
        if inputs.get('saveCls') and inputs.get('onlyLabel'):
            return 'saveCls and onlyLabel cannot both be enabled'
        for output in cls._extra_outputs(inputs):
            if output not in cls.EXTRA_OUTPUTS:
                return 'extra_outputs values must be one or more of: lowDepth, tooShort, unbinned, log'
        integer_bounds = {'minContig': (1500, None), 'minSmallContig': (500, None), 'maxP': (1, 100), 'minS': (1, 99), 'maxEdges': (1, None), 'pTNF': (0, None), 'minRecruitingSize': (0, None), 'seed': (0, None), 'minClsSize': (0, None), 'threads': (1, None)}
        for name, (minimum, maximum) in integer_bounds.items():
            raw = inputs.get(name)
            if raw is None or str(raw) == '':
                continue
            try:
                value = int(raw)
            except (TypeError, ValueError):
                return f'{name} must be an integer'
            if value < minimum:
                return f'{name} must be >= {minimum}'
            if maximum is not None and value > maximum:
                return f'{name} must be between {minimum} and {maximum}'
        for name in ['minCV', 'minCVSum']:
            raw = inputs.get(name)
            if raw is None or str(raw) == '':
                continue
            try:
                value = float(raw)
            except (TypeError, ValueError):
                return f'{name} must be a number'
            if value < 0:
                return f'{name} must be >= 0'
        return super().VALIDATE_INPUTS(inputs)


class MetaBAT2JgiSummarizeBamContigDepthsNode(CommandNode):
    """Calculate contig depth matrices for MetaBAT2."""
    NODE_ID = 'metabat2_jgi_summarize_bam_contig_depths'
    DISPLAY_NAME = 'Calculate contig depths'
    REQUIRED_CONDA_PACKAGES = ['metabat2']
    CATEGORY = 'metagenomics'
    DESCRIPTION = 'Calculate per-contig coverage depth matrices from one or more BAM files for MetaBAT2 binning.'
    SEARCH_ALIASES = [BIONODULO_BUILTIN_ALIAS, 'Calculate contig depths', 'jgi_summarize_bam_contig_depths', 'MetaBAT2 depth matrix', 'contig coverage depth', 'BAM contig depths']
    RETURN_TYPES = ('TSV', 'FASTA', 'TSV', 'TSV', 'TSV')
    RETURN_NAMES = ('outputDepth', 'outputPairedContigs', 'outputGC', 'outputReadStats', 'outputKmers')
    REQUIRED_EXECUTABLES = ['jgi_summarize_bam_contig_depths']
    DOCUMENTATION_URL = 'https://bitbucket.org/berkeleylab/metabat/src/master/'
    CITATION_DOIS = ['10.7717/peerj.7359']
    CITATION_URLS = [f'{DOI_URL}10.7717/peerj.7359']
    CITATION_TEXT = 'MetaBAT 2: an adaptive binning algorithm for robust and efficient genome reconstruction from metagenome assemblies.'
    VERSION = '2.18.23'
    MODE_TYPES = ['individual', 'co']

    @classmethod
    def _mode_type(cls, inputs: dict[str, Any]) -> str:
        return str(inputs.get('mode_type', inputs.get('type', '')) or '')

    @classmethod
    def _bam_inputs(cls, inputs: dict[str, Any]) -> list[str]:
        if cls._mode_type(inputs) == 'individual':
            return _as_list(inputs.get('bam_indiv_input'))
        return _as_list(inputs.get('bam_co_inputs'))

    @classmethod
    def _use_reference(cls, inputs: dict[str, Any]) -> str:
        return str(inputs.get('use_reference', 'no') or 'no')

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        out = _out(inputs)
        cmd = ['mkdir', '-p', out, '&&', 'jgi_summarize_bam_contig_depths', '--outputDepth', f'{out}/outputDepth.tsv', '--percentIdentity', str(inputs.get('percentIdentity', 97))]
        if inputs.get('output_paired_contigs'):
            cmd.extend(['--pairedContigs', f'{out}/outputPairedContigs.fa'])
        if inputs.get('noIntraDepthVariance'):
            cmd.append('--noIntraDepthVariance')
        if inputs.get('showDepth'):
            cmd.append('--showDepth')
        cmd.extend(['--minMapQual', str(inputs.get('minMapQual', 0))])
        cmd.extend(['--weightMapQual', str(inputs.get('weightMapQual', 0.0))])
        if inputs.get('includeEdgeBases'):
            cmd.append('--includeEdgeBases')
        cmd.extend(['--maxEdgeBases', str(inputs.get('maxEdgeBases', 75))])
        if cls._use_reference(inputs) == 'yes':
            cmd.extend(['--referenceFasta', str(inputs.get('referenceFasta', ''))])
            cmd.extend(['--outputGC', f'{out}/outputGC.tsv'])
            cmd.extend(['--gcWindow', str(inputs.get('gcWindow', 100))])
            cmd.extend(['--outputReadStats', f'{out}/outputReadStats.tsv'])
            cmd.extend(['--outputKmers', f'{out}/outputKmers.tsv'])
        cmd.extend(['--shredLength', str(inputs.get('shredLength', 16000))])
        cmd.extend(['--shredDepth', str(inputs.get('shredDepth', 5))])
        cmd.extend(['--minContigLength', str(inputs.get('minContigLength', 1))])
        cmd.extend(['--minContigDepth', str(inputs.get('minContigDepth', 0.0))])
        cmd.extend(cls._bam_inputs(inputs))
        return _shell_join(cmd)

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        out = Path(output_dir) / cls.NODE_ID
        out.mkdir(parents=True, exist_ok=True)
        outputs = [out / 'outputDepth.tsv']
        if inputs.get('output_paired_contigs'):
            outputs.append(out / 'outputPairedContigs.fa')
        if cls._use_reference(inputs) == 'yes':
            outputs.extend([out / 'outputGC.tsv', out / 'outputReadStats.tsv', out / 'outputKmers.tsv'])
        return outputs

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {'required': {'mode_type': ('STRING', {'options': cls.MODE_TYPES, 'description': 'Process one BAM or multiple BAM files together'})}, 'optional': {'bam_indiv_input': ('BAM', {'default': '', 'description': 'BAM for individual mode'}), 'bam_co_inputs': ('BAM', {'default': [], 'multiple': True, 'description': 'BAM files for co-processing mode'}), 'use_reference': ('STRING', {'default': 'no', 'options': ['no', 'yes'], 'description': 'Use the reference genome for additional outputs'}), 'reference_source': ('STRING', {'default': 'cached', 'options': ['cached', 'history'], 'advanced': True}), 'referenceFasta': ('FASTA', {'default': '', 'description': 'Reference FASTA used for read mapping'}), 'gcWindow': ('INT', {'default': 100, 'min': 1, 'description': 'Sliding window size for GC calculations'}), 'percentIdentity': ('INT', {'default': 97, 'min': 0, 'max': 100, 'description': 'Minimum end-to-end percent identity'}), 'output_paired_contigs': ('BOOLEAN', {'default': False, 'description': 'Output sparse matrix of contigs spanned by paired reads'}), 'noIntraDepthVariance': ('BOOLEAN', {'default': False, 'description': 'Remove variance from mean depth'}), 'showDepth': ('BOOLEAN', {'default': False, 'description': 'Output per-base depth files'}), 'minMapQual': ('INT', {'default': 0, 'min': 0, 'description': 'Minimum mapping quality'}), 'weightMapQual': ('FLOAT', {'default': 0.0, 'min': 0, 'description': 'Weight per-base depth by mapping quality'}), 'includeEdgeBases': ('BOOLEAN', {'default': False, 'description': 'Include edge bases when calculating depth'}), 'maxEdgeBases': ('INT', {'default': 75, 'min': 0, 'description': 'Maximum edge length for depth calculation'}), 'shredLength': ('INT', {'default': 16000, 'min': 1, 'description': 'Maximum shred length'}), 'shredDepth': ('INT', {'default': 5, 'min': 1, 'description': 'Depth for overlapping shreds'}), 'minContigLength': ('INT', {'default': 1, 'min': 1, 'description': 'Minimum contig length'}), 'minContigDepth': ('FLOAT', {'default': 0.0, 'min': 0, 'description': 'Minimum depth for breaking contigs'})}, 'hidden': {'output': ('STRING', {})}}

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        mode_type = cls._mode_type(inputs)
        if mode_type not in cls.MODE_TYPES:
            return 'mode_type must be one of: individual, co'
        if mode_type == 'individual' and (not str(inputs.get('bam_indiv_input', '')).strip()):
            return 'bam_indiv_input is required for individual mode'
        if mode_type == 'co' and (not _as_list(inputs.get('bam_co_inputs'))):
            return 'at least one BAM is required for co mode'
        use_reference = cls._use_reference(inputs)
        if use_reference not in {'no', 'yes'}:
            return 'use_reference must be one of: no, yes'
        if use_reference == 'yes' and (not str(inputs.get('referenceFasta', '')).strip()):
            return 'referenceFasta is required when use_reference is yes'
        for name, minimum, maximum in [('percentIdentity', 0, 100), ('gcWindow', 1, None), ('minMapQual', 0, None), ('maxEdgeBases', 0, None), ('shredLength', 1, None), ('shredDepth', 1, None), ('minContigLength', 1, None)]:
            raw = inputs.get(name)
            if raw is None or str(raw) == '':
                continue
            try:
                value = int(raw)
            except (TypeError, ValueError):
                return f'{name} must be an integer'
            if value < minimum:
                return f'{name} must be >= {minimum}'
            if maximum is not None and value > maximum:
                return f'{name} must be between {minimum} and {maximum}'
        for name in ['weightMapQual', 'minContigDepth']:
            raw = inputs.get(name)
            if raw is None or str(raw) == '':
                continue
            try:
                value = float(raw)
            except (TypeError, ValueError):
                return f'{name} must be a number'
            if value < 0:
                return f'{name} must be >= 0'
        return super().VALIDATE_INPUTS(inputs)
