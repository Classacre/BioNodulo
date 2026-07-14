"""odgi — pangenomics node(s). One tool per file (extracted from pangenomics.py)."""
from __future__ import annotations
from pathlib import Path
import re
import shlex
from typing import Any
from bionodulo.nodes.command_node import CommandNode
def _split_path_list(value: Any) -> list[str]:
    if isinstance(value, list | tuple):
        return [str(item) for item in value if str(item)]
    return [item for item in re.split('[\\s,]+', str(value or '')) if item]
def _safe_output_stem(value: Any, fallback: str) -> str:
    text = str(value or '').strip()
    if not text:
        text = fallback
    stem = Path(text).stem
    stem = re.sub('\\.(gz|bz2|xz|zip)$', '', stem)
    stem = re.sub('[^A-Za-z0-9_.-]+', '_', stem).strip('._-')
    return stem or fallback


class ODGIBuildNode(CommandNode):
    """Build an ODGI graph from a GFA pangenome graph and export JSON stats."""
    NODE_ID = 'odgi_build'
    DISPLAY_NAME = 'odgi Build'
    CATEGORY = 'pangenomics'
    DESCRIPTION = 'Build an ODGI pangenome graph from GFA input and summarize graph statistics.'
    SEARCH_ALIASES = ['odgi', 'odgi build', 'gfa to odgi', 'pangenome graph', 'graph conversion', 'stats']
    RETURN_TYPES = ('ODGI', 'JSON')
    RETURN_NAMES = ('graph_odgi', 'stats')
    REQUIRED_EXECUTABLES = ['odgi']
    REQUIRED_CONDA_PACKAGES = ['odgi']
    DOCUMENTATION_URL = 'https://odgi.readthedocs.io/'
    VERSION = '0.9.0'
    SHELL = True

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        base_validation = super().VALIDATE_INPUTS(inputs)
        if base_validation is not True:
            return base_validation
        if int(inputs.get('threads', 0) or 0) < 0:
            return 'odgi Build threads must be zero or greater.'
        return True

    @classmethod
    def _planned_paths(cls, inputs: dict[str, Any], output_dir: str | Path) -> tuple[Path, Path]:
        node_out = Path(output_dir)
        fallback_stem = _safe_output_stem(inputs.get('gfa_graph'), 'graph')
        stem = _safe_output_stem(inputs.get('output_name'), fallback_stem)
        return (node_out / f'{stem}.odgi', node_out / f'{stem}.stats.json')

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        validation = cls.VALIDATE_INPUTS(inputs)
        if validation is not True:
            raise ValueError(str(validation))
        out_dir = Path(str(inputs.get('output', '.')))
        graph_odgi, stats = cls._planned_paths(inputs, out_dir)
        threads = int(inputs.get('threads', 0) or 0)
        cmd = ['odgi', 'build', '-g', str(inputs.get('gfa_graph', '')), '-o', str(graph_odgi)]
        if threads > 0:
            cmd.extend(['-t', str(threads)])
        if inputs.get('compact_ids'):
            cmd.append('-c')
        if inputs.get('validate'):
            cmd.append('-v')
        cmd.extend(['&&', 'odgi', 'stats', '-i', str(graph_odgi), '-j', '>', str(stats)])
        return cmd

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        node_out = Path(output_dir) / cls.NODE_ID
        node_out.mkdir(parents=True, exist_ok=True)
        return list(cls._planned_paths(inputs, node_out))

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {'required': {'gfa_graph': ('GFA', {'description': 'Input pangenome graph in GFA format'})}, 'optional': {'threads': ('INT', {'default': 4, 'min': 0, 'max': 64, 'display': 'slider'}), 'compact_ids': ('BOOLEAN', {'default': False, 'description': 'Compact node identifiers while building'}), 'validate': ('BOOLEAN', {'default': False, 'description': 'Ask odgi build to validate input graph consistency'}), 'output_name': ('STRING', {'default': '', 'description': 'Optional output filename stem'})}, 'hidden': {'output': ('STRING', {})}}


