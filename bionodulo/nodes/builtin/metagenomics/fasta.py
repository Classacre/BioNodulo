"""fasta — metagenomics node(s). One tool per file (extracted from wrapped_assembly_typing.py)."""
from __future__ import annotations
from bionodulo.nodes.builtin._wrapped_tool_utils import *


class FastaToContig2BinNode(CommandNode):
    """Convert genome-bin FASTA files into a DAS Tool contig-to-bin table."""
    NODE_ID = 'fasta_to_contig2bin'
    DISPLAY_NAME = 'FASTA to Contig2Bin'
    REQUIRED_CONDA_PACKAGES = ['das_tool']
    CATEGORY = 'metagenomics'
    DESCRIPTION = 'Convert a list of genome-bin FASTA files into a tabular contig-to-bin assignment table for DAS Tool.'
    SEARCH_ALIASES = [BIONODULO_BUILTIN_ALIAS, 'Fasta_to_Contig2Bin', 'Fasta_to_Contig2Bin.sh', 'DAS Tool helper', 'contig2bin', 'contigs2bin', 'genome bins', 'bin FASTA']
    RETURN_TYPES = ('TSV',)
    RETURN_NAMES = ('contigs2bin',)
    REQUIRED_EXECUTABLES = ['Fasta_to_Contig2Bin.sh']
    DOCUMENTATION_URL = 'https://github.com/cmks/DAS_Tool#preparation-of-input-files'
    CITATION_DOIS = ['10.1038/s41564-018-0171-1']
    CITATION_URLS = ['https://doi.org/10.1038/s41564-018-0171-1']
    CITATION_TEXT = 'Recovery of genomes from metagenomes via a dereplication, aggregation and scoring strategy.'
    VERSION = '1.1.7'
    SHELL = True

    @classmethod
    def _input_files(cls, inputs: dict[str, Any]) -> list[str]:
        return _as_list(inputs.get('inputs', inputs.get('input')))

    @classmethod
    def _element_identifiers(cls, inputs: dict[str, Any], input_files: list[str]) -> list[str]:
        raw = inputs.get('element_identifiers', inputs.get('identifiers', inputs.get('labels')))
        if isinstance(raw, (list, tuple)):
            identifiers = [str(identifier) if identifier is not None else '' for identifier in raw]
        elif raw is None or raw == '':
            identifiers = []
        else:
            identifiers = [str(raw)]
        return [_safe_identifier(identifiers[index]) if index < len(identifiers) and identifiers[index] else _safe_name(input_file) for index, input_file in enumerate(input_files)]

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        out = _out(inputs)
        input_dir = f'{out}/inputs'
        input_files = cls._input_files(inputs)
        identifiers = cls._element_identifiers(inputs, input_files)
        cmd = ['mkdir', '-p', input_dir]
        for input_file, identifier in zip(input_files, identifiers, strict=True):
            cmd.extend(['&&', 'ln', '-sf', input_file, f'{input_dir}/{identifier}.fasta'])
        cmd.extend(['&&', 'Fasta_to_Contig2Bin.sh', '--extension', 'fasta', '--input_folder', input_dir, '>', f'{out}/contigs2bin.tsv'])
        return cmd

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        out = Path(output_dir) / cls.NODE_ID
        out.mkdir(parents=True, exist_ok=True)
        return [out / 'contigs2bin.tsv']

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {'required': {'inputs': ('FASTA_LIST', {'description': 'Genome-bin FASTA files to convert into contig-to-bin assignments'})}, 'optional': {'element_identifiers': ('STRING', {'list': True, 'description': 'Optional bin labels matching the FASTA collection element identifiers'})}, 'hidden': {'output': ('STRING', {})}}
