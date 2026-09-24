# Universal tool integration and generated semantic contracts

Status: architecture direction clarified from the user's request and the v4 proposal. An initial native CWL descriptor-to-app execution path is implemented; the general acquisition, generation, container probing and scientific validation system remains required. See [the implemented profile and its limits](../../universal-cwl.md).

## Objective and proposal alignment

The product objective is a reusable system that generates executable, contract-bearing integrations. Progress is measured by the generator's performance on previously unseen tools and versions, rather than by the number of Python wrappers written by hand.

The supplied proposal explicitly says “Coverage is generated rather than curated” (document paragraph P28). Aim A calls for documentation/registry inference, container-based empirical probes, human confirmation, an expert reference corpus of roughly fifty tools, and a declarative YAML description with JSON Schema and MCP tooling (P33–P38). The proposal's human review and reference contracts remain part of the research design; they are not a requirement to implement the production library by hand.

Source: [extracted v4 proposal](../../../../phd-verification-2026-09-19/proposal-extracted.txt), verified against the unchanged DOCX SHA-256 `62b2a066eac79018585530e554d52d4cad7c04dade28e8c1904d5faa0013acb0`.

The wording that maintenance does not scale with tool count is a hypothesis to test and refine. Automation can reduce marginal effort; evidence, unavailable dependencies, interface changes and ambiguous semantics still incur costs. Do not claim zero maintenance or guaranteed correct execution of every arbitrary program.

## Architectural invariant

Adding a tool described by an already supported interface must require no new BioNodulo Python class, tool-name branch, hand-edited static index or copied command renderer. A generated descriptor and its evidence are data consumed by shared runtime implementations.

Importers and runtime backends are implemented per interface standard or execution mechanism. A newly encountered capability may require a reusable backend extension. It must not be hidden behind a supposedly universal per-tool exception table.

```mermaid
flowchart LR
    A[Registry and upstream descriptors] --> B[Identity and interface resolution]
    B --> C[Descriptor generation and contract inference]
    C --> D[Shared compiler and runtime]
    D --> E[Isolated probes and independent checks]
    E --> F[Evidence and contract review]
    F --> G[Generated app nodes and exports]
    G --> H[Version drift and revalidation]
    H --> B
```

## Information sources and responsibilities

