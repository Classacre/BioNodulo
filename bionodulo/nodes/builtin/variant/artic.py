"""artic — variant node(s). One tool per file (extracted from wrapped_annotation_sequence.py)."""
from __future__ import annotations
from bionodulo.nodes.builtin._wrapped_tool_utils import *


class ArticMinionNode(CommandNode):
    """Call variants and build consensus sequence outputs with ARTIC minion."""
    NODE_ID = 'artic_minion'
    DISPLAY_NAME = 'ARTIC minion'
    REQUIRED_CONDA_PACKAGES = ['artic']
    CATEGORY = 'variant'
    DESCRIPTION = 'Build consensus sequences and call variants from amplicon-based Nanopore reads with ARTIC minion.'
    SEARCH_ALIASES = [BIONODULO_BUILTIN_ALIAS, 'ARTIC minion', 'artic_minion', 'amplicon consensus', 'Nanopore variants', 'Clair3', 'primertrimmed BAM']
    RETURN_TYPES = ('BAM', 'TSV', 'VCF_GZ', 'VCF_GZ', 'VCF_GZ', 'FASTA', 'TSV', 'TXT')
    RETURN_NAMES = ('alignment_trimmed', 'alignment_report', 'variants_merged_vcf', 'variants_fail_vcf', 'variants_pass_vcf', 'consensus_fasta', 'coverage_mask', 'analysis_log')
    REQUIRED_EXECUTABLES = ['artic', 'run_clair3.sh', 'samtools', 'bgzip', 'sed', 'tar']
    DOCUMENTATION_URL = ARTIC_DOCUMENTATION_URL
    CITATION_DOIS = []
    CITATION_URLS = [ARTIC_CITATION_URL]
    CITATION_TEXT = ARTIC_CITATION_TEXT
    VERSION = '1.7.3+galaxy1'
    SHELL = True
    FETCH_OPTIONS = ['yes', 'no']
    MODEL_SOURCES = ['built-in', 'datatable', 'history']
    BUILT_IN_MODELS = ['r941_prom_sup_g5014', 'r941_prom_hac_g360+g422']
    PRIMER_SCHEME_SOURCES = ['tool_data_table', 'history']
    REFERENCE_SOURCES = ['cached', 'history']

    @classmethod
    def _sample_name(cls, inputs: dict[str, Any]) -> str:
        return str(inputs.get('sample_name', 'sample') or 'sample')

    @classmethod
    def _model_commands(cls, inputs: dict[str, Any]) -> list[str]:
        source = str(inputs.get('model_source', 'built-in') or 'built-in')
        if source == 'history':
            model = str(inputs.get('model', '') or '')
            quoted_model = shlex.quote(model)
            return [f'OUTNAME=$(tar -tf {quoted_model} | head -1 | cut -f1 -d/)', f'tar -xf {quoted_model}', 'mv $OUTNAME clair3_model']
        if source == 'datatable':
            model = str(inputs.get('model', '') or '')
            return [_shell_join(['ln', '-s', model, 'clair3_model'])]
        model = str(inputs.get('select_built_in', 'r941_prom_sup_g5014') or 'r941_prom_sup_g5014')
        return [f'ln -s $(dirname $(which run_clair3.sh))/models/{shlex.quote(model)} clair3_model']

    @classmethod
    def _reference_commands(cls, inputs: dict[str, Any]) -> list[str]:
        if str(inputs.get('fetch', 'yes') or 'yes') != 'no':
            return []
        return [_shell_join(['ln', '-s', str(inputs.get('bed', '') or ''), 'primer.bed']), _shell_join(['ln', '-s', str(inputs.get('reference', '') or ''), 'reference.fasta']), _shell_join(['samtools', 'faidx', 'reference.fasta'])]

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> str:
        commands = [*cls._model_commands(inputs), *cls._reference_commands(inputs)]
        cmd = ['artic', 'minion', '--read-file', str(inputs.get('read_file', '') or ''), '--threads', '${GALAXY_SLOTS:-1}']
        if str(inputs.get('fetch', 'yes') or 'yes') == 'no':
            cmd.extend(['--bed', 'primer.bed', '--ref', 'reference.fasta'])
        else:
            cmd.extend(['--scheme-name', str(inputs.get('scheme_name', '') or ''), '--scheme-version', str(inputs.get('scheme_version', '') or ''), '--scheme-length', str(inputs.get('scheme_length', 400))])
        cmd.extend(['--model-dir', '.', '--model', 'clair3_model', '--min-depth', str(inputs.get('min_depth', 20)), '--min-mapq', str(inputs.get('min_mapq', 20)), '--primer-match-threshold', str(inputs.get('primer_match_threshold', 35))])
        if inputs.get('align_consensus', False):
            cmd.append('--align-consensus')
        if inputs.get('linearise_fasta', False):
            cmd.append('--linearise-fasta')
        if inputs.get('allow_mismatched_primers', False):
            cmd.append('--allow-mismatched-primers')
        normalise = int(inputs.get('normalise', 0))
        if normalise > 0:
            cmd.extend(['--normalise', str(normalise)])
        sample_name = cls._sample_name(inputs)
        quoted_sample_name = shlex.quote(sample_name)
        minion_command = _shell_join(cmd).replace("'${GALAXY_SLOTS:-1}'", '${GALAXY_SLOTS:-1}')
        commands.append(f'''{minion_command} "'{quoted_sample_name}'"''')
        commands.append(_shell_join(['bgzip', '-f', f'{sample_name}.fail.vcf']))
        commands.append(f"""sed -i "1s/'{quoted_sample_name}'/{quoted_sample_name}/" {shlex.quote(f'{sample_name}.consensus.fasta')}""")
        return ' && '.join(commands)

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        out = Path(output_dir) / cls.NODE_ID
        out.mkdir(parents=True, exist_ok=True)
        sample_name = cls._sample_name(inputs)
        return [out / f'{sample_name}.primertrimmed.rg.sorted.bam', out / f'{sample_name}.alignreport.txt', out / f'{sample_name}.merged.vcf.gz', out / f'{sample_name}.fail.vcf.gz', out / f'{sample_name}.pass.vcf.gz', out / f'{sample_name}.consensus.fasta', out / f'{sample_name}.coverage_mask.txt', out / f'{sample_name}.minion.log.txt']

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        if not inputs.get('read_file'):
            return 'read_file is required'
        fetch = str(inputs.get('fetch', 'yes') or 'yes')
        if fetch not in cls.FETCH_OPTIONS:
            return f"fetch must be one of: {', '.join(cls.FETCH_OPTIONS)}"
        if fetch == 'yes':
            if not inputs.get('scheme_name'):
                return 'scheme_name is required when fetch is yes'
            if not inputs.get('scheme_version'):
                return 'scheme_version is required when fetch is yes'
        else:
            if not inputs.get('bed'):
                return 'bed is required when fetch is no'
            if not inputs.get('reference'):
                return 'reference is required when fetch is no'
        model_source = str(inputs.get('model_source', 'built-in') or 'built-in')
        if model_source not in cls.MODEL_SOURCES:
            return f"model_source must be one of: {', '.join(cls.MODEL_SOURCES)}"
        if model_source == 'datatable' and str(inputs.get('model_data_source', '') or '') == 'rerio' and (not inputs.get('ont_license_agree', False)):
            return 'ont_license_agree is required for Rerio models'
        try:
            normalise = int(inputs.get('normalise', 0))
        except (TypeError, ValueError):
            return 'normalise must be an integer'
        if normalise < 0:
            return 'normalise must be greater than or equal to 0'
        return True

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {'required': {'read_file': ('FASTQ', {'description': 'Nanopore FASTQ reads for ARTIC minion'})}, 'optional': {'sample_name': ('STRING', {'default': 'sample', 'description': 'Sample name prefix for minion outputs'}), 'fetch': ('STRING', {'default': 'yes', 'options': cls.FETCH_OPTIONS, 'description': 'Fetch a named ARTIC primer scheme'}), 'scheme_name': ('STRING', {'default': '', 'description': 'ARTIC scheme name when fetching primers'}), 'scheme_version': ('STRING', {'default': '', 'description': 'ARTIC scheme version when fetching primers'}), 'scheme_length': ('INT', {'default': 400, 'min': 1, 'description': 'ARTIC scheme amplicon length'}), 'primer_scheme_source_selector': ('STRING', {'default': 'tool_data_table', 'options': cls.PRIMER_SCHEME_SOURCES}), 'bed': ('BED', {'description': 'Primer BED file when not fetching a scheme'}), 'reference_source_selector': ('STRING', {'default': 'cached', 'options': cls.REFERENCE_SOURCES}), 'reference': ('FASTA', {'description': 'Reference FASTA when not fetching a scheme'}), 'model_source': ('STRING', {'default': 'built-in', 'options': cls.MODEL_SOURCES, 'description': 'Clair3 model source'}), 'select_built_in': ('STRING', {'default': 'r941_prom_sup_g5014', 'options': cls.BUILT_IN_MODELS}), 'model': ('FILE', {'description': 'Clair3 model from tool data or history'}), 'model_data_source': ('STRING', {'default': '', 'advanced': True}), 'ont_license_agree': ('BOOLEAN', {'default': False, 'advanced': True}), 'min_depth': ('INT', {'default': 20, 'min': 0}), 'min_mapq': ('INT', {'default': 20, 'min': 0}), 'primer_match_threshold': ('INT', {'default': 35, 'min': 0}), 'normalise': ('INT', {'default': 0, 'min': 0}), 'align_consensus': ('BOOLEAN', {'default': False}), 'linearise_fasta': ('BOOLEAN', {'default': False}), 'allow_mismatched_primers': ('BOOLEAN', {'default': False})}, 'hidden': {'output': ('STRING', {})}}
