"""Workflow export to various pipeline formats.

Delegates to converter modules for SnakeMake, NextFlow, CWL, and Galaxy.
"""

from __future__ import annotations

from typing import Any


def export_workflow(
    workflow: dict[str, Any],
    fmt: str,
    name: str = "workflow",
) -> str:
    """Export a workflow to the specified format.

    Args:
        workflow: Workflow dictionary to export.
        fmt: Target format - "snakemake", "nextflow", "cwl", "galaxy", or "json".
        name: Base name for the output file.

    Returns:
        String content of the exported workflow.

    Raises:
        ValueError: If the format is not supported.
        RuntimeError: If the requested converter module is unavailable.
    """
    fmt = fmt.lower()

    if fmt == "json":
        import json as _json
        return _json.dumps(workflow, indent=2, ensure_ascii=False, default=str)

    if fmt == "snakemake":
        try:
            from bionodulo.converter.snakemake_converter import export_to_snakemake as snakemake_export
            return snakemake_export(workflow)
        except ImportError as exc:
            raise _converter_unavailable(fmt) from exc

    if fmt == "nextflow":
        try:
            from bionodulo.converter.nextflow_converter import export_to_nextflow as nextflow_export
            return nextflow_export(workflow)
        except ImportError as exc:
            raise _converter_unavailable(fmt) from exc

    if fmt == "cwl":
        try:
            import json as _json
            from bionodulo.converter.cwl_converter import export_to_cwl as cwl_export
            return _json.dumps(cwl_export(workflow), indent=2, ensure_ascii=False, default=str)
        except ImportError as exc:
            raise _converter_unavailable(fmt) from exc

    if fmt == "galaxy":
        try:
            from bionodulo.converter.galaxy_converter import export_to_galaxy as galaxy_export
            return galaxy_export(workflow)
        except ImportError as exc:
            raise _converter_unavailable(fmt) from exc

    raise ValueError(
        f"Unsupported export format: '{fmt}'. "
        f"Supported: snakemake, nextflow, cwl, galaxy, json"
    )


def _converter_unavailable(fmt: str) -> RuntimeError:
    return RuntimeError(
        f"Cannot export {fmt} workflow because the converter module is unavailable. "
        "Install converter dependencies for full export support."
    )
