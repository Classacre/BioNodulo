"""trimn — trimming node(s). One tool per file (extracted from wrapped_amplicon_trimming.py)."""
from __future__ import annotations
from bionodulo.nodes.builtin._wrapped_tool_utils import *


class TrimNNode(CommandNode):
    """Trim N stretches and fake cut sites from scaffold FASTA assemblies."""
    NODE_ID = 'trimn'
    DISPLAY_NAME = 'TrimN'
    REQUIRED_CONDA_PACKAGES = ['trimns_vgp']
    CATEGORY = 'trimming'
    DESCRIPTION = 'Trim N stretches and remove fake cut sites from bionano hybrid scaffold FASTA assemblies.'
    SEARCH_ALIASES = [BIONODULO_BUILTIN_ALIAS, 'TrimN', 'trimns', 'trimns_vgp', 'trim_Ns_DNAnexus.py', 'remove fake cut sites', 'bionano scaffolds', 'VGP']
    RETURN_TYPES = ('FASTA',)
    RETURN_NAMES = ('trimmed_fasta',)
    REQUIRED_EXECUTABLES = ['remove_fake_cut_sites_DNAnexus.py', 'trim_Ns_DNAnexus.py', 'clip_regions_DNAnexus.py']
    DOCUMENTATION_URL = 'https://github.com/VGP/vgp-assembly/tree/master/pipeline/trim'
    CITATION_DOIS = TRIMN_CITATION_DOIS
    CITATION_URLS = [f'{DOI_URL}{doi}' for doi in TRIMN_CITATION_DOIS]
    CITATION_TEXT = TRIMN_CITATION_TEXT
    VERSION = '1.0'
    SHELL = True

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> str:
        out = _out(inputs)
        fasta_in = shlex.quote(str(inputs.get('fasta_in', '')))
        return f"remove_fake_cut_sites_DNAnexus.py {fasta_in} {shlex.quote(f'{out}/step1_out.fasta')} {shlex.quote(f'{out}/step1.log')} && trim_Ns_DNAnexus.py {fasta_in} {shlex.quote(f'{out}/step2_out.list')} && clip_regions_DNAnexus.py {shlex.quote(f'{out}/step1_out.fasta')} {shlex.quote(f'{out}/step2_out.list')} {shlex.quote(f'{out}/final_out.fasta')}"

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        out = Path(output_dir) / cls.NODE_ID
        out.mkdir(parents=True, exist_ok=True)
        return [out / 'final_out.fasta']

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        base_validation = super().VALIDATE_INPUTS(inputs)
        if base_validation is not True:
            return base_validation
        if not inputs.get('fasta_in'):
            return 'fasta_in is required'
        return True

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {'required': {'fasta_in': ('FASTA', {'description': 'FASTA assembly to trim and from which to remove N stretches and fake cut sites'})}, 'hidden': {'output': ('STRING', {})}}
