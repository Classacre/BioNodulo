"""gamma — annotation node(s). One tool per file (extracted from wrapped_phylogeny_assembly.py)."""
from __future__ import annotations
from bionodulo.nodes.builtin._wrapped_tool_utils import *


class GAMMANode(CommandNode):
    """Find and annotate microbial gene matches with GAMMA."""
    NODE_ID = 'gamma'
    DISPLAY_NAME = 'GAMMA'
    REQUIRED_CONDA_PACKAGES = ['GAMMA']
    CATEGORY = 'annotation'
    DESCRIPTION = 'Find and annotate gene matches in microbial assemblies using protein-coding identity with GAMMA.'
    SEARCH_ALIASES = [BIONODULO_BUILTIN_ALIAS, 'GAMMA', 'Gene Allele Mutation Microbial Assessment', 'gene match annotation', 'antimicrobial resistance genes', 'virulence genes', 'protein coding identity']
    RETURN_TYPES = ('TSV', 'GFF', 'FASTA')
    RETURN_NAMES = ('gamma_out', 'gamma_gff', 'gamma_fasta')
    REQUIRED_EXECUTABLES = ['GAMMA.py']
    DOCUMENTATION_URL = 'https://github.com/rastanton/GAMMA'
    CITATION_DOIS = [GAMMA_CITATION_DOI]
    CITATION_URLS = [f'{DOI_URL}{GAMMA_CITATION_DOI}']
    CITATION_TEXT = GAMMA_CITATION_TEXT
    VERSION = '2.2'
    SHELL = True

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> str:
        cmd = ['GAMMA.py', str(inputs.get('input_fasta', '')), str(inputs.get('input_db', '')), f'{_out(inputs)}/gamma_out']
        if inputs.get('all'):
            cmd.append('-a')
        cmd.extend(['-i', str(inputs.get('identity', 90))])
        if inputs.get('extended'):
            cmd.append('-e')
        if inputs.get('fasta'):
            cmd.append('-f')
        if inputs.get('gff'):
            cmd.append('-g')
        if inputs.get('headless'):
            cmd.append('-l')
        return _shell_join(cmd)

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        out = Path(output_dir) / cls.NODE_ID
        out.mkdir(parents=True, exist_ok=True)
        outputs = [out / 'gamma_out.gamma']
        if inputs.get('gff'):
            outputs.append(out / 'gamma_out.gff')
        if inputs.get('fasta'):
            outputs.append(out / 'gamma_out.fasta')
        return outputs

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        if not inputs.get('input_fasta'):
            return 'input FASTA is required'
        if not inputs.get('input_db'):
            return 'gene database FASTA is required'
        try:
            identity = int(inputs.get('identity', 90))
        except (TypeError, ValueError):
            return 'identity must be an integer'
        if not 0 <= identity <= 100:
            return 'identity must be between 0 and 100'
        base_validation = super().VALIDATE_INPUTS(inputs)
        if base_validation is not True:
            return base_validation
        return True

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {'required': {'input_fasta': ('FASTA', {'description': 'Genome or assembly FASTA to screen'}), 'input_db': ('FASTA', {'description': 'Multifasta coding-sequence gene database'})}, 'optional': {'all': ('BOOLEAN', {'default': False, 'description': 'Include all gene matches, including overlaps'}), 'identity': ('INT', {'default': 90, 'min': 0, 'max': 100, 'description': 'Minimum BLAT nucleotide identity percent'}), 'extended': ('BOOLEAN', {'default': False, 'description': 'Return all gene mutations'}), 'fasta': ('BOOLEAN', {'default': False, 'description': 'Write matched genes as FASTA'}), 'gff': ('BOOLEAN', {'default': False, 'description': 'Write matched genes as GFF'}), 'headless': ('BOOLEAN', {'default': False, 'description': 'Remove column headers from the GAMMA table'})}, 'hidden': {'output': ('STRING', {})}}


class GAMMASNode(CommandNode):
    """Find nucleotide or protein gene matches with GAMMA-S."""
    NODE_ID = 'gamma_s'
    DISPLAY_NAME = 'GAMMA-S'
    REQUIRED_CONDA_PACKAGES = ['GAMMA']
    CATEGORY = 'annotation'
    DESCRIPTION = 'Find gene matches in microbial assemblies using nucleotide identity with GAMMA-S.'
    SEARCH_ALIASES = [BIONODULO_BUILTIN_ALIAS, 'GAMMA-S', 'gamma_s', 'Gene Allele Mutation Microbial Assessment Sequence', 'nucleotide gene matching', 'protein-protein comparisons', 'gene match annotation']
    RETURN_TYPES = ('TSV',)
    RETURN_NAMES = ('gamma_s_out',)
    REQUIRED_EXECUTABLES = ['GAMMA-S.py']
    DOCUMENTATION_URL = 'https://github.com/rastanton/GAMMA'
    CITATION_DOIS = [GAMMA_CITATION_DOI]
    CITATION_URLS = [f'{DOI_URL}{GAMMA_CITATION_DOI}']
    CITATION_TEXT = GAMMA_CITATION_TEXT
    VERSION = '2.2'
    SHELL = True

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> str:
        cmd = ['GAMMA-S.py', str(inputs.get('input_fasta', '')), str(inputs.get('input_db', '')), f'{_out(inputs)}/gamma-s_out']
        if inputs.get('all'):
            cmd.append('-a')
        cmd.extend(['-i', str(inputs.get('identity', 90))])
        if inputs.get('extended'):
            cmd.append('-e')
        if inputs.get('protein'):
            cmd.append('-p')
        cmd.extend(['-m', str(inputs.get('minimum', 20))])
        return _shell_join(cmd)

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        out = Path(output_dir) / cls.NODE_ID
        out.mkdir(parents=True, exist_ok=True)
        return [out / 'gamma-s_out.gamma']

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        if not inputs.get('input_fasta'):
            return 'input FASTA is required'
        if not inputs.get('input_db'):
            return 'gene database FASTA is required'
        for key in ('identity', 'minimum'):
            try:
                value = int(inputs.get(key, 90 if key == 'identity' else 20))
            except (TypeError, ValueError):
                return f'{key} must be an integer'
            if not 0 <= value <= 100:
                return f'{key} must be between 0 and 100'
        base_validation = super().VALIDATE_INPUTS(inputs)
        if base_validation is not True:
            return base_validation
        return True

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {'required': {'input_fasta': ('FASTA', {'description': 'Genome, assembly, or protein FASTA to screen'}), 'input_db': ('FASTA', {'description': 'Multifasta gene or protein database'})}, 'optional': {'all': ('BOOLEAN', {'default': False, 'description': 'Include all gene matches, including overlaps'}), 'identity': ('INT', {'default': 90, 'min': 0, 'max': 100, 'description': 'Minimum identity percent'}), 'extended': ('BOOLEAN', {'default': False, 'description': 'Return all gene mutations'}), 'protein': ('BOOLEAN', {'default': False, 'description': 'Perform protein-protein comparisons'}), 'minimum': ('INT', {'default': 20, 'min': 0, 'max': 100, 'description': 'Minimum length percent match'})}, 'hidden': {'output': ('STRING', {})}}
