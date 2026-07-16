# Design: BioNodulo Node Catalog Big-Bang Rebuild

**Date:** 2026-07-15
**Status:** Approved by delegated user decision - ready for implementation planning
**Primary repository:** `BioNodulo`
**Related repository:** `bionodulo-website`

## 1. Decision and objective

Replace the current 943-node catalog and its mechanically split builtin tree with a new contract-driven catalog built from authoritative upstream documentation and source code. The existing catalog remains available only as forensic input during development. There is one coordinated cutover after every stable node ID has an explicit disposition and the release gates pass.

The user selected a big-bang rebuild, approved aggressive reorganization, and selected quarantine because the product is not yet public. Correctness takes precedence over preserving current Python module paths or current palette categories.

The rebuild must:

- Preserve every stable `NODE_ID`, or record an explicit deprecated tombstone. IDs are never silently lost, reused, or renamed.
- Use one typed contract as the source for backend validation, execution, frontend metadata, wiring compatibility, documentation, and environment resolution.
- Keep all nodes out of the normal palette until their computed verification gates pass.
- Validate tool flags, inputs, parameters, outputs, versions, and dependencies against official documentation, pinned upstream source, and real tool behavior.
- Prove released templates through the website, SkyPilot, a real worker, R2, callbacks, and downloadable outputs.
- Keep heavyweight package and data testing off the Codex host.

## 2. Why the current tree is not a migration base

There were two mechanical splits, neither a semantic decomposition. Commit `44c247986f3bcfe8f8d93d0d719a53e4853d0437` contains the true `galaxy_parity.py` monolith: 78,776 lines holding 551 of today's 943 IDs; the other 392 IDs already lived in native modules. Commit `a346ded79659d5a10e3056d7cf8ea2bf482606a7` distributed those 551 classes unchanged into 15 arbitrary `wrapped_*` batches whose names mix many unrelated categories. The later `scripts/extract_nodes.py` split groups on the first `NODE_ID`, uses one flat `CATEGORY`, copies the module preamble into generated files, and cannot reproduce the manually maintained facade and compatibility behavior. It created duplicated helpers and state, large pseudo-single-node modules, eager import fan-out, broken relative resource paths, missing sibling symbols, and metadata that can retain deleted nodes.

More importantly, the node contract currently has several independent interpretations:

- Python tuple-shaped `INPUT_TYPES`, class variables, and `RETURN_TYPES`/`RETURN_NAMES`.
- Registry conversion that reduces unsupported types to frontend `STRING`.
- Backend workflow validation that does not enforce exact source/target ports or type compatibility.
- Frontend family-prefix compatibility rules.
- Executor-specific list detection and result normalization.
- Environment and dependency resolution that is not fully represented in persisted manifests.

Repairing each layer independently would preserve the root problem. The new catalog is therefore additive during development and replaces the legacy resolver only at cutover.

## 3. Scope decomposition

This program has four coordinated workstreams:

1. **Contract and compiler foundation** - typed models, artifact registry, compatibility rules, execution plans, evidence, maturity, catalog compiler, and generated projections.
2. **Catalog reconstruction** - all 943 IDs partitioned by upstream tool/provider/library/core ownership and rebuilt from authoritative evidence.
3. **Workflow and template reconstruction** - exact port migrations, template validation, fixture workflows, and released template cloud proofs.
4. **Cloud execution reliability** - fail-closed staging, immutable release identity, output commit protocol, retries/preemption, callbacks, observability, and budgeted canaries. The detailed cloud design lives in the website repository.

The catalog and cloud foundation may be implemented in parallel, but catalog release requires both.

## 4. Immutable reconciliation ledger

Before implementation changes, generate a baseline ledger from these independent sources:

- Original Galaxy-parity monolith commit `44c247986f3bcfe8f8d93d0d719a53e4853d0437`, which supplies origin/blame provenance for 551 IDs.
- Immediate category split commit `a346ded79659d5a10e3056d7cf8ea2bf482606a7`.
- Latest pre-one-tool behavior snapshot `4092ad63a8f60e5b8080711a66428ba191bdc7b7`, which exposes all 943 nonempty IDs after later fixes.
- Committed one-tool split work-in-progress `ce54d30e4fd07cf26809d99d25bdb267d121e525`.
- Current dirty repair tree, whose class ASTs match the committed split but whose import/index repairs restore discovery of all 943 IDs.

