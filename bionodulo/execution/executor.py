"""
WorkflowExecutor - the main execution engine for BioNodulo v2.

Executes workflow graphs with support for:
- Topological-sort execution order
- Input resolution from upstream node outputs
- Muted and bypassed node handling
- Cache hit detection and skipping
- Mock and real execution modes
- WebSocket event emission
- Per-node and per-run metadata
- Preview artifact collection
- Provenance embedding
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import traceback
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable

from bionodulo.execution.cache import CacheStore
from bionodulo.execution.mock_runner import run_mock_node
from bionodulo.execution.subprocess_runner import run_subprocess


# ---------------------------------------------------------------------------
# ExecutionContext
# ---------------------------------------------------------------------------

@dataclass
class ExecutionContext:
    """Runtime context passed to each node's ``run()`` method.

    Attributes:
        run_id: Unique identifier for this workflow run.
        node_id: The node's identifier in the workflow graph.
        node_type: The node's type string.
        node_dir: Working directory for this node's execution.
        params: Resolved parameters for the node.
        mock_tools: If *True*, use mock execution instead of real tools.
        api_secrets: Dictionary of resolved API secrets.
        emit: Callback for emitting WebSocket events.
        cancel_event: Asyncio event that signals cancellation.
    """

    run_id: str
    node_id: str
    node_type: str
    node_dir: Path
    params: dict[str, Any]
    mock_tools: bool
    api_secrets: dict[str, str]
    emit: Callable[[str, dict[str, Any]], None]
    cancel_event: asyncio.Event

    # Mutable state set during execution
    _previews: list[dict[str, Any]] = field(default_factory=list, repr=False)
    _logs: list[dict[str, Any]] = field(default_factory=list, repr=False)

    def planned_outputs(self) -> dict[str, str]:
        """Return a mapping of output port names to planned file paths.

        By default, each output port gets a file inside ``node_dir``
        named after the port.
        """
        return {
            name: str(self.node_dir / f"{name}_output")
            for name in (self.params.get("_output_ports") or ["default"])
        }

    def log(self, level: str, message: str) -> None:
        """Emit a log message via WebSocket and store locally."""
        entry = {"node_id": self.node_id, "level": level, "message": message}
        self._logs.append(entry)
        self.emit("log", entry)

    def resolve_secret(self, key: str) -> str | None:
        """Resolve an API secret by *key*."""
        return self.api_secrets.get(key)

    def register_preview(self, path: str | Path, label: str | None = None) -> None:
        """Register a file as a previewable artifact."""
        preview = {
            "path": str(path),
            "label": label or Path(path).name,
            "node_id": self.node_id,
        }
        self._previews.append(preview)
        self.emit("preview", preview)

    async def run_command(
        self,
        cmd: str | list[str],
        cwd: str | Path | None = None,
        env: dict[str, str] | None = None,
        timeout: float | None = None,
    ) -> dict[str, Any]:
        """Run a subprocess command within this execution context.

        If ``mock_tools`` is enabled, this instead creates mock outputs.
        """
        stdout_path = self.node_dir / "stdout.log"
        stderr_path = self.node_dir / "stderr.log"

        if self.mock_tools:
            self.log("info", f"[mock] Would run: {cmd}")
            outputs = self.planned_outputs()
            return await run_mock_node(
                node_id=self.node_id,
                node_type=self.node_type,
                node_dir=self.node_dir,
                planned_outputs=outputs,
                params=self.params,
                emit=self.emit,
            )

        return await run_subprocess(
            cmd=cmd,
            cwd=cwd or self.node_dir,
            env=env,
            stdout_path=stdout_path,
            stderr_path=stderr_path,
            emit=self.emit,
            node_id=self.node_id,
            timeout=timeout,
        )


# ---------------------------------------------------------------------------
# WorkflowExecutor
# ---------------------------------------------------------------------------

class WorkflowExecutor:
    """Main workflow execution engine.

    Executes a workflow graph node by node in topological order,
    handling caching, mocking, muting, bypassing, and error recovery.
    """

    def __init__(
        self,
        cache_dir: str | Path | None = None,
        workspace_dir: str | Path = "./workspace",
    ) -> None:
        self.workspace_dir = Path(workspace_dir)
        self.cache = CacheStore(cache_dir or self.workspace_dir / "cache")
        self.workspace_dir.mkdir(parents=True, exist_ok=True)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def execute(
        self,
        run_id: str,
        workflow: dict[str, Any],
        record: Any | None = None,
        mock_tools: bool = False,
        force: bool = False,
        force_nodes: set[str] | None = None,
        options: dict[str, Any] | None = None,
        cancel_event: asyncio.Event | None = None,
        emit: Callable[[str, dict[str, Any]], None] | None = None,
    ) -> dict[str, Any]:
        """Execute a workflow.

        Args:
            run_id: Unique run identifier.
            workflow: Workflow dict with ``nodes`` and ``edges``.
            record: Optional run record object for progress tracking.
            mock_tools: Use mock execution (no real tool calls).
            force: Ignore cache for all nodes.
            force_nodes: Set of node IDs to force re-execution.
            options: Execution options (stop_on_error, etc.).
            cancel_event: Asyncio event for cancellation signaling.
            emit: Callback for WebSocket events.

        Returns:
            Execution result dict with ``status``, ``outputs``, ``previews``,
            ``metadata``, and ``node_results``.
        """
        options = options or {}
        force_nodes = force_nodes or set()
        cancel_event = cancel_event or asyncio.Event()

        if emit is None:
            def _noop_emit(event: str, data: dict[str, Any]) -> None:
                pass
            emit = _noop_emit

        nodes: dict[str, dict[str, Any]] = {
            n["id"]: n for n in workflow.get("nodes", [])
        }
        edges: list[dict[str, Any]] = workflow.get("edges", [])

        # Build adjacency lists
        upstream_of: dict[str, list[str]] = {nid: [] for nid in nodes}
        downstream_of: dict[str, list[str]] = {nid: [] for nid in nodes}
        edge_map: dict[str, list[dict[str, Any]]] = {nid: [] for nid in nodes}

        for edge in edges:
            src = edge.get("source")
            tgt = edge.get("target")
            if src in nodes and tgt in nodes:
                upstream_of[tgt].append(src)
                downstream_of[src].append(tgt)
                edge_map[tgt].append(edge)

        # Topological sort
        try:
            execution_order = self._topological_sort(nodes, upstream_of)
        except ValueError as exc:
            emit("error", {"run_id": run_id, "message": f"Cycle detected: {exc}"})
            return {"status": "failed", "error": str(exc)}

        emit("start", {"run_id": run_id, "total_nodes": len(execution_order)})

        # State tracking
        node_results: dict[str, dict[str, Any]] = {}
        node_cache_keys: dict[str, str | None] = {}
        node_outputs: dict[str, dict[str, str]] = {}
        failed_nodes: set[str] = set()
        skipped_nodes: set[str] = set()
        previews: list[dict[str, Any]] = []
        run_metadata: dict[str, Any] = {
            "run_id": run_id,
            "mock": mock_tools,
            "forced": force,
            "nodes": {},
        }

        stop_on_error = options.get("stop_on_error", True)

        for idx, node_id in enumerate(execution_order):
            if cancel_event.is_set():
                emit("cancelled", {"run_id": run_id, "node_id": node_id})
                return {
                    "status": "cancelled",
                    "node_results": node_results,
                    "cancelled_at": node_id,
                }

            node = nodes[node_id]
            node_type = node.get("type", "unknown")
            node_meta = node.get("meta", {})

            emit(
                "node_start",
                {
                    "run_id": run_id,
                    "node_id": node_id,
                    "node_type": node_type,
                    "progress": f"{idx + 1}/{len(execution_order)}",
                },
            )

            # ---- Muted node: skip execution entirely ----
            if node_meta.get("muted"):
                emit(
                    "node_skip",
                    {"run_id": run_id, "node_id": node_id, "reason": "muted"},
                )
                node_results[node_id] = {"status": "muted"}
                skipped_nodes.add(node_id)
                continue

            # ---- Bypassed node: pass inputs through to outputs ----
            if node_meta.get("bypassed"):
                bypass_outputs = self._bypass_outputs(node_id, node, edge_map)
                emit(
                    "node_bypass",
                    {
                        "run_id": run_id,
                        "node_id": node_id,
                        "outputs": bypass_outputs,
                    },
                )
                node_results[node_id] = {
                    "status": "bypassed",
                    "outputs": bypass_outputs,
                }
                node_outputs[node_id] = bypass_outputs
                continue

            # ---- Resolve inputs from upstream nodes ----
            try:
                resolved_inputs = self._resolve_inputs(
                    node_id, node, edge_map, node_outputs
                )
            except Exception as exc:
                msg = f"Input resolution failed for {node_id}: {exc}"
                emit("error", {"run_id": run_id, "node_id": node_id, "message": msg})
                node_results[node_id] = {"status": "failed", "error": msg}
                failed_nodes.add(node_id)
                if stop_on_error:
                    break
                continue

            # ---- Fill parameter defaults ----
            resolved_params = self._with_defaults(node, resolved_inputs)

            # ---- Build upstream cache key map ----
            upstream_keys: dict[str, str | None] = {}
            for edge in edge_map.get(node_id, []):
                src = edge.get("source")
                src_port = edge.get("source_output", "default")
                tgt_port = edge.get("target_input", "default")
                upstream_keys[f"{src}:{src_port}->{tgt_port}"] = node_cache_keys.get(src)

            # ---- Compute cache key ----
            cache_key = self.cache.cache_key_for_node(
                node_id=node_id,
                node_type=node_type,
                params=resolved_params,
                inputs=resolved_inputs,
                upstream_keys=upstream_keys,
            )
            node_cache_keys[node_id] = cache_key

            # ---- Cache hit check ----
            if not force and node_id not in force_nodes and self.cache.is_hit(cache_key):
                marker = self.cache.read_marker(cache_key)
                cached_outputs = marker.get("outputs", {}) if marker else {}
                emit(
                    "node_cache_hit",
                    {
                        "run_id": run_id,
                        "node_id": node_id,
                        "cache_key": cache_key,
                        "outputs": cached_outputs,
                    },
                )
                node_results[node_id] = {
                    "status": "cached",
                    "cache_key": cache_key,
                    "outputs": cached_outputs,
                }
                node_outputs[node_id] = cached_outputs
                continue

            # ---- Prepare node working directory ----
            node_dir = self.workspace_dir / "runs" / run_id / node_id
            node_dir.mkdir(parents=True, exist_ok=True)

            # ---- Build execution context ----
            ctx = ExecutionContext(
                run_id=run_id,
                node_id=node_id,
                node_type=node_type,
                node_dir=node_dir,
                params=resolved_params,
                mock_tools=mock_tools,
                api_secrets=options.get("api_secrets", {}),
                emit=emit,
                cancel_event=cancel_event,
            )

            # ---- Execute the node ----
            try:
                result = await self._execute_node(ctx, node, resolved_inputs)
                node_results[node_id] = {
                    "status": "completed",
                    "outputs": result.get("outputs", {}),
                    "cache_key": cache_key,
                }
                node_outputs[node_id] = result.get("outputs", {})

                # Cache the result
                self.cache.write_marker(
                    cache_key=cache_key,
                    outputs=result.get("outputs", {}),
                    params=resolved_params,
                    inputs=resolved_inputs,
                    upstream_keys=upstream_keys,
                )

                # Collect previews
                node_previews = self._collect_previews(ctx, result)
                previews.extend(node_previews)

                emit(
                    "node_complete",
                    {
                        "run_id": run_id,
                        "node_id": node_id,
                        "outputs": result.get("outputs", {}),
                    },
                )

            except Exception as exc:
                tb = traceback.format_exc()
                msg = f"Execution failed for {node_id}: {exc}"
                emit(
                    "node_error",
                    {
                        "run_id": run_id,
                        "node_id": node_id,
                        "error": msg,
                        "traceback": tb,
                    },
                )
                node_results[node_id] = {"status": "failed", "error": msg, "traceback": tb}
                failed_nodes.add(node_id)
                if stop_on_error:
                    break

            run_metadata["nodes"][node_id] = {
                "type": node_type,
                "status": node_results[node_id]["status"],
                "cache_key": cache_key,
            }

        # ---- Finalize ----
        final_status = "completed" if not failed_nodes else "failed"
        if cancel_event.is_set():
            final_status = "cancelled"

        run_metadata["status"] = final_status
        run_metadata["failed_nodes"] = list(failed_nodes)
        run_metadata["skipped_nodes"] = list(skipped_nodes)

        # Collect all artifacts
        artifacts = self._collect_artifacts(run_id, nodes, node_results)

        # Write run metadata
        self._write_metadata(run_id, run_metadata)

        # Embed provenance in outputs
        if options.get("embed_provenance", True):
            try:
                from bionodulo.provenance.workflow_embed import embed_workflow_in_outputs
                embed_workflow_in_outputs(workflow, artifacts)
            except Exception:
                pass

        emit("complete", {"run_id": run_id, "status": final_status})

        return {
            "status": final_status,
            "run_id": run_id,
            "outputs": node_outputs,
            "previews": previews,
            "artifacts": artifacts,
            "metadata": run_metadata,
            "node_results": node_results,
        }

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    async def _execute_node(
        self,
        ctx: ExecutionContext,
        node: dict[str, Any],
        inputs: dict[str, Any],
    ) -> dict[str, Any]:
        """Execute a single node, either via its ``run()`` method or mock."""
        node_class = node.get("_node_class")
        if node_class is not None and hasattr(node_class, "run"):
            kwargs = {**inputs, **ctx.params}
            kwargs = {k: v for k, v in kwargs.items() if not k.startswith("_")}
            if asyncio.iscoroutinefunction(node_class.run):
                return await node_class.run(context=ctx, **kwargs)
            else:
                return node_class.run(context=ctx, **kwargs)

        # Fallback: mock execution creates placeholder outputs
        outputs = ctx.planned_outputs()
        for port, path in outputs.items():
            Path(path).parent.mkdir(parents=True, exist_ok=True)
            if not Path(path).exists():
                Path(path).write_text(f"# Auto-generated output for port \'{port}\'\n")

        return {"outputs": outputs}

    def _topological_sort(
        self,
        nodes: dict[str, dict[str, Any]],
        upstream_of: dict[str, list[str]],
    ) -> list[str]:
        """Return node IDs in topological order (Kahn's algorithm)."""
        in_degree = {nid: len(upstream_of[nid]) for nid in nodes}
        queue = [nid for nid, deg in in_degree.items() if deg == 0]
        order: list[str] = []

        while queue:
            nid = queue.pop(0)
            order.append(nid)
            for downstream in nodes:
                if nid in upstream_of[downstream]:
                    in_degree[downstream] -= 1
                    if in_degree[downstream] == 0:
                        queue.append(downstream)

        if len(order) != len(nodes):
            remaining = [nid for nid in nodes if nid not in order]
            raise ValueError(f"Cycle detected involving nodes: {remaining}")

        return order

    def _resolve_inputs(
        self,
        node_id: str,
        node: dict[str, Any],
        edge_map: dict[str, list[dict[str, Any]]],
        node_outputs: dict[str, dict[str, str]],
    ) -> dict[str, Any]:
        """Resolve edge connections to actual values from upstream outputs."""
        inputs: dict[str, Any] = {}
        node_def_inputs = node.get("inputs", {})

        # Start with literal/default values from node definition
        for inp_name, inp_val in node_def_inputs.items():
            if isinstance(inp_val, dict) and "value" in inp_val:
                inputs[inp_name] = inp_val["value"]
            else:
                inputs[inp_name] = inp_val

        # Override with upstream connections
        for edge in edge_map.get(node_id, []):
            src = edge.get("source")
            src_port = edge.get("source_output", "default")
            tgt_port = edge.get("target_input", "default")

            if src in node_outputs:
                upstream_out = node_outputs[src]
                if src_port in upstream_out:
                    inputs[tgt_port] = upstream_out[src_port]
                elif "default" in upstream_out:
                    inputs[tgt_port] = upstream_out["default"]

        return inputs

    def _with_defaults(
        self,
        node: dict[str, Any],
        inputs: dict[str, Any],
    ) -> dict[str, Any]:
        """Fill in default parameter values from node definition."""
        params: dict[str, Any] = {}
        # Widget values / parameters
        widgets = node.get("widgets", {})
        params.update(widgets)
        # Override with resolved inputs
        params.update(inputs)
        # Add metadata
        params["_node_type"] = node.get("type", "unknown")
        params["_output_ports"] = list(node.get("outputs", {}).keys()) or ["default"]
        return params

    def _bypass_outputs(
        self,
        node_id: str,
        node: dict[str, Any],
        edge_map: dict[str, list[dict[str, Any]]],
    ) -> dict[str, str]:
        """Compute bypassed node outputs by passing inputs through."""
        outputs: dict[str, str] = {}
        node_outputs_def = node.get("outputs", {})
        node_inputs = node.get("inputs", {})

        # For simple passthrough, map each output to the first input value
        input_values = [
            v["value"] if isinstance(v, dict) and "value" in v else v
            for v in node_inputs.values()
        ]
        input_values = [v for v in input_values if isinstance(v, str)]

        for out_name in node_outputs_def:
            if input_values:
                outputs[out_name] = input_values[0]
            else:
                outputs[out_name] = ""

        return outputs

    def _collect_previews(
        self,
        ctx: ExecutionContext,
        result: dict[str, Any],
    ) -> list[dict[str, Any]]:
        """Collect previewable output files (HTML, images, JSON, etc.)."""
        previews: list[dict[str, Any]] = []
        preview_exts = {".html", ".htm", ".png", ".jpg", ".jpeg", ".gif", ".svg", ".json", ".csv", ".tsv"}

        for port, path in result.get("outputs", {}).items():
            p = Path(path)
            if p.exists() and p.suffix.lower() in preview_exts:
                previews.append(
                    {
                        "path": str(p),
                        "label": f"{ctx.node_id}/{port}",
                        "node_id": ctx.node_id,
                    }
                )

        return previews + ctx._previews

    def _collect_artifacts(
        self,
        run_id: str,
        nodes: dict[str, dict[str, Any]],
        node_results: dict[str, dict[str, Any]],
    ) -> list[dict[str, Any]]:
        """Collect all output artifact file paths from the run."""
        artifacts: list[dict[str, Any]] = []
        for node_id, result in node_results.items():
            if result.get("status") not in ("completed", "cached", "bypassed"):
                continue
            outputs = result.get("outputs", {})
            for port, path in outputs.items():
                p = Path(path)
                if p.exists():
                    artifacts.append(
                        {
                            "node_id": node_id,
                            "node_type": nodes.get(node_id, {}).get("type", "unknown"),
                            "port": port,
                            "path": str(p),
                            "size": p.stat().st_size,
                        }
                    )
        return artifacts

    def _write_metadata(self, run_id: str, metadata: dict[str, Any]) -> None:
        """Write run metadata JSON to the workspace."""
        meta_dir = self.workspace_dir / "runs" / run_id
        meta_dir.mkdir(parents=True, exist_ok=True)
        meta_path = meta_dir / "run_metadata.json"
        with open(meta_path, "w", encoding="utf-8") as fh:
            json.dump(metadata, fh, indent=2, ensure_ascii=True)

    def _command_prefix(
        self,
        env_type: str | None,
        env_name: str | None,
        container: str | None,
    ) -> str:
        """Generate environment command prefix (conda/docker/apptainer)."""
        if container:
            if container.startswith("docker://"):
                return f"docker run --rm -v $(pwd):/work -w /work {container[9:]} "
            elif container.startswith("apptainer://") or container.startswith("singularity://"):
                img = container.split("://", 1)[1]
                return f"apptainer exec {img} "
            else:
                return f"apptainer exec {container} "

        if env_type == "conda" and env_name:
            return f"conda run -n {env_name} "
        if env_type == "micromamba" and env_name:
            return f"micromamba run -n {env_name} "

        return ""

    def _change_fingerprint(
        self,
        node_id: str,
        params: dict[str, Any],
        inputs: dict[str, Any],
    ) -> str:
        """Detect if node inputs changed by computing a fingerprint."""
        payload = json.dumps(
            {"params": params, "inputs": inputs},
            sort_keys=True,
            separators=(",", ":"),
        )
        return hashlib.sha256(payload.encode()).hexdigest()
