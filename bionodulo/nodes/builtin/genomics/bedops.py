"""bedops — genomics node(s). One tool per file (extracted from wrapped_bedtools.py)."""
from __future__ import annotations
from bionodulo.nodes.builtin._wrapped_tool_utils import *


class BEDOPSSortBedNode(CommandNode):
    """Sort BED records into BEDOPS canonical order."""
    NODE_ID = 'bedops_sort_bed'
    DISPLAY_NAME = 'BEDOPS Sort BED'
    REQUIRED_CONDA_PACKAGES = ['bedops']
    CATEGORY = 'genomics'
    DESCRIPTION = 'Sort one or more BED files into BEDOPS canonical order, optionally emitting only unique or duplicate records.'
    SEARCH_ALIASES = [BIONODULO_BUILTIN_ALIAS, 'bedops', 'sort-bed', 'BEDOPS sort-bed', 'sort BED', 'unique BED', 'duplicate BED']
    RETURN_TYPES = ('BED',)
    RETURN_NAMES = ('sorted_bed',)
    REQUIRED_EXECUTABLES = ['sort-bed']
    DOCUMENTATION_URL = 'https://bedops.readthedocs.io/en/latest/content/reference/file-management/sorting/sort-bed.html'
    CITATION_DOIS = [BEDOPS_CITATION_DOI]
    CITATION_URLS = [f'{DOI_URL}{BEDOPS_CITATION_DOI}']
    CITATION_TEXT = BEDOPS_CITATION_TEXT
    VERSION = '2.4.42'
    SHELL = True

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        cmd = ['sort-bed', '--max-mem', f"{int(inputs.get('memory_mb', 1024) or 1024)}M", '--tmpdir', str(inputs.get('tmpdir') or '.')]
        if inputs.get('unique'):
            cmd.append('--unique')
        if inputs.get('duplicates'):
            cmd.append('--duplicates')
        cmd.extend(_as_list(inputs.get('inputs')))
        _add_shell_redirect(cmd, f'{_out(inputs)}/sorted.bed')
        return cmd

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        return [_bedtools_common_output(cls.NODE_ID, 'sorted.bed', output_dir)]

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        base_validation = super().VALIDATE_INPUTS(inputs)
        if base_validation is not True:
            return base_validation
        if not _as_list(inputs.get('inputs')):
            return 'at least one BED input is required'
        if inputs.get('unique') and inputs.get('duplicates'):
            return 'unique and duplicates modes are mutually exclusive'
        return True

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {'required': {'inputs': ('BED_LIST', {'description': 'One or more BED files to sort'})}, 'optional': {'unique': ('BOOLEAN', {'default': False, 'description': 'Output only unique BED elements'}), 'duplicates': ('BOOLEAN', {'default': False, 'description': 'Output only duplicate BED elements'}), 'memory_mb': ('INT', {'default': 1024, 'min': 1, 'description': 'Maximum memory for sort-bed in MB'}), 'tmpdir': ('DIRECTORY', {'description': 'Temporary directory for sorting files larger than memory', 'advanced': True})}, 'hidden': {'output': ('STRING', {})}}
