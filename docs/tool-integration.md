# Tool integration

The shared integration path turns supported upstream descriptors into typed
nodes. Adding another tool within a supported profile should require descriptor
data and evidence, rather than another tool-specific Python adapter or a new
queue. Existing working adapters remain regression references and retain their
saved-workflow identities.

## Current profiles

| Profile | Purpose | Details |
| --- | --- | --- |
| bio.tools reference toolbox | Discover registry records and save reference nodes; execution is refused | [Reference toolbox](GENERATED_REGISTRY_TOOLBOX.md) |
| Native CWL | Lower a declared subset of CommandLineTool into the ordinary executor | [Native profile](universal-cwl.md) |
| CWL reference engine | Retain upstream CWL and run it through a shared pinned engine and tool environment | [Generated executable integrations](generated-biotools.md) |
| Experimental OCI reference | Exercise an explicitly configured, digest-pinned container profile | [Audit and limits](../reports/oci-reference/README.md) |

These profiles have different admission rules. Registry annotation coverage,
descriptor import, installation and scientific execution are separate results.
None establishes universal executable coverage.

## Design rules

- Extend the existing `NodeSpec`, environment, artifact and evidence models.
  Preserve exact upstream identities, source revisions and content digests.
- Generate controls, ports and runtime bindings from the same descriptor.
  Use shared backends for standards and execution mechanisms.
- Retain unsupported semantics and report a concrete rejection; do not silently
  discard CWL expressions, Galaxy command behavior or output requirements.
- Keep structural invocation evidence separate from biological claims. EDAM
  annotations and exit zero do not prove units, strandedness, reference identity
  or normalization state.
- Require explicit pinned runtime requirements and secret bindings. Descriptors
  must not contain embedded credentials.
- Keep unknown biological state unknown. Incompatible known states must be
  rejected, and model-generated clauses require independent review/evidence.

## Acceptance and further work

A generated executable integration needs discovery through the ordinary API,
a real queued run, retained provenance and independently specified output
checks. Multiple acquired descriptors must compose without tool-name branches.
Changes to a descriptor or runtime invalidate evidence for its previous revision.

Broader acquisition from documentation and command help, empirical container
probes, expert contract review and scientific validation remain separate work.
Evaluate on held-out tools and versions; measure acquisition, installation,
execution, clause correctness, false admissions, abstentions and manual effort.
Report denominators separately for registry records, operations, versions,
platforms and interface classes. Current receipts are indexed in
[reports](../reports/README.md).
