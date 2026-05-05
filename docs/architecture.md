# Architecture

BioNodulo is split into a Python backend and a browser frontend.

The backend owns node registration, workflow validation, queueing, execution, caching, logs, metadata, and run directories. The frontend queries `/object_info` and builds node cards and parameter widgets dynamically.

Core packages:

- `bionodulo.nodes`: node API, command-node API, built-in nodes, custom node loading
- `bionodulo.workflow`: workflow JSON schema, graph helpers, validation
- `bionodulo.execution`: queue, executor, cache, mock runner, subprocess runner, metadata
- `bionodulo.api`: REST routes and WebSocket endpoint

The implementation is ComfyUI-inspired in shape: Python node classes expose metadata, runs are queued asynchronously, WebSocket messages update the UI, and cache keys avoid recomputation. The domain model is bioinformatics-specific: file provenance, command lines, tool availability, logs, outputs, and reproducibility are first-class concerns.
