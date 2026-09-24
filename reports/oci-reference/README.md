# Isolated OCI reference profile audit

This is an opt-in source profile on the `coverage/oci-reference-profile` branch.
It is wired into BioNodulo's discovery, readiness, queue, publication, and
RO-Crate paths only when a data-only catalog is explicitly loaded with
`BIONODULO_ALLOW_UNVERIFIED_CWL=1` and the host has an explicit
`BIONODULO_OCI_RUNTIME_CONFIG`. The released application count remains **52
generated** of **147** pinned CWL descriptors. The one isolated OCI app node
has not been added to that release count.

The complete source denominator is the 147 descriptors at
`bio-cwl-tools@810495363e06f80529633389ec25f8bb6b961844`. The prior ledger
identified 38 descriptors without a machine-readable SoftwareRequirement.
`source-cohort.json` verifies all source SHA-256s against that ledger and finds
30 descriptors with a structurally importable DockerRequirement and 8 with
other profile failures. `all-registry-resolution.json` resolves immutable
registry metadata for all 30 source-only descriptors (15 distinct source
pulls); these are **not** 30 executed tools. Twenty-six resolve directly to a
single platform manifest. Four resolve through multiarchitecture indexes and
remain source-only because the app profile currently requires the source image
digest and execution digest to match. Seventeen source pulls have a declared
numeric release tag, but only **16** also pass the single-manifest app
projection gate without inventing a tool version or unproven index-to-platform
linkage. `ucsc-resolution.json` is the earlier one-descriptor resolution
receipt. Its source pull `biowardrobe2/ucscuserapps:v358` resolved via
read-only Registry API metadata to the linux/amd64 platform manifest
`registry-1.docker.io/biowardrobe2/ucscuserapps@sha256:c20b52737a16a2d554e686ae7d1b448d5d2dc5251d23432ab0a381bac1e61a73`.
Resolution alone proves neither local image availability nor execution.

`generated-app-catalog.json` projects those 16 admissible source contracts
without selecting descriptors by hand. `projection-ledger.json` records all
30 decisions, including the 13 nonnumeric-tag and one multiarchitecture
denials. Loading the generated catalog requires the unverified-CWL opt-in;
the other 15 projected app specs have no execution proof.

The profile retains the original CWL source and its hash. It admits a declared
DockerRequirement only in the OCI opt-in inspection and rewrites only its
`dockerPull` to the verified platform digest for execution. Its runtime
preflight requires pinned cwltool, Docker, and Node.js
binaries, a live daemon of the requested architecture, and the exact local
image digest. The runner uses an exact allowlisted child environment and
invokes cwltool with `--disable-pull` and `--custom-net none`. The Docker CLI
shim adds a unique attempt label to every `docker run`; cleanup checks both
daemon-side labels and cwltool cidfiles, and refuses foreign-labeled IDs.
Failure attempts retain bounded logs and identity receipts. Each attempt goes
to a new evidence directory without overwriting older receipts.

For the chosen CWL v1.0 descriptor, cwltool's pinned `evalResources` defaults
are 1 CPU and 1024 MiB RAM when ResourceRequirement is absent. The strict CPU
and memory flags pass those values to Docker as `--cpus=1` and `--memory=1024m`.
The 180-second parent timeout bounds the direct oracle and its attempt-labeled
container is cleaned up on success or failure. App readiness checks
that static source resource requests fit the configured 2 CPU / 2048 MiB cap;
dynamic resource expressions fail closed. These caps are audit defaults in the
explicit runtime config and can be lowered for other hosts.

The audit uses the dedicated `BioNodulo-PhD-Audit` WSL distro. Official Ubuntu
24.04 Docker packages were installed there, leaving the frozen
/opt/bionodulo-phd/venv unchanged. The runtime receipt records Docker's
executable digest and daemon version alongside the pinned image. No production host,
cloud compute, or Windows Docker Desktop daemon is involved.