The ledger is generated from source AST and git objects, not from existing generated metadata. Each row contains:

```yaml
node_id: samtools_sort
legacy:
  original_commit: <sha>
  original_module: <module>
  original_class: <class>
  original_source_sha256: <digest>
  current_module: <module>
  current_class: <class>
  current_source_sha256: <digest>
identity:
  aliases: []
  template_references: []
  workflow_references: []
rebuild:
  family: samtools
  operation: sort
  status: inventoried
  disposition: rebuild
  contract_version: null
  evidence_record: null
```

The compiler fails unless every baseline ID has exactly one disposition:

- `released`
- `quarantined`
- `byol`
- `deprecated_tombstone`

No generated catalog may seed itself from a previous generated catalog. Generation always starts empty and fails on duplicate IDs, import failures, missing ledger rows, stale rows, or unaccounted source definitions.

## 5. Physical package organization

Executable code follows upstream ownership and runtime, not UI placement:

```text
bionodulo/nodes/
  contract/
    model.py
    artifacts.py
    parameters.py
    compatibility.py
    execution.py
    environments.py
    evidence.py
    maturity.py
    compiler.py

  catalog/
    core/
      artifacts/
      input/
      flow/
      values/
    libraries/
      biopython/
      pandas/
      scanpy/
    providers/
      ncbi/
      uniprot/
      alphafold_db/
    tools/
      samtools/
        tool.py
        common.py
        view.py
        sort.py
        index.py
        evidence.authoring.json
        fixtures/
      bedtools/
        tool.py
        common.py
        intersect.py
        closest.py
        evidence.authoring.json
        fixtures/

  generated/
    baseline-ledger.json
    catalog.lock.json
    catalog.runtime.json
    catalog.ui.json
    compatibility.json
    node-index.json
    migrations.json

  legacy/
    adapter.py
```

Rules:

- One operation per focused module unless two operations are inseparable parts of one public contract.
- Shared code is explicit in `tool.py` or `common.py`; generated files never copy a preamble.
- Package `__init__.py` files are empty or contain only a declared registration list. They do not eagerly re-export operations.
- Relative resources live inside the owning package and are loaded with `importlib.resources`.
- UI location is metadata (`palette_path`, `domain_tags`, `operation_kind`) and never determines Python location.
- Node discovery uses a generated static index and imports only the requested implementation.

## 6. Canonical typed contract

Use Pydantic v2, already a project dependency, for strict models and deterministic JSON schema. Unknown fields are rejected. Mutable default containers are forbidden.

```text
NodeSpec
  identity
    node_id
    contract_version
    implementation_version
    tool_version
    aliases
    port_aliases
    workflow_migrations

  presentation
    display_name
    description
    palette_path
    domain_tags
    operation_kind
    tool_family/provider

  inputs
    artifact_ports
    value_ports
    parameters
    secrets

  outputs
    artifact/value type
    cardinality
    required/optional/conditional state
    collection strategy
    content validation

  execution
    runtime kind
    typed execution-plan builder
    environment lock
    resources and architecture
    network policy
    timeout/retry/checkpoint policy

  evidence
    authoritative claims
    source version/commit
    CLI help fingerprint
    verification records

  lifecycle
    access class
    maturity evidence
    deprecation/tombstone state
```

### 6.1 Artifact and value separation

Artifact ports represent materialized workflow data. Parameters represent scalar configuration. Value ports represent connectable scalar data when a workflow genuinely needs dynamic values. A parameter does not become a data port merely because its historical type string is not `STRING`.

Artifact type and cardinality are separate:

```yaml
type: sequence.fastq
cardinality: many
container: file
compression: [none, gzip]
```

This replaces encodings such as `FASTQ_LIST`. Cardinalities are:

- `one`
- `optional_one`
- `many`
- `nonempty_many`
- Explicit structured group types for paired reads or coordinated collections

### 6.2 Compatibility

Compatibility is directional and structural. It is compiled once for backend and frontend consumers. It may consider canonical artifact type, accepted variants, compression, container kind, and cardinality. It never uses string-family prefixes.

Examples:

- `alignment.bam` may satisfy a generic file port that explicitly accepts any file.
- A many-valued FASTQ port cannot satisfy a single BAM port.
- TSV and CSV are not interchangeable unless the target contract explicitly accepts both.
- A directory is not a string path widget.

### 6.3 Parameter semantics

