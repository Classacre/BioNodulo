# Node API

Nodes are Python classes derived from `BaseNode` or `CommandNode`.

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
- `OUTPUT_NODE`
- `EXPERIMENTAL`
- `REQUIRED_EXECUTABLES`
- `DOCUMENTATION_URL`
- `ENVIRONMENT`
- `VERSION`

`CommandNode` subclasses declare `COMMAND`, a list of command arguments with templates such as `{inputs.reads[0]}`, `{outputs.report}`, and `{params.threads}`. In mock mode, the command is not executed and placeholder outputs are created. In real mode, the executable must exist on `PATH`.

Custom nodes go in `custom_nodes/`. A broken import is recorded as a warning and does not crash the app.
