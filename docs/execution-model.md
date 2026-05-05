# Execution Model

Runs are submitted with `POST /runs` and executed by an async queue.

The executor:

1. Validates the workflow.
2. Computes a topological order.
3. Restricts execution to explicit output nodes and their dependencies when `outputs` is set.
4. Resolves connected inputs from upstream node outputs.
5. Computes cache keys.
6. Executes Python nodes or command-template nodes.
7. Streams WebSocket events and node logs.
8. Writes run and node metadata.
9. Blocks downstream nodes if an upstream dependency fails.

Each run writes:

- `workflow.json`
- `metadata.json`
- `nodes/<node-id>/stdout.log`
- `nodes/<node-id>/stderr.log`
- `nodes/<node-id>/command.txt`
- `nodes/<node-id>/metadata.json`
- `nodes/<node-id>/outputs.json`

Mock mode sleeps briefly, emits realistic log lines, and creates placeholder outputs. Real mode uses `asyncio.create_subprocess_exec` and local `PATH`.