Parameters use real primitive or enum types, `None` for absence, explicit defaults, allowed values, bounds, pattern/length constraints, and conditional visibility. Empty strings never represent missing integers, floats, or booleans. Boolean values are not accepted as integers.

Each CLI parameter has an explicit binding model for flag name, flag style, repeat behavior, positional order, omission behavior, delimiter, and version applicability. Complex tools use a typed plan-builder function instead of unsafe shell-string templates.

### 6.4 Output semantics

Output collection happens before output validation:

```text
validate inputs
  -> materialize artifacts
  -> build execution plan
  -> execute
  -> collect/rename/normalize outputs
  -> validate keys, cardinality, existence, format, and content
  -> publish
```

Collection strategies include:

- Exact path
- Tool-derived/prefix-derived path
- Glob with explicit cardinality
- Stdout capture
- Directory tree
- Conditional output
- Parser-produced in-memory value

This ordering removes the current post-`super().run()` failure class.

## 7. Execution architecture

Node implementations return an `ExecutionPlan`; they do not own workflow storage or cloud behavior.

Execution plan variants:

- `ArgvPlan` - default external process, no shell.
- `PipelinePlan` - explicit processes and pipes.
- `ScriptPlan` - generated script with declared interpreter and checked resources.
- `PythonPlan` - in-process callable with pinned import environment.
- `RPlan` - pinned R environment and script contract.
- `HttpPlan` - request, auth reference, rate policy, response schema, and retry policy.
- `ContainerPlan` - immutable image digest and entrypoint.

The runner owns subprocess environment sanitization, secret injection, cancellation, logs, timeout, exit-code handling, preemption signals, output collection, and provenance capture. Runtime-specific behavior is tested independently of tool modules.

Every execution record includes:

- Catalog digest
- Node ID and contract version
- Tool/package/container versions and hashes
- Rendered argv or script digest with secrets redacted
- Input artifact identities
- Output artifact identities and validators
- Cloud/architecture/runtime identity

## 8. Environment and dependency contracts

Environment declarations are first-class and persist in the release manifest. Supported kinds are Pixi/Conda, Python, R, and immutable container. Shell utilities are dependencies only when explicitly invoked.

Requirements:

- Pin tested tool versions or bounded compatible ranges backed by evidence.
- Produce a deterministic lock/digest per platform and architecture.
- Verify every declared executable and import after environment creation.
- Record `--version` and `--help` fingerprints for the tested build.
- Do not infer a node's environment by parsing shell scripts.
- Do not bundle or cache restricted vendor binaries in shared images or R2.
- Persist environment data so a workflow remains reproducible when a Python class is unavailable.

## 9. Authoritative evidence ledger

Every contract claim must point to authoritative evidence. Preferred order:

1. Official versioned manual or API schema.
2. Upstream source at a pinned tag/commit.
3. Installed tool `--help` or runtime behavior from the pinned environment.
4. A maintained package recipe only for packaging details.

Blogs, old wrappers, Galaxy XML, and the legacy BioNodulo implementation are discovery aids, not final authority, unless the upstream project designates them as canonical.

Checked-in `*.authoring.json` files contain plain `title`, `description`, and
`statement` strings. They never contain their own content digest. Authoring
files are strict duplicate-free UTF-8 JSON; YAML aliases, merges, tags,
non-finite numbers, and duplicate keys have no accepted interpretation. At any
depth they reject the compiler-owned fields `provenance`, `catalog_path`,
`catalog_content_sha256`, and `field_pointer`; those words remain legal inside
plain prose. The trusted compiler reopens each authoring file, resolves each
JSON pointer from those bytes, hashes the exact source bytes, and injects
provenance into the generated schema-version-2 record. A compiled record
contains only provenance-bound prose or structured, content-addressed captures:

```yaml
schema_version: 2
tool_id: samtools
tool_version: 1.23.1
sources:
  - source_id: samtools-index-manual
    tool_id: samtools
    kind: official_manual
    tool_version: 1.23.1
    url: https://www.htslib.org/doc/samtools-index.html
    content_sha256: sha256:<captured-document-digest>
    content_format: text
    title:
      value: Samtools index manual
      provenance:
        origin: catalog_author
        catalog_path: bionodulo/nodes/catalog/tools/samtools/evidence.authoring.json
        catalog_content_sha256: sha256:<exact-authoring-source-bytes-digest>
        field_pointer: /sources/0/title
    description:
      value: Authoritative index behavior for the pinned Samtools release.
      provenance:
        origin: catalog_author
        catalog_path: bionodulo/nodes/catalog/tools/samtools/evidence.authoring.json
        catalog_content_sha256: sha256:<exact-authoring-source-bytes-digest>
        field_pointer: /sources/0/description
    documentation_proof:
      proof_kind: declared_metadata
      tool_id: samtools
      tool_version: 1.23.1
      source_url: https://www.htslib.org/doc/samtools-index.html
      source_content_sha256: sha256:<captured-document-digest>
      locator:
        kind: byte_range
        start_byte: 120
        end_byte_exclusive: 164
      proof_content_sha256: sha256:<selected-proof-digest>
    retrieved_at: 2026-07-15
claims:
  - claim_id: samtools-index-default-output
    contract_pointer: /outputs/index/collector
    source_id: samtools-index-manual
    source_content_sha256: sha256:<captured-document-digest>
    locator:
      kind: byte_range
      start_byte: 912
      end_byte_exclusive: 1004
    excerpt_sha256: sha256:<selected-claim-digest>
    contract_value_sha256: sha256:<canonical-contract-value-digest>
    statement:
      value: Default BAM index is input.bam.bai unless -o is supplied.
      provenance:
        origin: catalog_author
        catalog_path: bionodulo/nodes/catalog/tools/samtools/evidence.authoring.json
        catalog_content_sha256: sha256:<exact-authoring-source-bytes-digest>
        field_pointer: /claims/0/statement
verifications:
  - evidence_id: samtools-index-smoke-linux-amd64
    tool_id: samtools
    tool_version: 1.23.1
    kind: tool_smoke
    outcome: passed
    test_id: samtools-index-tiny-bam-v1
    result_sha256: sha256:<canonical-verifier-report-digest>
    fixture_id: tiny-bam-v1
    fixture_sha256: sha256:<fixture-digest>
    environment_sha256: sha256:<environment-lock-digest>
    catalog_sha256: sha256:<catalog-lock-digest>
    platform_sha256: sha256:<platform-digest>
    verified_at: 2026-07-15
    verifier_id: catalog-tool-verifier
    verifier_version: 1.0.0
```

`title`, `description`, and claim `statement` are the only retained prose. Each
is a `RetainedText` value whose provenance identifies one checked-in catalog
blob by repository-relative path, SHA-256 digest, and JSON pointer. Ordinary
technical prose is allowed; it is not scanned for secret-looking words or host
paths. `catalog_author` is the only text origin. Runtime stdout, stderr,
environment values, and filesystem paths have no retained-text representation
and may enter the ledger only as digests or closed result codes.

Every source declares one closed `content_format`: `text`, `json`, or
`source_code`. Byte ranges select exact bytes in all three formats. JSON
pointers are accepted only for `json` and hash the canonical JSON encoding of
the strictly parsed selected value. Symbol locators are accepted only for an
`upstream_source` with `source_code` content and must equal that source's exact
symbol identity. A JSON-pointer documentation proof likewise requires `json`;
documentation byte-range proofs work for every official source format.

All parsed JSON paths are bounded before decoding: exact input is at most 8 MiB
and structural nesting is at most 64 object/array levels. Decoder recursion is a
controlled validation failure. Canonical selected values and compiler-resolved
contract values are independently limited to 64 levels and 1 MiB of output and
reject circular containers. These limits apply before digest comparison, so an
oversized self-consistent digest cannot bypass them.

JSON numbers are parsed as exact decimal tokens, never through binary float and
never through Python's process-wide integer digit limit. A coefficient has at
most 256 digits; both the written exponent and normalized adjusted exponent are
between -4096 and 4096. Canonicalization strips insignificant zeros, maps
negative zero to zero, uses lowercase scientific notation without exponent
expansion, plus signs, or exponent-leading zeros, and deliberately maps `1`,
`1.0`, and `1e0` to the same token `1`. Numerically distinct in-policy decimals
therefore remain distinct. The implementation does not use ambient Decimal
context operations.

This is an information-flow boundary, not proof that a caller is human. The
declarative model retains the immutable provenance; the trusted catalog loader
in Task 9 must reopen every referenced path and verify its exact source-byte
digest, pointer, and selected text before accepting a `NodeSpec`. Arbitrary
`get_node_specs()` factories may declare provenance but cannot attest it: the
compiler ignores self-asserted source content and performs the verification
with compiler-owned bytes. It accepts only Git-tracked authoring paths under
`bionodulo/nodes/catalog/`, rejects generated paths, and opens them without
following symlinks outside that tree. Runtime collectors never receive that
authority.

