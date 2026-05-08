from __future__ import annotations

import asyncio
import inspect
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from bionodulo import __version__
from bionodulo.core.paths import safe_node_dir_name
from bionodulo.environments.conda import conda_run_prefix
from bionodulo.environments.containers import apptainer_run_prefix, docker_run_prefix
from bionodulo.execution.cache import CacheStore, cache_key_for_node
from bionodulo.execution.mock_runner import run_mock_node
from bionodulo.provenance.workflow_embed import embed_workflow_in_outputs
from bionodulo.execution.run_metadata import RunRecord, utc_now
from bionodulo.execution.subprocess_runner import CommandExecutionError, run_subprocess
from bionodulo.nodes.command_node import CommandNode
from bionodulo.nodes.registry import NodeRegistry
from bionodulo.nodes.types import is_compatible
from bionodulo.workflow.graph import downstream_nodes, incoming_edges, topological_sort, upstream_nodes
from bionodulo.workflow.schema import Workflow
from bionodulo.workflow.validation import validate_workflow


class ExecutionContext:
    def __init__(
        self,
        *,
        run_id: str,
        node_id: str,
        node_type: str,
        node_display_name: str,
        node_dir: Path,
        run_dir: Path,
        params: dict[str, Any],
        planned_outputs: dict[str, Any],
        mock_tools: bool,
        api_secrets: dict[str, str] | None,
        emit,
        cancel_event: asyncio.Event,
    ) -> None:
        self.run_id = run_id
        self.node_id = node_id
        self.node_type = node_type
        self.node_display_name = node_display_name
        self.node_dir = node_dir
        self.run_dir = run_dir
        self.params = params
        self._planned_outputs = planned_outputs
        self.mock_tools = mock_tools
        self.api_secrets = api_secrets or {}
        self.emit = emit
        self.cancel_event = cancel_event
        self.environment = None
        self.command_prefix: list[str] = []
        self.stdout_log = node_dir / "stdout.log"
        self.stderr_log = node_dir / "stderr.log"

    def planned_outputs(self) -> dict[str, Any]:
        return self._planned_outputs

    async def log(self, stream: str, line: str) -> None:
        await self.emit(
            "node_log",
            {"run_id": self.run_id, "node_id": self.node_id, "node_type": self.node_type, "stream": stream, "line": line},
        )

    def resolve_secret(self, name: str) -> str:
        return self.api_secrets.get(name, "")

    async def register_preview(self, *, path: str, kind: str = "file", label: str | None = None) -> dict[str, Any]:
        preview = {"node_id": self.node_id, "path": path, "kind": kind, "label": label or Path(path).name}
        await self.emit("preview_available", {"run_id": self.run_id, **preview})
        return preview

    async def run_command(self, *, command: list[str], outputs: dict[str, Any]) -> dict[str, Any]:
        self.node_dir.mkdir(parents=True, exist_ok=True)
        executable_command = [*self.command_prefix, *command] if self.command_prefix else command
        (self.node_dir / "command.txt").write_text(" ".join(executable_command) + "\n", encoding="utf-8")
        if self.mock_tools:
            await run_mock_node(
                node_display_name=self.node_display_name,
                outputs=outputs,
                node_dir=self.node_dir,
                stdout_log=self.stdout_log,
                emit_log=self.log,
            )
            return outputs

        returncode = await run_subprocess(
            executable_command,
            cwd=self.run_dir,
            stdout_log=self.stdout_log,
            stderr_log=self.stderr_log,
            emit_log=self.log,
        )
        if returncode != 0:
            raise CommandExecutionError(executable_command, returncode)
        return outputs


