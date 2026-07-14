"""beagle — variant node(s). One tool per file (extracted from wrapped_variant_assembly.py)."""
from __future__ import annotations
from bionodulo.nodes.builtin._wrapped_tool_utils import *


class BeagleNode(CommandNode):
    """Phase genotypes and impute ungenotyped markers with Beagle."""
    NODE_ID = 'beagle'
    DISPLAY_NAME = 'Beagle'
    REQUIRED_CONDA_PACKAGES = ['beagle']
    CATEGORY = 'variant'
    DESCRIPTION = 'Phase genotypes and impute ungenotyped markers from VCF genotype data using Beagle.'
    SEARCH_ALIASES = [BIONODULO_BUILTIN_ALIAS, 'Beagle', 'Beagle genotype imputation', 'genotype phasing', 'impute ungenotyped markers', 'haplotype phasing', 'VCF imputation', 'GWAS']
    RETURN_TYPES = ('VCF', 'TXT')
    RETURN_NAMES = ('vcf_file', 'log_file')
    REQUIRED_EXECUTABLES = ['beagle']
    DOCUMENTATION_URL = 'https://faculty.washington.edu/browning/beagle/beagle.html'
    CITATION_DOIS = ['10.1016/j.ajhg.2018.07.015', '10.1086/521987']
    CITATION_URLS = [f'{DOI_URL}{doi}' for doi in CITATION_DOIS]
    CITATION_TEXT = 'Beagle supports genotype phasing, genotype imputation, and haplotype inference from genotype data.'
    VERSION = '5.4_29Oct24.c8e'
    SHELL = True

    @classmethod
    def _bool_text(cls, value: Any, default: bool) -> str:
        if value is None or value == '':
            value = default
        if isinstance(value, str):
            return 'false' if value.lower() in {'false', '0', 'no'} else 'true'
        return 'true' if bool(value) else 'false'

    @classmethod
    def _output_name(cls, inputs: dict[str, Any]) -> str:
        return 'phased_imputed.vcf.gz' if str(inputs.get('out_format', 'vcf')) == 'vcf_bgzip' else 'phased_imputed.vcf'

    @classmethod
    def _ref_path(cls, inputs: dict[str, Any], out: str) -> str:
        ref_ext = str(inputs.get('ref_ext', Path(str(inputs.get('ref', 'ref.vcf'))).suffix.lstrip('.') or 'vcf'))
        return f'{out}/ref.{ref_ext}'

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        out = _out(inputs)
        cmd: list[str] = []
        if inputs.get('ref'):
            cmd.extend(['ln', '-s', str(inputs.get('ref')), cls._ref_path(inputs, out), '&&'])
        gt = str(inputs.get('gt', ''))
        gt_arg = gt
        if str(inputs.get('gt_ext', '')).lower() == 'vcf_bgzip':
            gt_arg = f'{out}/tmp.gz'
            cmd.extend(['ln', '-s', gt, gt_arg, '&&'])
        cmd.extend(['beagle', f'gt={gt_arg}'])
        if inputs.get('ref'):
            cmd.append(f'ref={cls._ref_path(inputs, out)}')
        for key in ['map', 'chrom', 'excludesamples', 'excludemarkers']:
            if inputs.get(key):
                cmd.append(f'{key}={inputs[key]}')
        cmd.extend([f"ne={inputs.get('ne', 1000000)}", f"window={inputs.get('window', 40.0)}", f"overlap={inputs.get('overlap', 2.0)}"])
        if inputs.get('seed') not in (None, ''):
            cmd.append(f"seed={inputs.get('seed')}")
        if inputs.get('err') not in (None, ''):
            cmd.append(f"err={inputs.get('err')}")
        cmd.extend([f"burnin={inputs.get('burnin', 3)}", f"iterations={inputs.get('iterations', 12)}", f"phase-states={inputs.get('phase_states', inputs.get('phase-states', 280))}", f"impute={cls._bool_text(inputs.get('impute'), True)}", f"imp-states={inputs.get('imp_states', inputs.get('imp-states', 1600))}", f"imp-segment={inputs.get('imp_segment', inputs.get('imp-segment', 6.0))}", f"imp-step={inputs.get('imp_step', inputs.get('imp-step', 0.1))}", f"cluster={inputs.get('cluster', 0.005)}", f"ap={cls._bool_text(inputs.get('ap'), False)}", f"gp={cls._bool_text(inputs.get('gp'), False)}", f'out={out}/out', f"nthreads=${{GALAXY_SLOTS:-{inputs.get('threads', 1)}}}"])
        if str(inputs.get('out_format', 'vcf')) == 'vcf_bgzip':
            cmd.extend(['&&', 'mv', f'{out}/out.vcf.gz', f'{out}/phased_imputed.vcf.gz'])
        else:
            cmd.extend(['&&', 'gunzip', f'{out}/out.vcf.gz', '&&', 'mv', f'{out}/out.vcf', f'{out}/phased_imputed.vcf'])
        return cmd

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        out = Path(output_dir) / cls.NODE_ID
        out.mkdir(parents=True, exist_ok=True)
        outputs = [out / cls._output_name(inputs)]
        if inputs.get('output_log'):
            outputs.append(out / 'out.log')
        return outputs

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {'required': {'gt': ('VCF', {'description': 'VCF file containing genotypes for study samples'})}, 'optional': {'gt_ext': ('STRING', {'default': 'vcf', 'options': ['vcf', 'vcf_bgzip'], 'advanced': True}), 'ref': ('VCF', {'default': '', 'description': 'Optional phased reference panel in VCF or bref3 format'}), 'ref_ext': ('STRING', {'default': 'vcf', 'options': ['vcf', 'vcf_bgzip', 'bref3'], 'advanced': True}), 'map': ('TXT', {'default': '', 'description': 'Optional PLINK genetic map in cM units'}), 'chrom': ('STRING', {'default': '', 'description': 'Optional chromosome interval such as 22:100-'}), 'excludesamples': ('TXT', {'default': '', 'description': 'Samples to exclude from analysis'}), 'excludemarkers': ('TXT', {'default': '', 'description': 'Markers to exclude from analysis'}), 'ne': ('INT', {'default': 1000000, 'min': 0, 'description': 'Effective population size'}), 'window': ('FLOAT', {'default': 40.0, 'min': 0, 'description': 'Window length in cM'}), 'overlap': ('FLOAT', {'default': 2.0, 'min': 0, 'description': 'Window overlap in cM'}), 'err': ('FLOAT', {'default': '', 'min': 0, 'max': 1, 'description': 'Allele mismatch probability'}), 'seed': ('INT', {'default': '', 'description': 'Random seed'}), 'output_log': ('BOOLEAN', {'default': False, 'description': 'Keep Beagle log file'}), 'burnin': ('INT', {'default': 3, 'min': 0, 'description': 'Maximum burn-in iterations'}), 'iterations': ('INT', {'default': 12, 'min': 0, 'description': 'Phasing iterations'}), 'phase_states': ('INT', {'default': 280, 'min': 0, 'description': 'Model states for phasing'}), 'impute': ('BOOLEAN', {'default': True, 'description': 'Impute markers present in the reference panel'}), 'imp_states': ('INT', {'default': 1600, 'min': 0, 'description': 'Model states for imputation'}), 'imp_segment': ('FLOAT', {'default': 6.0, 'min': 0, 'description': 'Minimum cM length of imputation haplotype segments'}), 'imp_step': ('FLOAT', {'default': 0.1, 'min': 0, 'description': 'Step length in cM for short IBS detection'}), 'cluster': ('FLOAT', {'default': 0.005, 'min': 0, 'description': 'Maximum cM distance in a marker cluster'}), 'ap': ('BOOLEAN', {'default': False, 'description': 'Include posterior allele probabilities'}), 'gp': ('BOOLEAN', {'default': False, 'description': 'Include posterior genotype probabilities'}), 'out_format': ('STRING', {'default': 'vcf', 'options': ['vcf', 'vcf_bgzip'], 'description': 'Output VCF datatype'}), 'threads': ('INT', {'default': 1, 'min': 1, 'max': 128, 'display': 'slider'})}, 'hidden': {'output': ('STRING', {})}}

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        if not str(inputs.get('gt', '')).strip():
            return 'VCF genotype input is required'
        window = float(inputs.get('window', 40.0) or 0)
        overlap = float(inputs.get('overlap', 2.0) or 0)
        if window < overlap * 1.1:
            return 'window must be at least 1.1 times overlap'
        if inputs.get('err') not in (None, ''):
            err = float(inputs.get('err', 0))
            if err < 0 or err > 1:
                return 'err must be between 0 and 1'
        return super().VALIDATE_INPUTS(inputs)