Official documentation requires a `DocumentationVersionProof` over the exact
captured bytes. The proof repeats the exact tool, version, URL, and source
content digest, identifies proof bytes with a structured byte-range or JSON
pointer, and retains the selected-content digest. Task 9 must invoke proof
content verification for every proof and claim content verification for every
claim, using compiler-owned captured bytes rather than factory-supplied
selections. Both paths recompute the captured-source and selected-content
digests. Task 8 defines an evidence-free deterministic contract projection
containing exactly `identity`, `presentation`, `artifact_inputs`, `value_inputs`,
`parameters`, `secrets`, `outputs`, `environment`, `execution_kind`,
`execution_factory`, and `runtime_binding`. Artifact/value inputs, parameters,
secrets, and outputs are objects keyed by canonical ID and retain every item
field. All object keys and collection items use canonical order; for example,
`/outputs/index/collector` addresses output ID `index` rather than an array
position. `contract_digest()` hashes these exact Task-7 canonical bytes.
`NodeSpec` itself performs no pointer or filesystem resolution. Task 9 resolves
every claim's `contract_pointer` from that projection, passes the exact expected
pointer and resolved JSON value to the claim verifier, and recomputes
`contract_value_sha256` with the same lossless serializer used for JSON evidence
selections. Missing compiler arguments, pointer disagreement, or digest mismatch
is fatal. Symbol locators remain available for upstream-source claims, but are
not documentation-version proofs because this declarative module has no
source-language symbol resolver. A symbol claim is accepted only when a
compiler-owned, language-aware selector resolves the exact symbol from the
captured bytes. Unsupported languages and missing or ambiguous symbols
quarantine the node and prevent release. URL shape is transport metadata and
never establishes tool ownership or version. If the captured content cannot
prove the pair, the agent must inspect pinned upstream source and record the
exact file/symbol/commit. If behavior remains uncertain, the node stays
quarantined.

All explicit source paths use canonical repository-relative POSIX syntax. URLs
use canonical HTTPS parsing. Neither validator searches arbitrary path segments
or prose for versions, credentials, or host paths. Existing schema-v1 evidence
is not accepted implicitly: an offline migration must add authored provenance,
structured locators, and content proofs, and must quarantine any record whose
binding cannot be established without a heuristic.

## 10. Access and license classification

Access and resource requirements are independent from technical maturity and
are retained as a unique tuple in the canonical order below:

- `public`
- `public_rate_limited`
- `secret_required`
- `large_reference`
- `gpu_required`
- `byol`
- `service_license`

The tuple must contain at least one access mode. `public` and
`public_rate_limited` are mutually exclusive, and `public` cannot coexist with
`secret_required`, `byol`, or `service_license`; it may coexist with
`large_reference` and `gpu_required`. `secret_required` may coexist with BYOL
or service licensing. Any BYOL or service-license member blocks automatic
release, while GPU and large-reference members remain releasable after their
relevant technical gates pass.

Schema v2 has no manual-approval override artifact. Therefore a maturity record
containing BYOL or service licensing never reports `released`; it remains in
quarantine until a later design adds an auditable approval record and a
production verification path. Out-of-band approval must not mutate or bypass
the computed maturity state.

Task 8 validates secret declarations against this tuple. Any optional secret
requires `public_rate_limited`, `secret_required`, `byol`, or
`service_license`. A required secret requires `secret_required`, `byol`, or
`service_license`, and `secret_required` requires at least one required secret.
Thus account-bound licensed nodes may correctly declare required credentials;
an unclassified `public` node may not silently accept them.

Known restricted or account-bound families remain quarantined until terms and runtime provisioning are validated. This includes ANNOVAR, Allegro, Cell Ranger/Space Ranger, Dorado/Rerio branches, MSFragger/FragPipe, DIA-NN, MaxQuant, SIRIUS service-backed features, and KEGG service-provider use.

BYOL assets are account-scoped, never included in a shared worker image, and never placed in the global reference cache.

## 11. Computed maturity gates

Maturity is derived from retained test evidence, not a boolean written by an author.

