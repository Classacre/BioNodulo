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
from bionodulo.execution.run_metadata import RunRecord, utc_now
from bionodulo.execution.subprocess_runner import CommandExecutionError, run_subprocess
from bionodulo.nodes.command_node import CommandNode
from bionodulo.nodes.registry import NodeRegistry
from bionodulo.workflow.graph import incoming_edges, topological_sort, upstream_nodes
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
        emit,
    ) -> None:
        self.registry = registry
        self.runs_dir = runs_dir
        self.cache = CacheStore(cache_dir)
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
        cancel_event: asyncio.Event | None = None,
    ) -> RunRecord:
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
        force_nodes = force_nodes or []
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

            upstream_failed = [edge.from_.node for edge in incoming.get(node.id, []) if edge.from_.node in failed_nodes]
            if upstream_failed:
                record.node_statuses[node.id] = "blocked"
                failed_nodes.add(node.id)
                await self.emit("execution_error", {"run_id": run_id, "node_id": node.id, "node_type": node.type, "status": "blocked", "message": f"Blocked by failed upstream node(s): {', '.join(upstream_failed)}"})
                continue

            resolved_inputs = self._resolve_inputs(node_id=node.id, workflow=workflow, values=values, params=node.params)
            params = self._with_defaults(node_cls.INPUT_TYPES(), node.params)
            planned_outputs = node_cls.PLAN_OUTPUTS(node_dir, params, resolved_inputs)
            upstream_cache_keys = [cache_keys.get(edge.from_.node, "") for edge in incoming.get(node.id, [])]
            command_template = getattr(node_cls, "COMMAND", None) if issubclass(node_cls, CommandNode) else None
            cache_key = cache_key_for_node(
                node_type=node.type,
                node_version=node_cls.VERSION,
                command_template=command_template,
                params=params,
                inputs=resolved_inputs,
                upstream_cache_keys=upstream_cache_keys,
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

            if not force and node.id not in force_nodes and self.cache.is_hit(cache_key, planned_outputs):
                marker = self.cache.read_marker(cache_key) or {}
                outputs = marker.get("outputs", planned_outputs)
                values[node.id] = outputs
                record.node_statuses[node.id] = "cached"
                record.node_outputs[node.id] = outputs
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
                await self.emit("executed", {"run_id": run_id, "node_id": node.id, "node_type": node.type, "outputs": outputs})
            except Exception as exc:
                failed_nodes.add(node.id)
                record.node_statuses[node.id] = "failed"
                metadata["ended_at"] = utc_now()
                metadata["status"] = "failed"
                metadata["error"] = str(exc)
                (node_dir / "metadata.json").write_text(json.dumps(metadata, indent=2, default=str), encoding="utf-8")
                (node_dir / "stderr.log").open("a", encoding="utf-8").write(str(exc) + "\n")
                await self.emit("execution_error", {"run_id": run_id, "node_id": node.id, "node_type": node.type, "status": "failed", "message": str(exc)})
                for blocked_id in topo_order[index + 1 :]:
                    if blocked_id in wanted_nodes and blocked_id not in record.node_statuses:
                        blocked_node = nodes_by_id[blocked_id]
                        record.node_statuses[blocked_id] = "blocked"
                        failed_nodes.add(blocked_id)
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
