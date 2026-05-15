"""
WorkflowExecutor - the main execution engine for BioNodulo v2.

Executes workflow graphs with support for:
- Topological-sort execution order
- Input resolution from upstream node outputs
- Muted and bypassed node handling
- Cache hit detection and skipping
- Real execution with optional environment isolation
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
        api_secrets: Dictionary of resolved API secrets.
        emit: Callback for emitting WebSocket events.
        cancel_event: Asyncio event that signals cancellation.
        env_prefix: Optional command prefix for environment isolation
            (e.g. ["pixi", "run", "-e", "qc", "--"]).
    """

    run_id: str
    node_id: str
    node_type: str
    node_dir: Path
    workspace_dir: Path
    params: dict[str, Any]
    api_secrets: dict[str, str]
    emit: Callable[[str, dict[str, Any]], None]
    cancel_event: asyncio.Event
    env_prefix: list[str] = field(default_factory=list)

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

        If ``env_prefix`` is set, commands are wrapped for isolated execution.
        """
        stdout_path = self.node_dir / "stdout.log"
        stderr_path = self.node_dir / "stderr.log"

        # Wrap command with environment prefix if isolated execution is configured
        wrapped_cmd: str | list[str] = cmd
        if self.env_prefix:
            if isinstance(cmd, str):
                wrapped_cmd = " ".join(self.env_prefix) + " " + cmd
            else:
                wrapped_cmd = self.env_prefix + list(cmd)

        return await run_subprocess(
            cmd=wrapped_cmd,
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
    handling caching, muting, bypassing, and error recovery.
    """

    def __init__(
        self,
        cache_dir: str | Path | None = None,
        workspace_dir: str | Path = "./workspace",
        registry: Any | None = None,
        settings: Any | None = None,
    ) -> None:
        self.workspace_dir = Path(workspace_dir)
        self.cache = CacheStore(cache_dir or self.workspace_dir / "cache")
        self.workspace_dir.mkdir(parents=True, exist_ok=True)
        self.registry = registry
        self.settings = settings

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def execute(
        self,
        run_id: str,
        workflow: dict[str, Any],
        record: Any | None = None,
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

        # File extensions considered previewable
        preview_exts = {".html", ".htm", ".png", ".jpg", ".jpeg", ".gif", ".svg", ".json", ".csv", ".tsv"}

        # Build adjacency lists
        upstream_of: dict[str, list[str]] = {nid: [] for nid in nodes}
        downstream_of: dict[str, list[str]] = {nid: [] for nid in nodes}
        edge_map: dict[str, list[dict[str, Any]]] = {nid: [] for nid in nodes}

        for edge in edges:
            # Support both formats:
            #   ComfyUI-style: {"source": "node_id", "target": "node_id", ...}
            #   BioNodulo-style: {"from": {"node": "id", "output": "port"},
            #                    "to":   {"node": "id", "input": "port"}}
            src = edge.get("source")
            tgt = edge.get("target")
            if src is None and "from" in edge:
                src = edge["from"].get("node") if isinstance(edge["from"], dict) else edge["from"]
            if tgt is None and "to" in edge:
                tgt = edge["to"].get("node") if isinstance(edge["to"], dict) else edge["to"]

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
            _node_class = node.get("_node_class")
            if _node_class is None and self.registry is not None and hasattr(self.registry, "get"):
                _node_class = self.registry.get(node.get("type", "unknown"))
            resolved_params = self._with_defaults(node, resolved_inputs, _node_class)

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
                # Collect previews from cached outputs too
                for port, path in cached_outputs.items():
                    paths = path if isinstance(path, (list, tuple)) else [path]
                    for p_str in paths:
                        if not isinstance(p_str, (str, Path)):
                            continue
                        p = Path(p_str)
                        if p.exists() and p.suffix.lower() in preview_exts:
                            previews.append(
                                {
                                    "path": str(p),
                                    "label": f"{node_id}/{port}",
                                    "node_id": node_id,
                                }
                            )
                continue

            # ---- Prepare node working directory ----
            node_dir = self.workspace_dir / "runs" / run_id / node_id
            node_dir.mkdir(parents=True, exist_ok=True)

            # ---- Determine environment prefix for isolated execution ----
            env_prefix: list[str] = []
            isolation = getattr(self.settings, "execution", None)
            isolation_mode = getattr(isolation, "env_isolation", "auto") if isolation else "auto"
            if isolation_mode in ("auto", "always"):
                env_prefix = self._env_prefix_for_node(node)

            # ---- Build execution context ----
            ctx = ExecutionContext(
                run_id=run_id,
                node_id=node_id,
                node_type=node_type,
                node_dir=node_dir,
                workspace_dir=self.workspace_dir,
                params=resolved_params,
                api_secrets=options.get("api_secrets", {}),
                emit=emit,
                cancel_event=cancel_event,
                env_prefix=env_prefix,
            )

            # ---- Execute the node ----
            try:
                result = await self._execute_node(ctx, node, resolved_inputs)
                outputs = result.get("outputs", {})
                node_results[node_id] = {
                    "status": "completed",
                    "outputs": outputs,
                    "cache_key": cache_key,
                }
                node_outputs[node_id] = outputs

                # Cache the result
                self.cache.write_marker(
                    cache_key=cache_key,
                    outputs=outputs,
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
                        "outputs": outputs,
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

    # Types that indicate a file or directory path parameter
    _FILE_TYPES: set[str] = {
        "FASTQ_LIST", "FASTA", "FASTQ", "BAM", "SAM", "VCF", "GFF", "GTF",
        "BED", "WIG", "BIGWIG", "FILE", "DIR", "PATH", "INDEX_DIR",
        "REFERENCE", "READS", "ASSEMBLY", "CONTIGS", "ALIGNMENT",
        "REPORT", "PLOT", "IMAGE", "TABLE", "MATRIX", "TREE",
    }

    def _resolve_file_paths(
        self,
        node_class: Any,
        inputs: dict[str, Any],
    ) -> dict[str, Any]:
        """Resolve relative file paths in inputs against the workspace root."""
        try:
            input_types = node_class.INPUT_TYPES()
        except Exception:
            return inputs

        # Collect parameter names whose type indicates a file path
        file_params: set[str] = set()
        for section in ("required", "optional", "hidden"):
            for name, spec in input_types.get(section, {}).items():
                if isinstance(spec, tuple) and len(spec) > 0:
                    type_name = spec[0]
                    if isinstance(type_name, str) and type_name.upper() in self._FILE_TYPES:
                        file_params.add(name)

        if not file_params:
            return inputs

        resolved = dict(inputs)
        for name in file_params:
            if name not in resolved:
                continue
            val = resolved[name]
            if isinstance(val, str):
                resolved[name] = self._resolve_single_path(val)
            elif isinstance(val, (list, tuple)):
                resolved[name] = [
                    self._resolve_single_path(v) if isinstance(v, str) else v
                    for v in val
                ]
        return resolved

    def _resolve_single_path(self, path_str: str) -> str:
        """Convert a relative path to absolute against the workspace root."""
        if not path_str or path_str.startswith("/") or path_str.startswith("~"):
            return path_str
        # Leave URLs and simple names alone
        if "://" in path_str or "/" not in path_str:
            return path_str
        # Try workspace_dir first
        abs_path = (self.workspace_dir / path_str).resolve()
        if abs_path.exists():
            return str(abs_path)
        # Fallback: resolve relative to cwd (repo root when server starts from repo)
        cwd_path = Path(path_str).resolve()
        if cwd_path.exists():
            return str(cwd_path)
        return path_str

    async def _execute_node(
        self,
        ctx: ExecutionContext,
        node: dict[str, Any],
        inputs: dict[str, Any],
    ) -> dict[str, Any]:
        """Execute a single node via its ``run()`` method."""
        node_type = node.get("type", "unknown")
        node_class = node.get("_node_class")
        # Fallback: look up in registry if _node_class is not attached
        if node_class is None and self.registry is not None and hasattr(self.registry, "get"):
            node_class = self.registry.get(node.get("type", "unknown"))
        if node_class is not None and hasattr(node_class, "run"):
            kwargs = {**inputs, **ctx.params}
            kwargs = {k: v for k, v in kwargs.items() if not k.startswith("_")}
            kwargs = self._resolve_file_paths(node_class, kwargs)
            node_instance = node_class()
            if asyncio.iscoroutinefunction(node_class.run):
                raw = await node_instance.run(context=ctx, **kwargs)
            else:
                raw = node_instance.run(context=ctx, **kwargs)
            return self._normalize_result(raw, node_class)

        raise RuntimeError(
            f"Node class not found for '{node.get('type', 'unknown')}'. "
            "Ensure the node is registered in the node registry."
        )

    def _normalize_result(
        self,
        raw: Any,
        node_class: Any,
    ) -> dict[str, Any]:
        """Normalize node return value to dict format expected by the executor."""
        if isinstance(raw, dict):
            return raw
        if isinstance(raw, tuple):
            return_names = getattr(node_class, "RETURN_NAMES", ()) or ()
            outputs: dict[str, Any] = {}
            for idx, val in enumerate(raw):
                name = return_names[idx] if idx < len(return_names) else f"output_{idx}"
                outputs[name] = val
            return {"outputs": outputs}
        if raw is None:
            return {"outputs": {}}
        # Single scalar value
        return_names = getattr(node_class, "RETURN_NAMES", ()) or ()
        name = return_names[0] if return_names else "default"
        return {"outputs": {name: raw}}

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

        # Fallback: use params if no inputs defined (frontend/template format)
        if not inputs:
            for pname, pval in node.get("params", {}).items():
                inputs[pname] = pval

        # Override with upstream connections
        for edge in edge_map.get(node_id, []):
            # ComfyUI-style edges
            src = edge.get("source")
            src_port = edge.get("source_output", "default")
            tgt_port = edge.get("target_input", "default")

            # BioNodulo-style edges: {"from": {"node": ..., "output": ...},
            #                         "to":   {"node": ..., "input": ...}}
            if src is None and "from" in edge:
                from_data = edge["from"]
                if isinstance(from_data, dict):
                    src = from_data.get("node")
                    src_port = from_data.get("output", "default")
                else:
                    src = from_data
            if "to" in edge:
                to_data = edge["to"]
                if isinstance(to_data, dict):
                    tgt_port = to_data.get("input", "default")

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
        node_class: Any = None,
    ) -> dict[str, Any]:
        """Fill in default parameter values from node definition."""
        params: dict[str, Any] = {}
        # Widget values / parameters
        widgets = node.get("widgets", {})
        params.update(widgets)
        # Fallback: params from frontend/template format
        for pname, pval in node.get("params", {}).items():
            if pname not in params:
                params[pname] = pval
        # Pull defaults from node class INPUT_TYPES if available
        if node_class is not None and hasattr(node_class, "INPUT_TYPES"):
            try:
                input_types = node_class.INPUT_TYPES()
                for section in ("required", "optional", "hidden"):
                    for name, spec in input_types.get(section, {}).items():
                        if name not in params and isinstance(spec, (list, tuple)) and len(spec) > 1:
                            config = spec[1]
                            if isinstance(config, dict) and "default" in config:
                                params[name] = config["default"]
            except Exception:
                pass
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
            paths = path if isinstance(path, (list, tuple)) else [path]
            for p_str in paths:
                if not isinstance(p_str, (str, Path)):
                    continue
                p = Path(p_str)
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
                paths = path if isinstance(path, (list, tuple)) else [path]
                for p_str in paths:
                    if not isinstance(p_str, (str, Path)):
                        continue
                    p = Path(p_str)
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

    def _env_prefix_for_node(self, node: dict[str, Any]) -> list[str]:
        """Compute the environment command prefix for a node.

        Derives the isolated environment name from the node's CATEGORY.
        Uses the node's own ENVIRONMENT spec if explicitly set.
        Falls back to bionodulo-tools if the per-category env does not exist.
        """
        node_type = node.get("type", "")
        node_class = node.get("_node_class")

        # If _node_class is not attached, try registry lookup
        if node_class is None and self.registry is not None and hasattr(self.registry, "get"):
            node_class = self.registry.get(node_type)

        category = "general"
        if node_class is not None:
            category = getattr(node_class, "CATEGORY", "general")

        # Use the node's own ENVIRONMENT if explicitly set
        env_spec = getattr(node_class, "ENVIRONMENT", {}) if node_class else {}
        if env_spec and isinstance(env_spec, dict):
            env_type = env_spec.get("type", "micromamba")
            env_name = env_spec.get("name", "")
            if env_name:
                return self._command_prefix_list(env_type, env_name)

        # Default: per-category isolated environment (pixi naming)
        env_name = category.lower().replace(' ', '-').replace('/', '-').replace('_', '-')

        # Fallback to tools if the per-category env does not exist
        try:
            from bionodulo.environments.manager import env_exists
            if not env_exists(env_name):
                env_name = "tools"
        except Exception:
            pass

        return self._command_prefix_list("pixi", env_name)

    def _command_prefix_list(
        self,
        env_type: str | None,
        env_name: str | None,
    ) -> list[str]:
        """Generate environment command prefix as a token list."""
        if not env_name:
            return []

        # Resolve the actual executable path (system or managed)
        exe = env_type or "pixi"
        if exe == "pixi":
            from bionodulo.manager.runtime_installer import get_pixi_path
            pixi_path = get_pixi_path()
            if pixi_path is not None:
                exe = str(pixi_path)
            else:
                exe = "pixi"

        if env_type in ("pixi", "conda", "mamba", "micromamba"):
            return [exe, "run", "-e", env_name, "--"]
        return []

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