Verification and gate records retain only closed kinds, pass/fail outcomes,
failure codes, canonical report/artifact digests, dates, and verifier identity.
Every passed or failed gate has one or more sorted `verification_digests`. Raw
stdout, stderr, environment values, host paths, and author-written summaries or
failure reasons are not maturity data. The UI derives stable labels and failure
messages from the gate and failure-code enums; generated text is neither
serialized nor part of the maturity digest. Each gate declares one required
verification kind;
Task 8 resolves every assessment digest to a retained report for the same tool,
requires that report to have the declared kind, and requires its outcome and
failure code to agree with the assessment. Multiple same-kind reports support
platform-specific verification without weakening the binding.

Verification context is kind-specific and closed:

| Verification kind | Required context | Additional allowed context |
| --- | --- | --- |
| `inventory`, `evidence_coverage`, `contract_compile` | `catalog_sha256` | none |
| `command_fixture` | `fixture_id`, `fixture_sha256`, `environment_sha256`, `catalog_sha256` | `platform_sha256` |
| `environment_probe` | `environment_sha256`, `catalog_sha256`, `platform_sha256` | none |
| `tool_smoke` | `fixture_id`, `fixture_sha256`, `environment_sha256`, `catalog_sha256`, `platform_sha256` | none |
| `cloud_run`, `workflow_run` | `fixture_id`, `fixture_sha256`, `environment_sha256`, `catalog_sha256`, `platform_sha256`, `release_sha256` | none |

Fields outside the row are rejected, and fixture ID/digest are always supplied
together. This prevents a report for one catalog, environment, fixture,
platform, or release from satisfying a gate for another.

1. `inventoried` - baseline ID and disposition recorded.
2. `evidence_verified` - every contract claim has authoritative evidence.
3. `contract_verified` - typed schema and compatibility compile without warnings.
4. `command_verified` - valid/invalid inputs, argv/script, and output collection fixtures pass.
5. `environment_verified` - locked environment resolves and all dependencies identify correctly.
6. `tool_smoke_verified` - real pinned tool runs a tiny fixture and outputs pass content checks.
7. `cloud_verified` - supported worker/cloud/architecture completes staging through committed outputs.
8. `workflow_verified` - at least one canonical producer-consumer workflow passes frontend, backend, executor, and cloud validation.
9. `released` - compiler includes the node in the normal palette.

The internal quarantine lab may expose earlier states with the exact failed gate. Production execution rejects non-released nodes even if a client constructs a raw workflow payload.

## 12. Compiler outputs and release identity

The catalog compiler emits all consumer artifacts in one deterministic operation:

- Lazy Python node index
- Runtime catalog and environment locks
- Frontend node metadata and generated TypeScript types
- Directional compatibility table
- Workflow migration table
- Evidence and maturity report
- Catalog lock with content digest

The compiler starts empty and treats every warning as a failure. Generated artifacts are never manually edited.

The catalog compiler emits a canonical pre-build `contract.json`. Its `contract_id` is the SHA-256 of app/website source identities, protocol versions, catalog, compatibility, templates, evidence ledger, fixture set, and exact per-platform environment-lock digests. Every built artifact embeds this contract ID.

Within the catalog, each node also has Task 8's deterministic evidence-free
contract projection. It contains exactly identity, presentation, the five
ID-keyed input/parameter/secret/output collections, environment, execution kind,
execution factory, and runtime binding. Complete items and keys are canonically
ordered. Those stable keyed-map pointers and Task-7 canonical bytes are the
authority for `EvidenceClaim.contract_pointer`, `contract_value_sha256`, and the
node's `contract_digest`. During compilation, Task 9 resolves each claim pointer
from this projection with the bounded lossless JSON rules in Section 9 and
supplies the selected value to claim verification. A raw `NodeSpec` tuple index,
factory-supplied Python value, or factory-supplied digest is never a substitute.

After artifacts are built, the release orchestrator emits a signed `bundle.json`. Its `bundle_id` is the SHA-256 of the contract ID plus exact SPA, Lambda, worker-platform, dispatch-package, Vercel-artifact, SBOM, and provenance digests. This two-stage identity avoids circular hashing: images embed the contract ID, while the post-build bundle records image digests. Promotion always moves the already-built bundle and never rebuilds artifacts.

The editor SPA, editor Lambda, website validator, workflow/template bundle, and worker image must advertise the same contract ID. Run submission and worker startup reject mismatches instead of relying on whichever `main` revision was built most recently.

## 13. Template reconstruction