class ODGIVisualizeNode(CommandNode):
    """Visualize pangenome graph layouts with odgi."""
    NODE_ID = 'odgi_visualize'
    DISPLAY_NAME = 'odgi Visualize'
    CATEGORY = 'pangenomics'
    DESCRIPTION = 'Visualize pangenome graphs in 1D and 2D layout using odgi.'
    SEARCH_ALIASES = ['odgi', 'visualize', 'pangenome', 'graph viz', 'graph layout']
    RETURN_TYPES = ('IMAGE', 'IMAGE')
    RETURN_NAMES = ('graph_1d', 'graph_2d')
    REQUIRED_EXECUTABLES = ['odgi']
    REQUIRED_CONDA_PACKAGES = ['odgi']
    DOCUMENTATION_URL = 'https://odgi.readthedocs.io/'
    VERSION = '0.9.0'
    SHELL = True

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        out_dir = Path(str(inputs.get('output', '.')))
        graph = out_dir / 'graph.og'
        sorted_graph = out_dir / 'sorted.og'
        graph_1d = out_dir / 'graph_1d.png'
        graph_2d = out_dir / 'graph_2d.png'
        cmd = ['odgi', 'build', '-g', str(inputs.get('gfa_graph', '')), '-o', str(graph), '&&', 'odgi', 'viz', '-i', str(graph), '-o', str(graph_1d), '-x', str(inputs.get('width', 1200)), '-y', str(inputs.get('height', 200))]
        if inputs.get('show_path_names'):
            cmd.append('-p')
        cmd.extend(['&&', 'odgi', 'sort', '-i', str(graph), '-o', str(sorted_graph), '-Y', '&&', 'odgi', 'draw', '-i', str(sorted_graph), '-c', str(graph_2d), '-H', str(inputs.get('draw_height', 600)), '-C', str(inputs.get('draw_width', 1200))])
        return cmd

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        node_out = Path(output_dir) / cls.NODE_ID
        node_out.mkdir(parents=True, exist_ok=True)
        return [node_out / 'graph_1d.png', node_out / 'graph_2d.png']

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {'required': {'gfa_graph': ('GFA', {'description': 'Input pangenome graph in GFA format'})}, 'optional': {'width': ('INT', {'default': 1200, 'min': 100, 'max': 10000}), 'height': ('INT', {'default': 200, 'min': 50, 'max': 5000}), 'draw_width': ('INT', {'default': 1200, 'min': 100, 'max': 10000}), 'draw_height': ('INT', {'default': 600, 'min': 50, 'max': 5000}), 'show_path_names': ('BOOLEAN', {'default': False})}, 'hidden': {'output': ('STRING', {})}}


class ODGIVizNode(CommandNode):
    """Render a pangenome graph image for workflow-level reports."""
    NODE_ID = 'odgi_viz'
    DISPLAY_NAME = 'ODGI Viz'
    CATEGORY = 'pangenomics'
    DESCRIPTION = 'Render a pangenome graph image from GFA input using odgi viz.'
    SEARCH_ALIASES = ['odgi', 'odgi viz', 'graph visualization', 'pangenome graph', 'graph layout']
    RETURN_TYPES = ('IMAGE',)
    RETURN_NAMES = ('viz_image',)
    REQUIRED_EXECUTABLES = ['odgi']
    REQUIRED_CONDA_PACKAGES = ['odgi']
    DOCUMENTATION_URL = 'https://odgi.readthedocs.io/'
    VERSION = '0.9.0'
    SHELL = True
    _MODES = {'plain', 'gradient'}

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        base_validation = super().VALIDATE_INPUTS(inputs)
        if base_validation is not True:
            return base_validation
        mode = str(inputs.get('viz_mode', 'plain') or 'plain')
        if mode not in cls._MODES:
            return f'Unsupported ODGI Viz mode: {mode}'
        if int(inputs.get('threads', 0) or 0) < 0:
            return 'ODGI Viz threads must be zero or greater.'
        return True

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        validation = cls.VALIDATE_INPUTS(inputs)
        if validation is not True:
            raise ValueError(str(validation))
        out_dir = Path(str(inputs.get('output', '.')))
        graph = out_dir / 'graph.og'
        viz_image = out_dir / 'viz_image.png'
        threads = int(inputs.get('threads', 0) or 0)
        cmd = ['odgi', 'build', '-g', str(inputs.get('gfa_graph', '')), '-o', str(graph)]
        if threads > 0:
            cmd.extend(['-t', str(threads)])
        cmd.extend(['&&', 'odgi', 'viz', '-i', str(graph), '-o', str(viz_image), '-x', str(inputs.get('width', 1200)), '-y', str(inputs.get('height', 200))])
        if inputs.get('show_paths'):
            cmd.append('-p')
        return cmd

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        node_out = Path(output_dir) / cls.NODE_ID
        node_out.mkdir(parents=True, exist_ok=True)
        return [node_out / 'viz_image.png']

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {'required': {'gfa_graph': ('GFA', {'description': 'Input pangenome graph in GFA format'})}, 'optional': {'width': ('INT', {'default': 1200, 'min': 100, 'max': 10000}), 'height': ('INT', {'default': 200, 'min': 50, 'max': 5000}), 'show_paths': ('BOOLEAN', {'default': False, 'description': 'Draw path names when supported'}), 'viz_mode': ('STRING', {'default': 'plain', 'options': ['plain', 'gradient']}), 'threads': ('INT', {'default': 4, 'min': 0, 'max': 64, 'display': 'slider'})}, 'hidden': {'output': ('STRING', {})}}


