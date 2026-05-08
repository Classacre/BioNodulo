# Node API

Nodes are Python classes derived from `BaseNode` or `CommandNode`. BioNodulo can also adapt standalone schema-style custom nodes that expose `define_schema()` and `execute()` through `bionodulo.nodes.schema_api.io.SchemaNode`; see `custom_nodes/example_node.py.example`.

Required metadata:

- `NODE_ID`
- `DISPLAY_NAME`
- `CATEGORY`
- `RETURN_TYPES`
- `RETURN_NAMES`
- `INPUT_TYPES()`

Optional metadata:

- `DESCRIPTION`
- `SEARCH_ALIASES`
- `FUNCTION`
- `OUTPUT_NODE`
- `EXPERIMENTAL`
- `REQUIRED_EXECUTABLES`
- `DOCUMENTATION_URL`
- `ENVIRONMENT`
- `VERSION`

Optional hooks:

- `VALIDATE_INPUTS(...)`: return `True` or an error string before execution.
- `IS_CHANGED(...)`: return a cache fingerprint payload for important inputs or parameters.
- `PLAN_OUTPUTS(node_dir, params, inputs)`: predeclare run-local outputs.

`CommandNode` subclasses declare `COMMAND`, a list of command arguments with templates such as `{inputs.reads[0]}`, `{outputs.report}`, and `{params.threads}`. In mock mode, the command is not executed and placeholder outputs are created. In real mode, the executable must exist on `PATH`.

`run()` may be synchronous or asynchronous. When a node receives `context`, it can write to `context.node_dir`, emit logs with `await context.log(...)`, honor `context.cancel_event`, call external commands with `await context.run_command(...)`, and register previews with `await context.register_preview(...)`.

Frontend widgets can be hinted through the options dictionary in `INPUT_TYPES`, for example `{"widget": "slider", "min": 1, "max": 1000, "tooltip": "Records to scan"}`. BioNodulo passes these hints through `/object_info` so the static React UI can render sliders, checkboxes, text areas, and tooltips.

Custom nodes go in `custom_nodes/`. A broken import is recorded as a warning and does not crash the app.
