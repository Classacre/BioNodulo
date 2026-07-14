"""cello — synthetic_biology node(s). One tool per file (extracted from synthetic_biology.py)."""
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


class CelloCircuitDesignNode(CommandNode):
    """Run Cello DNACompiler or export stages from a local Cello-v2 installation."""
    NODE_ID = 'cello_circuit_design'
    DISPLAY_NAME = 'Cello Circuit Design'
    CATEGORY = 'synthetic_biology'
    DESCRIPTION = 'Run Cello DNACompiler genetic circuit design from Verilog netlists and UCF libraries.'
    SEARCH_ALIASES = ['cello', 'cello 2.0', 'synthetic biology', 'biocad', 'genetic circuit', 'verilog', 'ucf', 'dna compiler', 'sbol export']
    RETURN_TYPES = ('DIRECTORY', 'TSV', 'JSON', 'LOG')
    RETURN_NAMES = ('design_dir', 'result_index', 'metadata', 'log')
    REQUIRED_EXECUTABLES = ['python']
    REQUIRED_CONDA_PACKAGES: list[str] = []
    DOCUMENTATION_URL = 'https://github.com/CIDARLAB/Cello-v2'
    VERSION = '1.0'
    EXPERIMENTAL = True
    SHELL = True
    INDEX_SCRIPT = textwrap.dedent('        from __future__ import annotations\n        import csv\n        import json\n        import sys\n        from pathlib import Path\n\n        (\n            design_dir,\n            index_path,\n            metadata_path,\n            log_path,\n            input_netlist,\n            target_data_file,\n            options_file,\n            netlist_constraint_file,\n            cello_exec_dir,\n            application,\n            algo_name,\n            java_args,\n        ) = sys.argv[1:13]\n\n        root = Path(design_dir)\n        rows = []\n        if root.exists():\n            for path in sorted(root.rglob("*")):\n                if path.is_file():\n                    rows.append({\n                        "relative_path": str(path.relative_to(root)),\n                        "path": str(path),\n                        "size_bytes": path.stat().st_size,\n                    })\n\n        index_file = Path(index_path)\n        index_file.parent.mkdir(parents=True, exist_ok=True)\n        with index_file.open("w", newline="", encoding="utf-8") as handle:\n            writer = csv.DictWriter(handle, fieldnames=["relative_path", "path", "size_bytes"], delimiter="\\t")\n            writer.writeheader()\n            writer.writerows(rows)\n\n        log_file = Path(log_path)\n        metadata = {\n            "input_netlist": input_netlist,\n            "target_data_file": target_data_file,\n            "options_file": options_file,\n            "netlist_constraint_file": netlist_constraint_file,\n            "cello_exec_dir": cello_exec_dir,\n            "application": application,\n            "algo_name": algo_name,\n            "java_args": java_args,\n            "design_dir": design_dir,\n            "result_count": len(rows),\n            "result_index": index_path,\n            "log": {\n                "path": log_path,\n                "exists": log_file.exists(),\n                "size_bytes": log_file.stat().st_size if log_file.exists() else 0,\n            },\n        }\n        Path(metadata_path).write_text(json.dumps(metadata, indent=2, sort_keys=True) + "\\n", encoding="utf-8")\n    ')

    @classmethod
    def _planned_paths(cls, inputs: dict[str, Any], output_dir: str | Path) -> tuple[Path, Path, Path, Path]:
        node_out = Path(output_dir)
        node_out.mkdir(parents=True, exist_ok=True)
        stem = _safe_output_stem(inputs.get('output_name'), _safe_output_stem(inputs.get('input_netlist'), 'cello_design'))
        design_dir = node_out / stem
        return (design_dir, node_out / f'{stem}.result_index.tsv', node_out / f'{stem}.metadata.json', node_out / f'{stem}.log')

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        out_dir = Path(str(inputs.get('output', '.')))
        out_dir.mkdir(parents=True, exist_ok=True)
        design_dir, index_path, metadata_path, log_path = cls._planned_paths(inputs, out_dir)
        design_dir.mkdir(parents=True, exist_ok=True)
        input_netlist = str(inputs.get('input_netlist', ''))
        target_data_file = str(inputs.get('target_data_file', ''))
        options_file = str(inputs.get('options_file', ''))
        netlist_constraint_file = str(inputs.get('netlist_constraint_file', '') or '').strip()
        cello_exec_dir = str(inputs.get('cello_exec_dir', ''))
        java_args = str(inputs.get('java_args', '') or '').strip()
        application = str(inputs.get('application', 'DNACompiler') or 'DNACompiler').strip()
        algo_name = str(inputs.get('algo_name', '') or '').strip()
        if application not in {'DNACompiler', 'export'}:
            raise ValueError('application must be one of: DNACompiler, export')
        run_script = Path(cello_exec_dir) / 'run.py'
        app_args = ['-inputNetlist', input_netlist, '-targetDataFile', target_data_file, '-options', options_file, '-outputDir', str(design_dir)]
        if netlist_constraint_file:
            app_args.extend(['-netlistConstraintFile', netlist_constraint_file])
        if algo_name:
            app_args.extend(['-algoName', algo_name])
        app_arg_text = ' '.join(app_args)
        cmd = ['python', str(run_script), '-e', application]
        if java_args:
            cmd.extend(['-j', java_args])
        cmd.extend(['-a', app_arg_text, '>', str(log_path), '2>&1', '&&', 'python', '-c', cls.INDEX_SCRIPT, str(design_dir), str(index_path), str(metadata_path), str(log_path), input_netlist, target_data_file, options_file, netlist_constraint_file, cello_exec_dir, application, algo_name, java_args])
        return cmd

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        node_out = Path(output_dir) / cls.NODE_ID
        return list(cls._planned_paths(inputs, node_out))

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {'required': {'input_netlist': ('FILE', {'description': 'Verilog netlist or placement JSON for the Cello application'}), 'target_data_file': ('FILE', {'description': 'Cello UCF target data JSON'}), 'options_file': ('FILE', {'description': 'Cello options CSV'}), 'cello_exec_dir': ('DIRECTORY', {'description': 'Path to the Cello-v2 exec directory containing run.py'})}, 'optional': {'netlist_constraint_file': ('FILE', {'default': '', 'description': 'Optional Cello netlist constraints JSON'}), 'java_args': ('STRING', {'default': '-Xms2G -Xmx5G', 'description': 'Java memory arguments passed to Cello'}), 'application': ('STRING', {'default': 'DNACompiler', 'options': ['DNACompiler', 'export']}), 'algo_name': ('STRING', {'default': '', 'description': 'Export algorithm name such as SBOL'}), 'output_name': ('STRING', {'default': '', 'description': 'Optional output directory and filename stem'})}, 'hidden': {'output': ('STRING', {})}}
