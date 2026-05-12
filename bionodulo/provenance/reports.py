"""
Execution and provenance report generators.

Produces HTML execution reports and JSON provenance reports from
workflow run data.
"""

from __future__ import annotations

import html as html_mod
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def generate_execution_report(
    run_metadata: dict[str, Any],
    output_path: str | Path | None = None,
    include_artifacts: bool = True,
) -> str:
    """Generate an HTML report of a workflow execution.

    Args:
        run_metadata: Run metadata dict with ``run_id``, ``nodes``,
            ``status``, ``failed_nodes``, ``skipped_nodes``, etc.
        output_path: If given, write the HTML to this path.
        include_artifacts: Include artifact file listing.

    Returns:
        The HTML report as a string.
    """
    run_id = run_metadata.get("run_id", "unknown")
    status = run_metadata.get("status", "unknown")
    nodes = run_metadata.get("nodes", {})
    failed = run_metadata.get("failed_nodes", [])
    skipped = run_metadata.get("skipped_nodes", [])
    mock = run_metadata.get("mock", False)
    artifacts = run_metadata.get("artifacts", []) if include_artifacts else []

    status_color = {
        "completed": "#28a745",
        "failed": "#dc3545",
        "cancelled": "#ffc107",
        "running": "#007bff",
    }.get(status, "#6c757d")

    node_rows = ""
    for node_id, node_meta in nodes.items():
        node_status = node_meta.get("status", "unknown")
        node_type = node_meta.get("type", "unknown")
        cache_key = node_meta.get("cache_key", "")[:16]
        status_badge = _status_badge(node_status)
        node_rows += (
            f"<tr>"
            f"<td><code>{html_mod.escape(node_id)}</code></td>"
            f"<td>{html_mod.escape(node_type)}</td>"
            f"<td>{status_badge}</td>"
            f"<td><code>{html_mod.escape(cache_key)}...</code></td>"
            f"</tr>"
        )

    artifact_rows = ""
    for art in artifacts:
        if isinstance(art, dict):
            artifact_rows += (
                f"<tr>"
                f"<td><code>{html_mod.escape(art.get('node_id', ''))}</code></td>"
                f"<td>{html_mod.escape(art.get('port', ''))}</td>"
                f"<td><code>{html_mod.escape(art.get('path', ''))}</code></td>"
                f"<td>{art.get('size', 0)}</td>"
                f"</tr>"
            )

    completed_count = sum(
        1 for n in nodes.values() if n.get("status") in ("completed", "cached", "bypassed")
    )

    artifact_section = ""
    if include_artifacts and artifacts:
        artifact_section = (
            '<div class="section">'
            '<h2>Output Artifacts</h2>'
            '<table><thead><tr><th>Node ID</th><th>Port</th><th>Path</th><th>Size (bytes)</th></tr></thead><tbody>'
            + (artifact_rows if artifact_rows else '<tr><td colspan="4" style="text-align:center;color:#888;">No artifacts</td></tr>')
            + "</tbody></table></div>"
        )

    mock_badge = ' <span style="margin-left:8px;font-size:12px;">(MOCK MODE)</span>' if mock else ""

    html_content = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>BioNodulo Execution Report - {html_mod.escape(run_id)}</title>
    <style>
        * {{ box-sizing: border-box; margin: 0; padding: 0; }}
        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            background: #f5f5f5;
            color: #333;
            line-height: 1.6;
            padding: 20px;
        }}
        .container {{ max-width: 1200px; margin: 0 auto; }}
        .header {{
            background: linear-gradient(135deg, #1a1a2e 0%, #16213e 100%);
            color: white;
            padding: 30px;
            border-radius: 8px;
            margin-bottom: 24px;
        }}
        .header h1 {{ font-size: 24px; margin-bottom: 8px; }}
        .status {{
            display: inline-block;
            padding: 4px 12px;
            border-radius: 12px;
            font-size: 14px;
            font-weight: 600;
            background: {status_color};
            color: white;
        }}
        .summary {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
            gap: 16px;
            margin-bottom: 24px;
        }}
        .summary-card {{
            background: white;
            padding: 20px;
            border-radius: 8px;
            box-shadow: 0 1px 3px rgba(0,0,0,0.1);
        }}
        .summary-card h3 {{
            font-size: 12px;
            text-transform: uppercase;
            color: #888;
            margin-bottom: 8px;
        }}
        .summary-card .value {{
            font-size: 28px;
            font-weight: 700;
            color: #1a1a2e;
        }}
        .section {{
            background: white;
            padding: 24px;
            border-radius: 8px;
            box-shadow: 0 1px 3px rgba(0,0,0,0.1);
            margin-bottom: 24px;
        }}
        .section h2 {{
            font-size: 18px;
            margin-bottom: 16px;
            color: #1a1a2e;
        }}
        table {{
            width: 100%;
            border-collapse: collapse;
            font-size: 14px;
        }}
        th, td {{
            text-align: left;
            padding: 10px 12px;
            border-bottom: 1px solid #eee;
        }}
        th {{
            font-weight: 600;
            color: #666;
            font-size: 12px;
            text-transform: uppercase;
        }}
        tr:hover {{ background: #f8f9fa; }}
        code {{
            font-family: 'SF Mono', Monaco, monospace;
            font-size: 12px;
            background: #f0f0f0;
            padding: 2px 6px;
            border-radius: 3px;
        }}
        .badge {{
            display: inline-block;
            padding: 2px 8px;
            border-radius: 10px;
            font-size: 12px;
            font-weight: 600;
        }}
        .badge-success {{ background: #d4edda; color: #155724; }}
        .badge-failed {{ background: #f8d7da; color: #721c24; }}
        .badge-muted {{ background: #e2e3e5; color: #383d41; }}
        .badge-bypassed {{ background: #fff3cd; color: #856404; }}
        .badge-cached {{ background: #cce5ff; color: #004085; }}
        .footer {{
            text-align: center;
            color: #888;
            font-size: 12px;
            padding: 20px;
        }}
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>BioNodulo Execution Report</h1>
            <p>Run ID: <code>{html_mod.escape(run_id)}</code></p>
            <p style="margin-top: 8px;">
                <span class="status">{html_mod.escape(status.upper())}</span>
                {mock_badge}
            </p>
        </div>

        <div class="summary">
            <div class="summary-card">
                <h3>Total Nodes</h3>
                <div class="value">{len(nodes)}</div>
            </div>
            <div class="summary-card">
                <h3>Completed</h3>
                <div class="value">{completed_count}</div>
            </div>
            <div class="summary-card">
                <h3>Failed</h3>
                <div class="value">{len(failed)}</div>
            </div>
            <div class="summary-card">
                <h3>Skipped</h3>
                <div class="value">{len(skipped)}</div>
            </div>
        </div>

        <div class="section">
            <h2>Node Execution Details</h2>
            <table>
                <thead>
                    <tr><th>Node ID</th><th>Type</th><th>Status</th><th>Cache Key</th></tr>
                </thead>
                <tbody>
                    {node_rows if node_rows else '<tr><td colspan="4" style="text-align:center;color:#888;">No nodes executed</td></tr>'}
                </tbody>
            </table>
        </div>

        {artifact_section}

        <div class="footer">
            <p>Generated by BioNodulo Alpha 1.1 on {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')}</p>
        </div>
    </div>
</body>
</html>"""

    if output_path:
        out = Path(output_path)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(html_content, encoding="utf-8")

    return html_content


def generate_provenance_report(
    workflow: dict[str, Any],
    run_metadata: dict[str, Any],
    node_results: dict[str, dict[str, Any]],
    artifacts: list[dict[str, Any]],
    output_path: str | Path | None = None,
) -> str:
    """Generate a JSON provenance report.

    Args:
        workflow: The workflow definition.
        run_metadata: Run-level metadata.
        node_results: Per-node execution results.
        artifacts: Output artifact descriptions.
        output_path: If given, write the JSON to this path.

    Returns:
        The JSON provenance report as a string.
    """
    report: dict[str, Any] = {
        "provenance_schema_version": "1.0",
        "bionodulo_version": "Alpha 1.1",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "workflow": {
            "id": workflow.get("id", "unknown"),
            "name": workflow.get("name", ""),
            "description": workflow.get("description", ""),
            "node_count": len(workflow.get("nodes", [])),
            "edge_count": len(workflow.get("edges", [])),
        },
        "execution": {
            "run_id": run_metadata.get("run_id", ""),
            "status": run_metadata.get("status", ""),
            "mock_execution": run_metadata.get("mock", False),
            "forced": run_metadata.get("forced", False),
            "start_time": run_metadata.get("start_time"),
            "end_time": run_metadata.get("end_time"),
        },
        "nodes": {},
        "artifacts": artifacts,
    }

    for node_id, node_meta in run_metadata.get("nodes", {}).items():
        result = node_results.get(node_id, {})
        report["nodes"][node_id] = {
            "type": node_meta.get("type", "unknown"),
            "status": node_meta.get("status", "unknown"),
            "cache_key": node_meta.get("cache_key", ""),
            "outputs": result.get("outputs", {}),
            "error": result.get("error"),
        }

    json_content = json.dumps(report, indent=2, ensure_ascii=True)
    if output_path:
        out = Path(output_path)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json_content, encoding="utf-8")
    return json_content


def _status_badge(status: str) -> str:
    """Generate an HTML status badge."""
    badge_class = {
        "completed": "badge-success",
        "cached": "badge-cached",
        "failed": "badge-failed",
        "muted": "badge-muted",
        "bypassed": "badge-bypassed",
        "cancelled": "badge-muted",
    }.get(status, "badge-muted")
    return f'<span class="badge {badge_class}">{html_mod.escape(status.upper())}</span>'