The targeted tests cover source Docker declarations, immutable digest checks,
read-only registry resolution, runtime failure on a missing digest or wrong
daemon architecture, child secret-env isolation, resource caps, foreign CID
denial, and independent 2bit decoding. `oracle-try-3/receipt.json` records the
biological result with the standalone runner's attempt-labeled container
cleanup in `finally`; its stderr shows the exact digest, `--net=none`,
`--read-only=true`, `--memory=1024m`, and `--cpus=1`.
The output SHA-256 is
`94534d5910fa143a19f747ad176ff887a780a6f8fbe44af51ca95cf9d0be45fb`.

`app-e2e-auto-try-3.json` records discovery, denied readiness before runtime
configuration, accepted readiness after configuration, a real queued run,
generic input staging/output publication, independent decoding of the
published 2bit file, and source/image/runtime digests on the RO-Crate run
action. It uses the automatically generated 16-spec catalog, records its digest
and the tested source-derived node ID, and checks all 16 nodes are discoverable
as unverified. The app's output and evidence stayed in this isolated worktree.
`app-cancel-try-1.json` records a second, authored CWL descriptor using the
same pinned image to run `sleep`: the app observed a running container by its
attempt label, cancelled the queue run, and verified no labeled container
remained. Its bounded failure receipt was retained. This cancellation
descriptor is a test fixture, not a second upstream coverage accession.
`app-timeout-try-1.json` repeats the same fixture with a six-second app timeout;
the run failed with a timeout receipt and no labeled container remained. The
configured Node.js pin is unconditional because ordinary CWL expressions may
invoke Node without an explicit InlineJavascriptRequirement.

The app profile is still experimental and unverified for release. One
image/tool/fixture has passed biological execution; the remaining projected
specifications need local image availability and independent execution oracles.
The OCI adapter does not use native Conda prefix assertions or claim
bio.tools accessions absent from the source.

## Reproduce the automatic catalog export

From the repository root in an installed development environment, this command
projects every resolved source in the retained report without network requests
or tool selection:

```sh
python -m scripts.audit_oci_reference_coverage \
  --resolution-report reports/oci-reference/all-registry-resolution.json \
  --catalog-output generated-oci-catalog.json \
  --projection-output generated-oci-projection.json
```

Load the catalog with `BIONODULO_DECLARATIVE_CATALOG` and explicit
`BIONODULO_ALLOW_UNVERIFIED_CWL=1`. Execution additionally requires a host-local
`BIONODULO_OCI_RUNTIME_CONFIG` with verified executable paths and digests. The
checked-in `app-runtime.json` describes the audit host; copying it does not
install or prove a runtime on another host. The three opt-in app tests declare
their fixture, catalog, runtime and new evidence destination environment
variables in their source files.

## Validation boundary

On the isolated Linux host, the bounded native regression selection passed
623 tests with two skips, and the focused OCI group passed 21. The subsequent
automatic export audit group passed ten tests. These groups overlap and are
not added together. The final full-catalog app fixture passed once; its receipt
records the exact 16-spec catalog hash and tested generated node ID. Real
cancellation and timeout fixtures passed separately. Changed-file Ruff,
targeted mypy for five new modules, and `git diff --check` passed.

An earlier all-catalog sweep passed 107 tests before detecting stale generated
projections in the older worktree base. Four filesystem tests initially failed
on Windows-mounted temporary storage; all passed in the 623-test rerun using
native Linux `/tmp`. These are not Windows container execution proofs. Earlier
attempts and setup logs remain in the local audit archive; only bounded final
receipts are included here. Full repository GitHub CI remains a separate gate.

After bringing in released main, the catalog compilation checks, export tests,
and generated-catalog app E2E passed together: **13 passed**. This closes the
stale-projection failure above. The final catalog uses canonical LF bytes on
both Windows and Linux; its SHA-256 is
`315a26320c159b8acc8cbb4b1335e5daabe08259167a8ed781523b0f30504bbc`.
The final app receipt records that exact hash. Line endings are preserved by
`.gitattributes`, and the exporter writes canonical bytes independently of host OS.