class ODGIStatsNode(CommandNode):
    """Compute JSON graph statistics from a GFA pangenome graph."""
    NODE_ID = 'odgi_stats'
    DISPLAY_NAME = 'ODGI Stats'
    CATEGORY = 'pangenomics'
    DESCRIPTION = 'Compute JSON graph statistics from GFA input using odgi stats.'
    SEARCH_ALIASES = ['odgi', 'odgi stats', 'graph statistics', 'pangenome graph', 'stats json']
    RETURN_TYPES = ('JSON',)
    RETURN_NAMES = ('stats_json',)
    REQUIRED_EXECUTABLES = ['odgi']
    REQUIRED_CONDA_PACKAGES = ['odgi']
    DOCUMENTATION_URL = 'https://odgi.readthedocs.io/'
    VERSION = '0.9.0'
    SHELL = True

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        base_validation = super().VALIDATE_INPUTS(inputs)
        if base_validation is not True:
            return base_validation
        if int(inputs.get('threads', 0) or 0) < 0:
            return 'ODGI Stats threads must be zero or greater.'
        return True

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        validation = cls.VALIDATE_INPUTS(inputs)
        if validation is not True:
            raise ValueError(str(validation))
        out_dir = Path(str(inputs.get('output', '.')))
        graph = out_dir / 'graph.og'
        stats = out_dir / 'stats.json'
        threads = int(inputs.get('threads', 0) or 0)
        cmd = ['odgi', 'build', '-g', str(inputs.get('gfa_graph', '')), '-o', str(graph)]
        if threads > 0:
            cmd.extend(['-t', str(threads)])
        cmd.extend(['&&', 'odgi', 'stats', '-i', str(graph), '-j', '>', str(stats)])
        return cmd

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        node_out = Path(output_dir) / cls.NODE_ID
        node_out.mkdir(parents=True, exist_ok=True)
        return [node_out / 'stats.json']

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {'required': {'gfa_graph': ('GFA', {'description': 'Input pangenome graph in GFA format'})}, 'optional': {'threads': ('INT', {'default': 4, 'min': 0, 'max': 64, 'display': 'slider'})}, 'hidden': {'output': ('STRING', {})}}


class ODGIViewNode(CommandNode):
    """Visualize and inspect ODGI pangenome graphs."""
    NODE_ID = 'odgi_view'
    DISPLAY_NAME = 'ODGI View'
    CATEGORY = 'pangenomics'
    DESCRIPTION = 'Visualize and extract information from ODGI pangenome graphs.'
    SEARCH_ALIASES = ['odgi', 'odgi stats', 'pangenome graph', 'graph view', 'paths']
    RETURN_TYPES = ('FILE', 'JSON')
    RETURN_NAMES = ('view', 'stats')
    REQUIRED_EXECUTABLES = ['odgi']
    REQUIRED_CONDA_PACKAGES = ['odgi']
    DOCUMENTATION_URL = 'https://odgi.readthedocs.io/'
    VERSION = '0.9.0'
    SHELL = True
    _MODES = {'png', 'paths'}

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        base_validation = super().VALIDATE_INPUTS(inputs)
        if base_validation is not True:
            return base_validation
        mode = str(inputs.get('mode', 'png') or 'png')
        if mode not in cls._MODES:
            return f'Unsupported ODGI view mode: {mode}'
        return True

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        validation = cls.VALIDATE_INPUTS(inputs)
        if validation is not True:
            raise ValueError(str(validation))
        out_dir = Path(str(inputs.get('output', '.')))
        graph = str(inputs.get('graph', ''))
        mode = str(inputs.get('mode', 'png') or 'png')
        view = out_dir / ('view.png' if mode == 'png' else 'view.txt')
        stats = out_dir / 'stats.json'
        if mode == 'png':
            cmd = ['odgi', 'viz', '-i', graph, '-o', str(view)]
            width = int(inputs.get('width', 0) or 0)
            height = int(inputs.get('height', 0) or 0)
            if width > 0:
                cmd.extend(['-x', str(width)])
            if height > 0:
                cmd.extend(['-y', str(height)])
            if inputs.get('show_path_names'):
                cmd.append('-p')
        else:
            cmd = ['odgi', 'paths', '-i', graph, '-L', '>', str(view)]
        cmd.extend(['&&', 'odgi', 'stats', '-i', graph, '-j', '>', str(stats)])
        return cmd

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        node_out = Path(output_dir) / cls.NODE_ID
        node_out.mkdir(parents=True, exist_ok=True)
        mode = str(inputs.get('mode', 'png') or 'png')
        view_name = 'view.png' if mode == 'png' else 'view.txt'
        return [node_out / view_name, node_out / 'stats.json']

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {'required': {'graph': ('ODGI', {'description': 'Input pangenome graph in ODGI format'}), 'mode': ('STRING', {'default': 'png', 'options': ['png', 'paths']})}, 'optional': {'width': ('INT', {'default': 1200, 'min': 0, 'max': 10000}), 'height': ('INT', {'default': 200, 'min': 0, 'max': 5000}), 'show_path_names': ('BOOLEAN', {'default': False})}, 'hidden': {'output': ('STRING', {})}}
