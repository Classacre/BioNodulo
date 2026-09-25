# Architecture

BioNodulo combines a Python workflow engine with a React editor. The desktop
application packages the same backend and editor; the website lives in the
separate `bionodulo-website` repository.

## Entry points

| Path | Responsibility |
| --- | --- |
| `main.py` | Command-line options and Uvicorn startup |
| `server.py` | FastAPI application, service lifecycle, routes and static frontend |
| `lambda_handler.py` | AWS Lambda adapter |
| `web/src/` | React/TypeScript editor, state and API clients |
| `desktop/` | Tauri application and backend packaging |
| `mcp/` | Separately packaged MCP server |

## Backend modules

| Package | Responsibility |
| --- | --- |
| `bionodulo/api/` | HTTP routes, authentication and WebSocket endpoints |
| `bionodulo/core/` | Settings, workspace paths, events and shared services |
| `bionodulo/nodes/` | Node discovery, contracts, catalogs and implementations |
| `bionodulo/workflow/` | Workflow models, validation and serialization |
| `bionodulo/execution/` | Queue, execution, cancellation, caching and run records |
| `bionodulo/environments/` | Runtime requirements, environment creation and committed locks |
| `bionodulo/manager/` | Custom node installation and dependency diagnostics |
| `bionodulo/converter/` | Workflow import/export adapters |
| `bionodulo/hpc/` | SLURM, PBS/Torque and SGE backends |
| `bionodulo/collab/` | Native Yjs collaboration, presence and access control |
| `bionodulo/provenance/` | Output metadata, workflow embedding and execution evidence |
| `bionodulo/ai/` | Assistant providers and research tools |

## Workflow execution

The editor submits a saved workflow to the API. Validation resolves its node
types and checks connections and execution readiness. The queue delegates to
the executor, which stages inputs, selects environments, executes nodes and
records outputs. WebSocket events carry progress back to the editor.

Local execution, HPC submission and cloud workers have different runtime
requirements. The shared editor mode serves catalog and editing endpoints
without creating a local execution queue or loading user custom-node code.

## Catalogs and compatibility

The runtime includes existing Python nodes, typed catalog definitions and
descriptor-driven CWL integrations. They share registry discovery and workflow
execution infrastructure. Older node IDs and import shims can still be needed by
saved workflows and plugins; a newer catalog does not imply every older node is
replaceable.

Generated bio.tools reference entries describe registry records and explicitly
refuse execution. Executable integrations require an admitted descriptor and
runtime evidence. See [tool integration](tool-integration.md) for the profiles
and their limits.

## Source and generated files

`templates/`, `examples/` and `tests/fixtures/` contain committed inputs.
`bionodulo/nodes/generated/` and the node index/metadata files contain generated
artifacts consumed by the application or validation tools. Maintain them with
the [catalog scripts](../scripts/README.md), rather than editing them by hand.

Build output, virtual environments, caches and local run workspaces are ignored.
Scientific receipts in [reports](../reports/README.md) are retained with their
scope and reproduction notes; they are not application state.