class WorkflowExecutor:
    def __init__(
        self,
        *,
        registry: NodeRegistry,
        runs_dir: Path,
        cache_dir: Path,
        api_secrets: dict[str, str] | None = None,
        emit,
    ) -> None:
        self.registry = registry
        self.runs_dir = runs_dir
        self.cache = CacheStore(cache_dir)
        self.api_secrets = api_secrets or {}
        self.emit = emit

    async def execute(
        self,
        *,
        run_id: str,
        workflow: Workflow,
        record: RunRecord,
        mock_tools: bool,
        force: bool = False,
        force_nodes: list[str] | None = None,
        options: dict[str, Any] | None = None,
        cancel_event: asyncio.Event | None = None,
    ) -> RunRecord:
        options = options or {}
        reuse_cache = bool(options.get("reuse_cache", True))
        strong_hashing = bool(options.get("strong_hashing", False))
        stop_on_error = bool(options.get("stop_on_error", True))
        cancel_event = cancel_event or asyncio.Event()
        run_dir = self.runs_dir / run_id
        run_dir.mkdir(parents=True, exist_ok=True)
        (run_dir / "nodes").mkdir(exist_ok=True)
        (run_dir / "reports").mkdir(exist_ok=True)
        (run_dir / "workflow.json").write_text(json.dumps(workflow.model_dump(by_alias=True), indent=2), encoding="utf-8")
        record.run_dir = str(run_dir)
        record.status = "running"
        record.started_at = utc_now()
        await self._write_metadata(run_dir, record, workflow)
        await self.emit("execution_start", {"run_id": run_id, "workflow_name": workflow.name})

        validation = validate_workflow(workflow, self.registry, mock_tools=mock_tools)
        if not validation.valid:
            record.status = "failed"
            record.error = "Workflow validation failed"
            record.ended_at = utc_now()
            await self.emit("execution_error", {"run_id": run_id, "errors": [issue.model_dump() for issue in validation.errors]})
            await self._write_metadata(run_dir, record, workflow)
            return record

        nodes_by_id = {node.id: node for node in workflow.nodes}
        wanted_nodes = upstream_nodes(workflow, workflow.outputs) if workflow.outputs else set(nodes_by_id)
        incoming = incoming_edges(workflow)
        values: dict[str, dict[str, Any]] = {}
        cache_keys: dict[str, str] = {}
        failed_nodes: set[str] = set()
        blocking_nodes: set[str] = set()
        force_nodes = force_nodes or []
        forced_closure = downstream_nodes(workflow, force_nodes) if force_nodes else set()
        topo_order = topological_sort(workflow)

        for index, node_id in enumerate(topo_order):
            if node_id not in wanted_nodes:
                continue
            node = nodes_by_id[node_id]
            node_cls = self.registry.get(node.type)
            node_dir = run_dir / "nodes" / safe_node_dir_name(node.id)
            node_dir.mkdir(parents=True, exist_ok=True)
            if cancel_event.is_set():
                record.node_statuses[node.id] = "interrupted"
                record.status = "interrupted"
                await self.emit("execution_interrupted", {"run_id": run_id, "node_id": node.id, "node_type": node.type})
                break

            if node.ui.muted:
                record.node_statuses[node.id] = "muted"
                record.execution_plan[node.id] = {"action": "skip", "reason": "muted"}
                blocking_nodes.add(node.id)
                await self.emit("execution_skipped", {"run_id": run_id, "node_id": node.id, "node_type": node.type, "reason": "muted"})
                continue

            upstream_failed = [edge.from_.node for edge in incoming.get(node.id, []) if edge.from_.node in blocking_nodes]
            if upstream_failed:
                record.node_statuses[node.id] = "blocked"
                failed_nodes.add(node.id)
                blocking_nodes.add(node.id)
                record.execution_plan[node.id] = {"action": "skip", "reason": "blocked", "upstream": upstream_failed}
                await self.emit("execution_error", {"run_id": run_id, "node_id": node.id, "node_type": node.type, "status": "blocked", "message": f"Blocked by failed upstream node(s): {', '.join(upstream_failed)}"})
                continue

            resolved_inputs = self._resolve_inputs(node_id=node.id, workflow=workflow, values=values, params=node.params)
            if node.ui.bypassed:
                outputs = self._bypass_outputs(node=node, workflow=workflow, values=values)
                if not outputs:
                    failed_nodes.add(node.id)
                    blocking_nodes.add(node.id)
                    record.node_statuses[node.id] = "failed"
                    record.execution_plan[node.id] = {"action": "skip", "reason": "bypass_unresolved"}
                    await self.emit("execution_error", {"run_id": run_id, "node_id": node.id, "node_type": node.type, "status": "failed", "message": "Bypass could not resolve a compatible upstream value."})
                    continue
                values[node.id] = outputs
                record.node_statuses[node.id] = "bypassed"
                record.node_outputs[node.id] = outputs
                record.execution_plan[node.id] = {"action": "skip", "reason": "bypassed"}
                await self.emit("execution_skipped", {"run_id": run_id, "node_id": node.id, "node_type": node.type, "reason": "bypassed", "outputs": outputs})
                continue
            params = self._with_defaults(node_cls.INPUT_TYPES(), node.params)
            planned_outputs = node_cls.PLAN_OUTPUTS(node_dir, params, resolved_inputs)
            upstream_cache_keys = [cache_keys.get(edge.from_.node, "") for edge in incoming.get(node.id, [])]
            command_template = getattr(node_cls, "COMMAND", None) if issubclass(node_cls, CommandNode) else None
            change_fingerprint = self._change_fingerprint(node_cls, params=params, resolved_inputs=resolved_inputs)
            cache_key = cache_key_for_node(
                node_type=node.type,
                node_version=node_cls.VERSION,
                command_template=command_template,
                params=params,
                inputs=resolved_inputs,
                upstream_cache_keys=upstream_cache_keys,
                change_fingerprint=change_fingerprint,
                strong_hashing=strong_hashing,
            )
            cache_keys[node.id] = cache_key
            metadata = {
                "run_id": run_id,
                "node_id": node.id,
                "node_type": node.type,
                "display_name": node_cls.DISPLAY_NAME,
                "started_at": utc_now(),
                "cache_key": cache_key,
                "params": params,
                "inputs": resolved_inputs,
                "environment": node_cls.ENVIRONMENT,
                "required_executables": node_cls.REQUIRED_EXECUTABLES,
            }

            forced = force or node.id in forced_closure
            if reuse_cache and not forced and self.cache.is_hit(cache_key, planned_outputs):
                marker = self.cache.read_marker(cache_key) or {}
                outputs = marker.get("outputs", planned_outputs)
                values[node.id] = outputs
                record.node_statuses[node.id] = "cached"
                record.node_outputs[node.id] = outputs
                record.execution_plan[node.id] = {"action": "skip", "reason": "cached", "cache_key": cache_key}
                previews = self._collect_previews(node.id, outputs)
                if previews:
                    record.previews[node.id] = previews
                record.artifacts.extend(self._collect_artifacts(node.id, outputs))
                await self.emit("execution_cached", {"run_id": run_id, "node_id": node.id, "node_type": node.type, "cache_key": cache_key})
                continue

            try:
                record.node_statuses[node.id] = "queued"
                await self.emit("node_queued", {"run_id": run_id, "node_id": node.id, "node_type": node.type})
                record.node_statuses[node.id] = "running"
                await self.emit("executing", {"run_id": run_id, "node_id": node.id, "node_type": node.type})
                context = ExecutionContext(
                    run_id=run_id,
                    node_id=node.id,
                    node_type=node.type,
                    node_display_name=node_cls.DISPLAY_NAME,
                    node_dir=node_dir,
                    run_dir=run_dir,
                    params=params,
                    planned_outputs=planned_outputs,
                    mock_tools=mock_tools,
                    api_secrets=self.api_secrets,
                    emit=self.emit,
                    cancel_event=cancel_event,
                )
                node_instance = node_cls()
                context.environment = workflow.environment
                context.command_prefix = self._command_prefix(workflow.environment, run_dir)
                runtime_kwargs = dict(params)
                runtime_kwargs.update(resolved_inputs)
                result = node_instance.run(context=context, **runtime_kwargs)
                if inspect.isawaitable(result):
                    result = await result
                outputs = result or planned_outputs
                (node_dir / "outputs.json").write_text(json.dumps(outputs, indent=2, default=str), encoding="utf-8")
                metadata["ended_at"] = utc_now()
                metadata["status"] = "completed"
                (node_dir / "metadata.json").write_text(json.dumps(metadata, indent=2, default=str), encoding="utf-8")
                self.cache.write_marker(cache_key, {"outputs": outputs, "metadata": metadata})
                values[node.id] = outputs
                record.node_statuses[node.id] = "completed"
                record.node_outputs[node.id] = outputs
                record.execution_plan[node.id] = {"action": "run", "reason": "forced" if forced else "dirty_input", "cache_key": cache_key}
                previews = self._collect_previews(node.id, outputs)
                if previews:
                    record.previews[node.id] = previews
                    for preview in previews:
                        await self.emit("preview_available", {"run_id": run_id, **preview})
                record.artifacts.extend(self._collect_artifacts(node.id, outputs))
                metadata["embedded_workflow"] = embed_workflow_in_outputs(outputs, workflow)
                await self.emit("executed", {"run_id": run_id, "node_id": node.id, "node_type": node.type, "outputs": outputs})
            except Exception as exc:
                failed_nodes.add(node.id)
                blocking_nodes.add(node.id)
                record.node_statuses[node.id] = "failed"
                record.execution_plan[node.id] = {"action": "run", "reason": "failed", "error": str(exc)}
                metadata["ended_at"] = utc_now()
                metadata["status"] = "failed"
                metadata["error"] = str(exc)
                (node_dir / "metadata.json").write_text(json.dumps(metadata, indent=2, default=str), encoding="utf-8")
                (node_dir / "stderr.log").open("a", encoding="utf-8").write(str(exc) + "\n")
                await self.emit("execution_error", {"run_id": run_id, "node_id": node.id, "node_type": node.type, "status": "failed", "message": str(exc)})
                if not stop_on_error:
                    continue
                for blocked_id in topo_order[index + 1 :]:
                    if blocked_id in wanted_nodes and blocked_id not in record.node_statuses:
                        blocked_node = nodes_by_id[blocked_id]
                        record.node_statuses[blocked_id] = "blocked"
                        failed_nodes.add(blocked_id)
                        blocking_nodes.add(blocked_id)
                        record.execution_plan[blocked_id] = {"action": "skip", "reason": "blocked", "upstream": [node.id]}
                        await self.emit(
                            "execution_error",
                            {
                                "run_id": run_id,
                                "node_id": blocked_id,
                                "node_type": blocked_node.type,
                                "status": "blocked",
                                "message": f"Workflow stopped after failed node: {node.id}",
                            },
                        )
                break

        if record.status == "interrupted":
            pass
        elif failed_nodes:
            record.status = "failed"
            record.error = f"{len(failed_nodes)} node(s) failed or were blocked"
        else:
            record.status = "completed"
            await self.emit("execution_success", {"run_id": run_id})
        record.ended_at = utc_now()
        await self._write_metadata(run_dir, record, workflow)
        return record

    def _bypass_outputs(self, *, node, workflow: Workflow, values: dict[str, dict[str, Any]]) -> dict[str, Any]:
        node_cls = self.registry.get(node.type)
        output_types = {name: typ for name, typ in zip(node_cls.RETURN_NAMES, node_cls.RETURN_TYPES, strict=False)}
        candidates: list[tuple[str, Any]] = []
        nodes_by_id = {item.id: item for item in workflow.nodes}
        for edge in incoming_edges(workflow).get(node.id, []):
            source = nodes_by_id.get(edge.from_.node)
            if not source or not self.registry.has(source.type) or edge.from_.output is None:
                continue
            source_cls = self.registry.get(source.type)
            source_types = {name: typ for name, typ in zip(source_cls.RETURN_NAMES, source_cls.RETURN_TYPES, strict=False)}
            source_type = source_types.get(edge.from_.output)
            source_value = values.get(edge.from_.node, {}).get(edge.from_.output)
            if source_type and source_value is not None:
                candidates.append((source_type, source_value))
        outputs = {}
        for output_name, output_type in output_types.items():
            for source_type, source_value in candidates:
                if is_compatible(source_type, output_type):
                    outputs[output_name] = source_value
                    break
        return outputs

    def _collect_previews(self, node_id: str, outputs: dict[str, Any]) -> list[dict[str, Any]]:
        previews = []
        for value in self._flatten(outputs):
            if not isinstance(value, str):
                continue
            path = Path(value)
            if path.is_file() and path.suffix.lower() in {".html", ".json", ".txt", ".log", ".png", ".jpg", ".jpeg", ".svg"}:
                previews.append({"node_id": node_id, "path": str(path), "kind": path.suffix.lower().lstrip(".") or "file", "label": path.name})
            elif path.is_dir():
                for child in sorted(path.iterdir())[:12]:
                    if child.is_file() and child.suffix.lower() in {".html", ".json", ".txt", ".log", ".png", ".jpg", ".jpeg", ".svg"}:
                        previews.append({"node_id": node_id, "path": str(child), "kind": child.suffix.lower().lstrip(".") or "file", "label": child.name})
        return previews

    def _collect_artifacts(self, node_id: str, outputs: dict[str, Any]) -> list[dict[str, Any]]:
        artifacts = []
        for value in self._flatten(outputs):
            if isinstance(value, str):
                path = Path(value)
                artifacts.append({"node_id": node_id, "path": str(path), "exists": path.exists(), "type": "directory" if path.is_dir() else "file"})
        return artifacts

    def _change_fingerprint(self, node_cls, *, params: dict[str, Any], resolved_inputs: dict[str, Any]) -> Any:
        try:
            return node_cls.IS_CHANGED(**{**params, **resolved_inputs})
        except TypeError:
            return node_cls.IS_CHANGED(**params)
        except Exception as exc:
            return {"is_changed_error": str(exc)}

    def _flatten(self, value: Any) -> list[Any]:
        if isinstance(value, dict):
            items: list[Any] = []
            for nested in value.values():
                items.extend(self._flatten(nested))
            return items
        if isinstance(value, (list, tuple)):
            items = []
            for nested in value:
                items.extend(self._flatten(nested))
            return items
        return [value]

    def _resolve_inputs(self, *, node_id: str, workflow: Workflow, values: dict[str, dict[str, Any]], params: dict[str, Any]) -> dict[str, Any]:
        resolved = dict(params)
        for edge in workflow.edges:
            if edge.to.node != node_id or edge.to.input is None or edge.from_.output is None:
                continue
            resolved[edge.to.input] = values.get(edge.from_.node, {}).get(edge.from_.output)
        return resolved

    def _with_defaults(self, input_types: dict, params: dict[str, Any]) -> dict[str, Any]:
        merged = dict(params)
        for section in ("required", "optional"):
            for name, (_, options) in input_types.get(section, {}).items():
                if name not in merged and "default" in options:
                    merged[name] = options["default"]
        return merged

    def _command_prefix(self, environment, run_dir: Path) -> list[str]:
        if environment.type == "conda":
            return conda_run_prefix(environment)
        if environment.type == "docker":
            return docker_run_prefix(environment, run_dir)
        if environment.type == "apptainer":
            return apptainer_run_prefix(environment, run_dir)
        return []

    async def _write_metadata(self, run_dir: Path, record: RunRecord, workflow: Workflow) -> None:
        payload = {
            "bionodulo_version": __version__,
            "metadata_written_at": datetime.now(timezone.utc).isoformat(),
            "run": record.as_dict(),
            "workflow": workflow.model_dump(by_alias=True),
        }
        (run_dir / "metadata.json").write_text(json.dumps(payload, indent=2, default=str), encoding="utf-8")