bio.tools supplies discovery, identities, operation/format annotations and links. Its own curation guide describes deliberately coarse functional metadata and excludes many invocation parameters. Entries can expose command-line, API, service or web interfaces, sometimes several interfaces for one entry. Consequently, a registry record cannot be assumed to be a complete executable specification. [Official curation guide](https://biotools.readthedocs.io/en/latest/curators_guide.html).

Prefer existing executable descriptions and fixtures over recreating them. CWL describes command/input/output bindings and runtime requirements; Galaxy tool descriptions include command, parameter, output and test structures. Boutiques provides another descriptor-based execution ecosystem. Their scientific semantic guarantees still need separate evidence. [CWL specification](https://www.commonwl.org/v1.2/CommandLineTool.html), [Galaxy schema](https://docs.galaxyproject.org/en/latest/dev/schema.html), [Boutiques](https://github.com/boutiques/boutiques).

The proposed acquisition order is:

1. Identify the exact upstream project, operation, version, platform and interface; keep registry identity separate from package-name guesses.
2. Import supported upstream descriptors with their source revision, license and fixtures. Preserve semantics that cannot yet be lowered; reject unsupported requirements explicitly.
3. Where no descriptor exists, draft an invocation specification from authoritative documentation, structured command help, source interfaces and package/container metadata. Model-assisted extraction may propose bindings and semantic clauses; it cannot promote its own guesses into verified facts.
4. Resolve an exact runtime and dependencies. A container/package locator is not by itself a complete invocation or scientific contract.
5. Probe and independently validate before promoting readiness. Missing inputs, references, credentials, licensing access, unsupported interfaces or absent validation cases stay visible as concrete gaps.

Avoid treating Galaxy command templates or CWL expressions as simple strings. Full-standard execution should use the appropriate established engine where practical; any native lowering must advertise and test its supported capability profile. Unsupported constructs must not disappear during translation.

## Shared descriptor and execution design

Extend the existing strict `NodeSpec`, environment, parameter, artifact, output, evidence and maturity models. Do not create a parallel incompatible node schema or a second job queue.

A versioned invocation recipe must carry executable/operation identity, argument and parameter bindings, input staging, output bindings, streams, runtime requirements, resource limits, conditional behavior and source digests. It contains data or a retained upstream descriptor executed by an explicit standard backend; it does not require an arbitrary tool-specific Python factory.

Keep structural invocation evidence separate from semantic claims. Each contract clause needs its source, applicable version/parameter conditions, review state, empirical observations and unresolved assumptions. EDAM labels or a successful exit must never establish reference identity, raw-count units, strandedness, normalization or other biological guarantees by themselves.

Generate UI ports/forms, execution bindings, catalog metadata and export representations from the same descriptor. The app registry binds the descriptor to a shared runner. Runtime evidence uses the existing provenance, artifact hashes, semantic checking and custody controls. Descriptors must not carry embedded credentials; runs use explicit existing secret bindings.

## Integration seams identified before this implementation

The table records the starting point of this change, not the current completion state. The native CWL slice now adds the invocation binding and compiler projection, loads a data-only catalog through the app's `bionodulo/nodes/registry.py`, and uses the existing executor. The remaining general acquisition and scientific-evidence work is described below.

| Existing surface | What it supplies | Required change |
|---|---|---|
| `bionodulo/nodes/contract/model.py:314` | Strict `NodeSpec` and runtime/environment/evidence fields | Add an explicit descriptor-backed invocation binding; current `execution_factory` still names Python code |
| `bionodulo/nodes/contract/execution.py:1` | Validated argv, pipeline, script, Python, R, HTTP and container plan models | Implement/reuse lowering and execution per supported capability; the module explicitly contains no execution behavior |
| `bionodulo/nodes/contract/compiler.py:218` | Catalog compilation and consistent projections | Compile descriptor data and preserve source/evidence identity without requiring one source module per tool |
| `bionodulo/nodes/catalog/registry.py:226` | Lazy resolution and maturity enforcement | Bind a descriptor to a shared executor, while retaining the legacy compatibility path |
| `bionodulo/execution/executor.py:161` | Existing command execution context | Reuse logging, cancellation, environment and queue integration; do not build a detached demo-only runner |
| `bionodulo/nodes/catalog/tools/samtools/view.py:16` | A typed reference integration | Currently delegates to `LEGACY_NODE`; use it as a regression oracle, not a universal implementation pattern |
| `scripts/compile_catalog.py:1` | Seven typed projections plus the legacy catalog | Replace manual discovery assumptions for the generated-descriptor path without rewriting the historical ledger |
| `scripts/infer_contracts.py:91` | Draft metadata-based inference | Replace unsupported generic propagation assumptions with traceable candidates and measured/reviewed clauses |
| `bionodulo/converter/cwl_node_runner.py:17` | A five-node export helper | This is not an importer/runtime for arbitrary upstream CWL descriptions; do not count it as universal integration |

Existing working integrations and their real-tool fixtures remain valuable regression and reference cases. Incremental migration must preserve them while the shared path is established. The September audit's coverage results remain bounded historical evidence, not proof that the generator exists.

## First complete implementation slice

Start with a declared CWL CommandLineTool capability profile because it offers a machine-readable invocation interface and a defined conformance target. The implemented first profile uses the existing native subprocess executor with explicit rejection of unsupported CWL features. General CWL support should use a pinned established engine where practical. Extend the same descriptor path to additional standards and invocation sources after this path works.

The broader acceptance target is complete only when all of these hold; a passing development fixture does not establish every item:

1. An upstream descriptor absent from the implementation fixtures is ingested, validated and retained with its source identity. No new per-tool code, name branch or registry allowlist entry is added.
2. The generated node appears through the ordinary app discovery API and UI with descriptor-derived controls and ports.
3. A normal workflow runs it through the existing queue/executor in a pinned runtime. This must execute the real tool, not a mocked subprocess or a parser-only test.
4. An independently specified fixture checks the materialized outputs. Exit zero, output existence or an oracle generated by the same inference step is insufficient evidence.
5. A workflow containing at least two independently acquired descriptors composes, executes and preserves provenance. Unknown biological state remains unknown; known incompatible states are rejected.
6. A held-out tool with materially different parameter/output behavior works without changing core code. An unsupported descriptor and an intentionally wrong mapping fail with actionable evidence rather than a fabricated successful integration.
7. A changed upstream descriptor/tool version invalidates the relevant validation receipt and triggers regeneration/retesting. A prior receipt cannot silently validate the new revision.

The existing isolated Linux audit environment can support initial local tests. Docker/container execution and the native desktop's broken original WSL registration remain separate unresolved runtime concerns; do not claim the container-probing requirement complete using native runs alone.

## Evaluation at ecosystem scale

Report separate denominators for registry entries, executable operations, versions, platforms and interface classes. A suite entry may expose many commands; a service and its underlying CLI must not be silently double-counted as independently validated algorithms.

Freeze a representative development corpus and a held-out evaluation corpus. Measure descriptor acquisition, automatic generation, installation, executable-test success, semantic-clause correctness, false-safe admission, abstention reasons, manual corrections/time per tool and regeneration success across version changes. Stratify results by source/interface and complexity, rather than selecting only convenient tools. These are proposed evaluation measures; no result is claimed here.

Compare inferred clauses to the proposal's independently authored expert contracts and report agreement with an appropriate chance-corrected method. Preserve the separate human study and scientific validation requirements. Neither registry coverage nor parser/test coverage substitutes for these outcomes.

The immediate engineering priority is the descriptor-to-app-execution path and the generation/probing system. Additional hand-written adapters are justified as reference fixtures or reusable capability investigations, not as the mechanism for attaining universal coverage.
