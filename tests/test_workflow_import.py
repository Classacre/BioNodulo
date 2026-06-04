from __future__ import annotations

import json
from pathlib import Path

from bionodulo.converter.cwl_converter import import_from_cwl
from bionodulo.converter.galaxy_converter import import_from_galaxy
from bionodulo.converter.nextflow_converter import import_from_nextflow
from bionodulo.converter.snakemake_converter import import_from_snakemake


def test_snakemake_import_maps_unknown_rule_to_generic_command() -> None:
    workflow = import_from_snakemake(
        """
rule custom_step:
    output:
        "out.txt"
    shell:
        "custom_tool --flag {output}"
"""
    )

    node = workflow["nodes"][0]
    assert node["type"] == "generic_command"
    assert node["widgets"]["command"] == "custom_tool --flag {output}"


def test_nextflow_import_maps_unknown_process_to_generic_command() -> None:
    workflow = import_from_nextflow(
        '''
process custom_step {
    output:
        path "out.txt"
    script:
        """
        custom_tool --flag out.txt
        """
}

workflow {
    custom_step()
}
'''
    )

    node = workflow["nodes"][0]
    assert node["type"] == "generic_command"
    assert node["widgets"]["command"] == "custom_tool --flag out.txt"


def test_cwl_import_maps_unknown_tool_to_generic_command(tmp_path: Path) -> None:
    tools_dir = tmp_path / "tools"
    tools_dir.mkdir()
    (tmp_path / "workflow.cwl").write_text(
        json.dumps(
            {
                "class": "Workflow",
                "cwlVersion": "v1.2",
                "steps": {
                    "custom_step": {
                        "run": "tools/custom_step.cwl",
                        "in": {},
                        "out": ["out"],
                    }
                },
            }
        ),
        encoding="utf-8",
    )
    (tools_dir / "custom_step.cwl").write_text(
        json.dumps(
            {
                "class": "CommandLineTool",
                "baseCommand": ["custom_tool", "--flag"],
                "outputs": {
                    "out": {
                        "type": "File",
                        "outputBinding": {"glob": "out.txt"},
                    }
                },
            }
        ),
        encoding="utf-8",
    )

    workflow = import_from_cwl(tmp_path / "workflow.cwl")

    node = workflow["nodes"][0]
    assert node["type"] == "generic_command"
    assert node["widgets"]["command"] == "custom_tool --flag"


def test_galaxy_import_maps_unknown_tool_to_generic_command() -> None:
    workflow = import_from_galaxy(
        json.dumps(
            {
                "a_galaxy_workflow": "true",
                "name": "Unknown Tool",
                "steps": {
                    "1": {
                        "type": "tool",
                        "label": "custom_step",
                        "tool_id": "toolshed.example/repos/example/custom_tool/custom_tool/1.0",
                        "tool_state": {"command": "custom_tool --flag"},
                        "outputs": [{"name": "out"}],
                        "position": {"left": 100, "top": 100},
                    }
                },
            }
        )
    )

    node = workflow["nodes"][0]
    assert node["type"] == "generic_command"
    assert node["widgets"]["command"] == "custom_tool --flag"
