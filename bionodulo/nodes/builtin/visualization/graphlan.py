"""graphlan — visualization node(s). One tool per file (extracted from wrapped_variant_assembly.py)."""
from __future__ import annotations
from bionodulo.nodes.builtin._wrapped_tool_utils import *


class GraphlanAnnotateNode(CommandNode):
    """Add graphical annotations to a tree before rendering it with GraPhlAn."""
    NODE_ID = 'graphlan_annotate'
    DISPLAY_NAME = 'GraPhlAn Annotate'
    REQUIRED_CONDA_PACKAGES = ['graphlan']
    CATEGORY = 'visualization'
    DESCRIPTION = 'Apply GraPhlAn annotation settings to a Newick, NHX, Nexus, or PhyloXML tree.'
    SEARCH_ALIASES = [BIONODULO_BUILTIN_ALIAS, 'GraPhlAn Annotate', 'graphlan_annotate tree annotation', 'GraPhlAn personalization', 'phylogenetic tree annotation', 'circular tree annotations']
    RETURN_TYPES = ('PHYLOXML',)
    RETURN_NAMES = ('output_tree',)
    REQUIRED_EXECUTABLES = ['graphlan_annotate.py']
    DOCUMENTATION_URL = 'https://github.com/biobakery/graphlan'
    CITATION_DOIS = ['10.7717/peerj.1029']
    CITATION_URLS = [f'{DOI_URL}10.7717/peerj.1029']
    CITATION_TEXT = 'Compact graphical representation of phylogenetic data and metadata with GraPhlAn.'
    VERSION = '1.1.3'

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        out = _out(inputs)
        cmd = ['graphlan_annotate.py']
        _add_if_value(cmd, '--annot', inputs.get('annot'))
        cmd.extend([str(inputs.get('input_tree', '')), f'{out}/output_tree.phyloxml'])
        return cmd

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        out = Path(output_dir) / cls.NODE_ID
        out.mkdir(parents=True, exist_ok=True)
        return [out / 'output_tree.phyloxml']

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {'required': {'input_tree': ('PHYLOGENY_TREE', {'description': 'Input tree in Newick, NHX, Nexus, or PhyloXML format'})}, 'optional': {'annot': ('TXT', {'default': '', 'description': 'Optional tab-delimited GraPhlAn annotation file'})}, 'hidden': {'output': ('STRING', {})}}

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        if not str(inputs.get('input_tree', '')).strip():
            return 'input_tree is required'
        return super().VALIDATE_INPUTS(inputs)


class GraphlanNode(CommandNode):
    """Render annotated phylogenetic trees with GraPhlAn."""
    NODE_ID = 'graphlan'
    DISPLAY_NAME = 'GraPhlAn'
    REQUIRED_CONDA_PACKAGES = ['graphlan']
    CATEGORY = 'visualization'
    DESCRIPTION = 'Produce graphical circular representations of taxonomic or phylogenetic trees with GraPhlAn.'
    SEARCH_ALIASES = [BIONODULO_BUILTIN_ALIAS, 'GraPhlAn', 'graphlan circular tree rendering', 'phylogenetic tree visualization', 'taxonomic tree image', 'publication-ready tree plot']
    RETURN_TYPES = ('IMAGE',)
    RETURN_NAMES = ('image',)
    REQUIRED_EXECUTABLES = ['graphlan.py']
    DOCUMENTATION_URL = 'https://github.com/biobakery/graphlan'
    CITATION_DOIS = ['10.7717/peerj.1029']
    CITATION_URLS = [f'{DOI_URL}10.7717/peerj.1029']
    CITATION_TEXT = 'Compact graphical representation of phylogenetic data and metadata with GraPhlAn.'
    VERSION = '1.1.3'
    OUTPUT_FORMATS = ['png', 'pdf', 'ps', 'eps', 'svg']

    @classmethod
    def _format(cls, inputs: dict[str, Any]) -> str:
        return str(inputs.get('image_format', inputs.get('format', 'png')) or 'png').lower()

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        out = _out(inputs)
        output_format = cls._format(inputs)
        cmd = ['graphlan.py', '--format', output_format, '--size', str(inputs.get('size', 7))]
        _add_if_value(cmd, '--pad', inputs.get('pad'))
        if output_format == 'png':
            _add_if_value(cmd, '--dpi', inputs.get('dpi'))
        cmd.extend([str(inputs.get('input_tree', '')), f'{out}/image.{output_format}'])
        return cmd

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        out = Path(output_dir) / cls.NODE_ID
        out.mkdir(parents=True, exist_ok=True)
        return [out / f'image.{cls._format(inputs)}']

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {'required': {'input_tree': ('PHYLOGENY_TREE', {'description': 'Input tree in text, NHX, or PhyloXML format'})}, 'optional': {'image_format': ('STRING', {'default': 'png', 'options': cls.OUTPUT_FORMATS, 'description': 'Output image format'}), 'size': ('INT', {'default': 7, 'min': 1, 'description': 'Output figure size'}), 'pad': ('INT', {'default': '', 'min': 0, 'description': 'Padding around the outermost graphical element'}), 'dpi': ('INT', {'default': '', 'min': 1, 'description': 'PNG resolution in dots per inch', 'displayOptions': {'show': {'image_format': ['png']}}})}, 'hidden': {'output': ('STRING', {})}}

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        if not str(inputs.get('input_tree', '')).strip():
            return 'input_tree is required'
        output_format = cls._format(inputs)
        if output_format not in cls.OUTPUT_FORMATS:
            return 'image_format must be one of: png, pdf, ps, eps, svg'
        for name, minimum in {'size': 1, 'pad': 0, 'dpi': 1}.items():
            raw = inputs.get(name)
            if raw is None or str(raw) == '':
                continue
            try:
                value = int(raw)
            except (TypeError, ValueError):
                return f'{name} must be an integer'
            if value < minimum:
                return f'{name} must be >= {minimum}'
        return super().VALIDATE_INPUTS(inputs)
