"""sbol — synthetic_biology node(s). One tool per file (extracted from synthetic_biology.py)."""
from __future__ import annotations
import re
import textwrap
from pathlib import Path
from typing import Any
from bionodulo.nodes.command_node import CommandNode
def _safe_output_stem(value: Any, fallback: str) -> str:
    text = str(value or '').strip()
    if not text:
        text = fallback
    stem = Path(text).stem
    stem = re.sub('\\.(gz|bz2|xz|zip)$', '', stem)
    stem = re.sub('[^A-Za-z0-9_.-]+', '_', stem).strip('._-')
    return stem or fallback


class SBOLDesignImportNode(CommandNode):
    """Import, normalize, and summarize SBOL designs with pySBOL3."""
    NODE_ID = 'sbol_design_import'
    DISPLAY_NAME = 'SBOL Design Import'
    CATEGORY = 'synthetic_biology'
    DESCRIPTION = 'Import and summarize Synthetic Biology Open Language designs with pySBOL3.'
    SEARCH_ALIASES = ['sbol', 'pysbol3', 'synthetic biology', 'biocad', 'genetic design', 'sbol3']
    RETURN_TYPES = ('SBOL', 'JSON')
    RETURN_NAMES = ('normalized_sbol', 'summary')
    REQUIRED_EXECUTABLES = ['python']
    REQUIRED_CONDA_PACKAGES = ['pysbol3']
    DOCUMENTATION_URL = 'https://pysbol3.readthedocs.io/'
    VERSION = '1.1'
    SHELL = True

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        out_dir = Path(str(inputs.get('output', '.')))
        out_dir.mkdir(parents=True, exist_ok=True)
        script_file = out_dir / 'sbol_design_import.py'
        stem = _safe_output_stem(inputs.get('output_name'), _safe_output_stem(inputs.get('sbol_file'), 'design'))
        output_format = str(inputs.get('output_format', 'rdfxml') or 'rdfxml')
        extension = '.nt' if output_format == 'ntriples' else '.xml'
        normalized_path = out_dir / f'{stem}{extension}'
        summary_path = out_dir / f'{stem}.summary.json'
        namespace = str(inputs.get('namespace', '') or '').strip()
        validate = bool(inputs.get('validate', True))
        namespace_line = f'sbol3.set_namespace({namespace!r})' if namespace else ''
        validation_line = 'report = doc.validate()' if validate else 'report = None'
        validation_summary = '"validation_errors": [str(result) for result in getattr(report, \'errors\', [])],\n    "validation_warnings": [str(result) for result in getattr(report, \'warnings\', [])],' if validate else '"validation_errors": [],\n    "validation_warnings": [],'
        script = textwrap.dedent(f"""            from __future__ import annotations\n\n            import json\n            from pathlib import Path\n\n            import sbol3\n\n            {namespace_line}\n            doc = sbol3.Document()\n            doc.read({str(inputs.get('sbol_file', ''))!r})\n            {validation_line}\n            doc.write({str(normalized_path)!r}, file_format={output_format!r})\n\n            def identity(obj):\n                return str(getattr(obj, "identity", obj))\n\n            components = [obj for obj in doc.objects if isinstance(obj, sbol3.Component)]\n            sequences = [obj for obj in doc.objects if isinstance(obj, sbol3.Sequence)]\n            interactions = []\n            for component in components:\n                interactions.extend(getattr(component, "interactions", []) or [])\n\n            summary = {{\n                "input_file": {str(inputs.get('sbol_file', ''))!r},\n                "normalized_sbol": {str(normalized_path)!r},\n                "object_count": len(doc.objects),\n                "components": [identity(obj) for obj in components],\n                "sequences": [identity(obj) for obj in sequences],\n                "interactions": [identity(obj) for obj in interactions],\n                "output_format": {output_format!r},\n                {validation_summary}\n            }}\n            summary_path = Path({str(summary_path)!r})\n            summary_path.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\\n", encoding="utf-8")\n        """)
        script_file.write_text(script, encoding='utf-8')
        return ['python', str(script_file)]

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        node_out = Path(output_dir) / cls.NODE_ID
        node_out.mkdir(parents=True, exist_ok=True)
        stem = _safe_output_stem(inputs.get('output_name'), _safe_output_stem(inputs.get('sbol_file'), 'design'))
        output_format = str(inputs.get('output_format', 'rdfxml') or 'rdfxml')
        extension = '.nt' if output_format == 'ntriples' else '.xml'
        return [node_out / f'{stem}{extension}', node_out / f'{stem}.summary.json']

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {'required': {'sbol_file': ('FILE', {'description': 'SBOL file to import (.xml, .rdf, .nt, .ttl)'})}, 'optional': {'namespace': ('STRING', {'default': '', 'description': 'Default SBOL namespace for generated identities'}), 'validate': ('BOOLEAN', {'default': True, 'description': 'Validate the design after import'}), 'output_format': ('STRING', {'default': 'rdfxml', 'options': ['rdfxml', 'ntriples']}), 'output_name': ('STRING', {'default': '', 'description': 'Optional output filename stem'})}, 'hidden': {'output': ('STRING', {})}}