Templates are rebuilt against stable port IDs and pinned catalog digests. A template cannot be released unless:

- Every referenced node is released.
- Every edge resolves exact source and target port IDs.
- Cardinality and artifact compatibility pass the canonical compiler.
- Parameters pass typed validation.
- A deterministic fixture run passes locally where lightweight.
- The full template or a documented minimal equivalent passes the cloud gate.
- Expected outputs have content-level assertions, not existence-only checks.

Templates are prioritized by complete user workflows rather than node count: core input/artifact handling, FASTQ QC, alignment/variant basics, RNA-seq, assembly, phylogeny, metagenomics, single-cell/spatial, proteomics/metabolomics, and specialized/vendor lanes.

## 14. Agent-swarm operating model

Shared foundation files have one integration owner. Family agents never edit compiler models, generated artifacts, or broad package facades.

For each upstream family:

1. Evidence agent maps official docs/source and versions.
2. Contract agent writes typed specs and failing contract/command tests.
3. Implementation agent implements plans and output collectors.
4. Verification agent independently compares implementation to evidence and runs cloud fixtures.
5. Integration owner accepts the family and regenerates artifacts once.

Work assignment is stored in a machine-readable migration ledger. Each family has exclusive paths, fixture prefixes, cloud job labels, and R2 test prefixes. This prevents the shared-file collisions that characterized the intern split.

## 15. Testing strategy for the slow local host

Run locally:

- AST reconciliation and catalog compilation
- Pydantic contract tests
- Frontend/backend compatibility parity
- Command and script snapshots
- Fake-runner output collection tests
- Mocked HTTP/API tests
- Pure-Python tests with tiny fixtures

Run on disposable cloud workers:

- Environment resolution and package installation
- Real executables and language packages
- Heavy CPU/RAM/GPU tools
- Reference-backed tools
- Cross-architecture tests
- Full website-to-worker workflow canaries

Cloud tests use tiny upstream or purpose-built fixtures, immutable worker digests, strict timeouts, unique R2 prefixes, hard spend caps, and guaranteed teardown. Public CPU, GPU/high-memory, external API, and BYOL tests use separate lanes.

## 16. Big-bang cutover

Development happens on isolated branches/worktrees while the existing app remains untouched.

Cutover prerequisites:

- All 943 IDs reconciled with no duplicates or ghosts.
- Every release-eligible public node reaches `released`; all others have explicit quarantine/BYOL/tombstone reasons.
- All generated artifacts share one catalog digest.
- All released templates pass exact validation and cloud tests.
- Website input staging and output commit protocols are fail-closed.
- The two dependency-free canaries pass on AWS, followed by capability-gated OCI canaries.
- Credential rotation and minimum file permissions are complete.
- Rollback artifacts and database/workflow migrations are rehearsed.

Cutover steps:

1. Freeze workflow/template writes briefly.
2. Back up current catalog artifacts and workflow definitions.
3. Deploy the version-aligned editor, Lambda, website, worker images, and dispatch contract.
4. Run dependency-free and file-staging canaries.
5. Run representative released templates.
6. Enable the new palette and unfreeze writes.
7. Observe a soak window before deleting legacy code.

Rollback restores the previous coordinated release and catalog digest. New workflows are not accepted by an old release unless an explicit reverse migration exists.

## 17. Completion criteria

The rebuild is complete when:

- The reconciliation ledger accounts for all 943 stable IDs.
- No normal-palette node depends on the legacy adapter.
- No catalog compiler warnings, skipped imports, unknown types, lossy frontend conversions, or unvalidated template edges remain.
- Released nodes have authoritative evidence, deterministic environments, command/output fixtures, and real-tool cloud evidence.
- Every released template completes through the website and returns validated downloadable artifacts.
- Cloud completion is impossible after failed staging, execution, validation, or upload.
- Editor, Lambda, website, worker, templates, and catalog all share one immutable release digest.
- Restricted/unverified nodes remain clearly quarantined rather than pretending to work.
- The old extractor and split tree are removed only after the final reconciliation report passes.

## 18. Explicit non-goals

- Preserving current Python module paths or UI categories.
- Releasing all vendor-restricted nodes without appropriate licensing.
- Downloading large tools or datasets to the Codex host.
- Adding per-cloud object-store mirrors before measurements show R2 is a material bottleneck.
- Treating static lint success or output-file existence as proof of biological correctness.
