# Samtools First-Wave Canary

Status: quarantined. This canary is a no-execution local contract plus a
disposable-worker gate. The cloud gate was not run for this change.

## Inputs and Contract

The public, synthetic fixture is:

- `tests/fixtures/samtools_first_wave/tiny.sam`
- `tests/fixtures/samtools_first_wave/workflow.json`

The SAM has two interleaved pairs at the same coordinates. `pair_high` has
`I` qualities and `pair_low` has `5` qualities. There are no read-name
suffixes or private data. `fixmate -m` supplies the `MC` and `ms` tags required
by `markdup`; the Samtools 1.23.1 documentation says that `ms` is used to
select the reads to keep. The markdup documentation and `bam_markdup.c` state
that equal alignment positions and orientation keep the highest base-quality
read, so `pair_high` is the deterministic original and `pair_low` is the
duplicate pair.

The fixture and workflow hashes in this checkout are:

```text
tiny.sam    0b621dee8e14e8ebf5e52772c3c6695b47c312e5190b52591644ce872ee422c7
workflow.json 86407589c10492da463a8fd2ae9cfcadb6e53c3f83d5c797f44c9eda8b63739a
```

The focused test asserts these SHA-256 values against the raw file bytes and
also checks that the same values remain documented here.

Do not regenerate or normalize the SAM with a tool before hashing it. The
workflow parameter must be an absolute path at execution time. Relative paths
are intentionally not accepted as a substitute because the dry-run resolver
does not absolutize them.

## Local Structural Gate

Activate the project's Python environment using the repository's supported
environment manager, then run from the repository root. This command reads
JSON, creates an isolated node registry, validates the graph, and plans
commands only; it does not call Samtools or `PREPARE_EXECUTION`:

```bash
python -m pytest -q tests/nodes/samtools/test_canary_fixture.py
```

The focused test must report four passing tests. It asserts:

- the exact raw-byte fixture and workflow SHA-256 values;
- repository `text eol=lf` attributes for both fixture files;
- the exact seven-node order `view_001`, `collate_001`, `fixmate_001`,
  `sort_001`, `markdup_001`, `index_001`, `flagstat_001`;
- the six canonical ports in `workflow.json`;
- token-list commands with `shell == false` and `will_execute == false`;
- `samtools fixmate ... -m ...`;
- `index_001` outputs ending in `indexed_bam.bam` and
  `indexed_bam.bam.bai`; and
- `flagstat_001` consuming `index_001.indexed_bam`.

## Future Canonical Baseline Contract

The focused test does not use or assert the identity below. It uses a pytest
`tmp_path` workspace, run ID `samtools-first-wave-canary`, and the fixture's
absolute path in the current checkout; it asserts only stable output suffixes.
The following values are a future local/worker execution contract once a
supported launcher can enforce them:

```text
workspace: /tmp/bionodulo-samtools-first-wave-canary
run id:   samtools-first-wave-canary-v1
parameter tiny_sam: /tmp/bionodulo-samtools-first-wave-canary/input/tiny.sam
```

The corresponding future output paths are:

```text
/tmp/bionodulo-samtools-first-wave-canary/runs/samtools-first-wave-canary-v1/index_001/samtools_index/indexed_bam.bam
/tmp/bionodulo-samtools-first-wave-canary/runs/samtools-first-wave-canary-v1/index_001/samtools_index/indexed_bam.bam.bai
/tmp/bionodulo-samtools-first-wave-canary/runs/samtools-first-wave-canary-v1/markdup_001/samtools_markdup/duplicate_stats.stats.txt
/tmp/bionodulo-samtools-first-wave-canary/runs/samtools-first-wave-canary-v1/flagstat_001/samtools_flagstat/stats.stats.txt
```

Path equality is necessary for BAM/BAI comparison because Samtools `@PG` command
lines and the markdup `COMMAND` statistic contain paths. It is not sufficient
for the text artifacts. `WorkflowExecutor` defaults `embed_provenance` to true
and appends a provenance block containing a fresh UTC `embedded_at` value to
both `duplicate_stats.stats.txt` and `stats.stats.txt` after execution. The
source-remediated cloud worker now passes an explicit provenance option that
defaults to `embed_provenance=false`; a future local baseline must select the
same mode. No execution has verified raw hash equality yet.

For an output-hash gate, record the chosen provenance mode. Download outputs
only after worker finalization and hash those exact finalized bytes;
pre-embedding artifact metadata, planned paths, and object-listing metadata are
not hash evidence. If normalization is used instead, preserve each finalized
raw hash and separately record the normalized digest.

This dry-run is not a local execution baseline. After the path, provenance,
and environment-lock prerequisites exist, execute locally under this canonical
identity and record all finalized artifact evidence in the worker record.

## Historical Cloud Gap Audit (`dc188ee05b1dec99e12be61caa3bf9c2f94fb406`)

Set `BIONODULO_WEBSITE_ROOT` to a local checkout of the website/worker repository
at commit `dc188ee05b1dec99e12be61caa3bf9c2f94fb406`. All website paths below
are relative to `$BIONODULO_WEBSITE_ROOT`. This commit pins the historical gap
claims below. They describe that exact checkout, not the later source-level
remediation. The fixed source must still be deployed and recorded as the actual
worker-source commit for a future run.

The existing authenticated editor/website topology is:

1. `POST /api/workflows` creates an empty website workflow row.
   `PUT /api/workflows/{id}` accepts this raw fixture inside the envelope
   `{"definition": <workflow.json>, ...}`. The website route reads
   `body.definition`, not a top-level raw workflow.
   `saveCloudWorkflow` in `web/src/api/website.ts` preserves `nodes`, `edges`,
   `outputs`, `parameters`, `version`, and `app` in that field.
2. `POST /api/runs` accepts the resulting `workflowId` and approved compute
   selection. The request schema is implemented by
   `$BIONODULO_WEBSITE_ROOT/apps/web/app/api/runs/route.ts`; there is no separate
   `parameters` field.
3. `$BIONODULO_WEBSITE_ROOT/apps/web/lib/jobs/dispatch.ts` resolves only the
   `skypilot` backend and posts the built task to the dispatch service's
   `/jobs` endpoint. The worker implementation is
   `$BIONODULO_WEBSITE_ROOT/infrastructure/worker/run_worker.py`.
4. The editor polls `GET /api/runs/{runId}` for status; this route supports the
   authenticated bearer path. The cookie-only output endpoint lists only
   object key, name, size, content type, and a short-lived presigned URL; it
   does not return SHA-256 or provenance.

This checkout contains only the client-side half of this cloud flow; its Python
backend is the local queue. The website root above contains the website runner
and worker. The public submit request accepts `workflowId`, compute selection,
and optional `inputs`. `inputs` can replace a matching `parameters[].value`,
but it does not rewrite a local path to the worker materialization path.

Current file staging is not sufficient for this canary at two separate layers.
First, `web/src/utils/workflowFiles.ts` scans selected node parameter keys for
literal local paths. This fixture stores the required `{{tiny_sam}}`
placeholder under `alignment`; its workflow parameter has no default or value.
The local dry-run test injects the absolute fixture path through
`options.parameters`, but the cloud hook drops that map. A raw website
PUT/POST therefore reaches the worker without a `tiny_sam` value unless an
unsupported `inputs` override is used. Even a supplied local absolute path is
not rewritten or materialized for the worker. Second, when other files are
uploaded, the editor sends them inside nested `inputs.files`, while the staging
scan in `$BIONODULO_WEBSITE_ROOT/apps/web/lib/jobs/input-files.ts` checks only
top-level `inputs` values for upload keys.

The cloud branch in `web/src/hooks/workflow/useWorkflow.ts` does not forward
its runtime `options.parameters`; it calls `submitCloudRun` with only compute
and `options.inputs`. A manual `inputs.tiny_sam` can mutate the matching
`parameters[].value`, but that is not the supported editor flow and it still
does not rewrite an upload key or local path. The worker downloads staged
objects below `/tmp/workspace/input`, but no automatic rewrite binds the
parameter to that downloaded file. Supplying a manual presign payload or
internal top-level upload-key shape must not be used as release evidence.

The editor also catches a `saveCloudWorkflow` error and proceeds to submit the
workflow ID. That behavior is not fail-closed evidence that the exact fixture
definition reached the worker.

The website database also creates the run UUID.
`$BIONODULO_WEBSITE_ROOT/infrastructure/worker/run_worker.py` uses
`/tmp/workspace/runs/<generated-run-uuid>`, so the public API cannot enforce the
fixed workspace and run path needed for raw hash equality. It also cannot
select or attest an image digest, provider/region/architecture, or worker
identity. The local app's `POST /runs` accepts `parameters`, but that endpoint
uses the local queue and is not a cloud-worker launch command.

Therefore there is currently **no single supported command that can launch
this canonical fixture with its fixed absolute parameter and reproducible raw
hash identity**. Do not replace this gap with an undocumented `curl`, a direct
dispatch/SkyPilot call, an obsolete AWS Batch call, or credentials in this
repository. The prerequisite for the remote gate is a documented
website/worker submission interface that can:

- persist this exact fixture workflow at the commit under test;
- materialize `tiny.sam` and rewrite/pass `tiny_sam` as the fixed absolute
  worker path before execution;
- select the fixed workspace and run ID above (or provide an equivalent path
  normalization that makes `@PG` and markdup paths identical);
- pin and report the worker image digest, provider, NA region, architecture,
  worker identity, environment manifest key, committed lock digest, and
  resolved package builds; and
- return per-node statuses, output paths, byte sizes, SHA-256/provenance,
  timing, and cost.

Do not submit any remote job until the immutable worker image digest is
attested to contain both the BioNodulo app commit recorded for this run and the
audited website worker source. The worker image build excludes
`tests/`, so containing the app commit does not make `tiny.sam` available; the
fixture still needs an explicit, verified staging path.

For this canary, the future disposable target must be an x86_64 worker in AWS
`us-east-1`: the generated workflow Pixi manifest currently declares only
`linux-64`. Pin `SKYPILOT_CLOUD=aws` and `SKYPILOT_REGION=us-east-1`; require
`SKYPILOT_MULTI_CLOUD` to be unset or `0`; and require `WORKER_ARCH`,
`SKYPILOT_ANY_REGIONS`, and `SKYPILOT_POOL` to be unset. An any-region list
overrides a pinned region, while a pool routes to pre-provisioned capacity and
defeats disposable per-run teardown. Do not use the small/micro Graviton route
for this gate. Before submission, verify deployment of the published
`WORKER_IMAGE`, `JOB_BACKEND=skypilot`, public callback URL, callback secret,
SkyPilot dispatch URL/token, and required object-store configuration. OCI
additionally requires its separate published worker image and is outside this
NA gate.

`$BIONODULO_WEBSITE_ROOT/infrastructure/dispatch/README.md` still marks
dispatch-host deployment, worker-image publication/R2 smoke testing, and
worker callback reachability as pending. Those boxes are repository evidence,
not a live-environment check; verify all three deployments before a disposable
canary is submitted. The cookie-only cancel endpoint calls `sky.jobs.cancel`;
there is no checked-in controller or object-store cleanup command, and cancel
is not proof that the controller, VM, workspace, and temporary objects were
torn down. Verify those resources separately in the evidence record.

## Historical Environment Reproducibility Blocker

`40db091121c94941` is only the environment manifest key derived from the
normalized constraint set `samtools = "1.23.1"`. It is not a digest of resolved
packages and must not be reported as an installed-environment identity.

The canary workflow environment currently has no shared committed lock. The
local environment flow may solve a workspace-local `pixi.lock`, while
`$BIONODULO_WEBSITE_ROOT/infrastructure/worker/run_worker.py` generates the
manifest and invokes `pixi install` directly, explicitly bypassing the app's
separate lock step. Separate solves under the same manifest key can select
different HTSlib or transitive builds and package artifacts.

Before execution evidence is admissible, local and cloud must consume one
committed canary-workflow `pixi.lock` without re-solving. Record the exact lock
bytes' SHA-256 and the selected `linux-64` package records. Those records must
include Samtools, HTSlib, and every transitive package's name, version, build
identifier/build number, immutable package URL, and package hash. The same lock
digest and resolved records must be verified on both machines.

These were blockers at the historical website commit above. The following
section records their source-level remediation; deployment and execution
evidence are still absent.

## Source-Level Remediation (Undeployed)

The application-side remediation is committed at:

- `1d280cdae25de8473851d9b8ea69a5adecf7b3f1` — explicit reference sidecars and
  repaired official variant/WGS DAGs;
- `185c67887199dbdf79a8d04c6883c4999396eb51` — committed Pixi lock plus local
  installer and client cloud-handoff fixes.

This wave rebuilds one additional stable node, `samtools_faidx`, for a
cumulative `8/943`. The GATK HaplotypeCaller, FreeBayes, Manta, and Delly edits
repair sidecar contracts in their existing monolithic family and are not counted
as rebuilt nodes.

Pinned node-contract authorities for this wave are:

- Samtools `1.23.1`: `6efb9b6da35224cf804921dedecf9fb8f411365d`;
- GATK `4.6.2.0`: `76edc75c26504da94bbaee66584e107e76ee15de`;
- FreeBayes `1.3.10`: `b0d8efd9fa7f6612c883ec5ff79e4d17a0c29993`;
- Manta `1.6.0`: `ab9f5502985a29ec74cfafb4963179b9cc185e55`;
- Delly `1.2.6`: `e6246dbb18b7f6df2b7b381d542cdeaea6be8c82`.

The website/worker remediation is committed at:

- `e43ed6ceb179954c395a7618b26b8693de0da0d9` — canonical runtime parameters and
  uploaded-file manifest, worker path rewriting, locked environment install,
  x86 routing, immutable identity, durable output attestation, lifecycle CAS,
  cleanup, and SkyPilot dispatch compatibility.

That website commit is tested against SkyPilot `0.12.3.post1`, upstream release
commit `e60704b3e0174ff0461fdf7c219b2bbdeac7ee41`. The committed dispatch
configuration uses `jobs.controller.resources.autostop` with
`idle_minutes: 5` and `down: true`.

The remediated source now provides:

- runtime `parameters` preserved from the editor through `POST /api/runs` and
  into `WorkflowExecutor.options.parameters`;
- one canonical `inputs.files[originalPath] = uploadKey` contract, fail-closed
  staging, bounded manifest/object validation, and exact recursive path rewrite
  after worker download;
- fail-closed workflow persistence and explicit rejection of unsupported cloud
  selected-node, resume, environment-override, force-node, and no-cache modes;
- `linux-64` routing that cannot select ARM;
- full app/website Git identities and digest-pinned worker images required at
  submission;
- provenance defaulting to disabled for cloud execution;
- `run_attestation.json` uploaded last, only after artifact upload and workspace
  cleanup, with source, worker, environment, artifact-size, and SHA-256 evidence;
- reconciliation recovery from that exact run-owned attestation when a durable
  completion callback is lost;
- atomic final billing/status metadata, stale-progress and duplicate-fallback
  protection, absolute runtime deadlines across SkyPilot recoveries, and
  idempotent job/controller/temporary-object cleanup paths.

The shared Samtools environment bundle is:

```text
path: bionodulo/environments/locks/40db091121c94941/
pixi.lock SHA-256: da58ebe2f489d3d740f23c302e9495ab23068491bad714f605438a92fb8afaa4
Samtools: 1.23.1 build ha83d96e_0
HTSlib: 1.23.1 build h633afcb_0
platform: linux-64
```

Both local installation paths and the cloud worker materialize this committed
manifest/lock pair, skip `pixi lock`, invoke `pixi install --locked`, and record
the lock digest marker. A workflow with external packages and no committed lock
fails closed in the cloud.

This is source evidence only. The fixed website/worker commit is not deployed,
no immutable worker image containing these commits has been attested, no real
Samtools process has run, and no local or cloud output-artifact hashes exist. The
browser upload path also still uses a single presigned PUT with a 5 GiB limit;
multipart upload remains required for WGS-scale BAMs even though worker staging
is bounded at 1 TiB per object and 4 TiB total.

```text
Real local Samtools execution: NOT RUN
Disposable cloud canary: NOT RUN
Fixed website deployment: NOT RUN
Credentials/API keys used: NO
All 943 nodes quarantined/evidence-pending: YES
Release-ready: NO
```

## Disposable NA Worker Record

Complete every field for a real run. Leave `NOT RUN` rather than guessing.

```text
BioNodulo fixture/first-wave commit: 2316c3ca54326229fe0aa236868369cfd442bfbd
BioNodulo reference-sidecar commit: 1d280cdae25de8473851d9b8ea69a5adecf7b3f1
BioNodulo lock/client-handoff commit: 185c67887199dbdf79a8d04c6883c4999396eb51
Audited current-gap website commit: dc188ee05b1dec99e12be61caa3bf9c2f94fb406
Fixed website/worker source commit (not deployed): e43ed6ceb179954c395a7618b26b8693de0da0d9
Actually deployed fixed worker-source commit and re-audit reference: NOT RUN
Fixture SHA-256 (tiny.sam):
Workflow SHA-256 (workflow.json):
Exact submission command or authenticated UI/API request:
Absolute tiny_sam parameter:
Canonical workspace:
Canonical run ID:
Worker run path:
Worker image digest:
Provenance/hash mode (`embed_provenance=false` or normalization ID/version):
Finalization timestamp/status before download:
Provider:
NA region:
Architecture:
Worker name/ID:
SkyPilot routing controls (`CLOUD`, `REGION`, `MULTI_CLOUD`, `WORKER_ARCH`, `ANY_REGIONS`, `POOL`):
Samtools version (`samtools --version`):
HTSlib version:
Environment manifest key (not resolved identity; expected: 40db091121c94941):
Committed canary pixi.lock path:
Committed canary pixi.lock SHA-256:
Resolver/platform and channels:
Resolver/toolchain version:
Resolved Samtools record (version/build/build number/package URL/hash):
Resolved HTSlib record (version/build/build number/package URL/hash):
Resolved transitive package records (name/version/build/build number/URL/hash):

Node statuses (must list all seven):
  view_001:
  collate_001:
  fixmate_001:
  sort_001:
  markdup_001:
  index_001:
  flagstat_001:

Outputs (download finalized bytes; record worker path, downloaded path, bytes, and raw SHA-256):
  indexed_bam:
  bai:
  duplicate_stats:
  flagstat:
Normalized text digests (only when normalization mode is used):
  duplicate_stats:
  flagstat:
Finalized-byte hash tool/command and version:

Semantic checks:
  input reads: 4
  input pairs: 2
  expected duplicate pairs: 1
  expected duplicate reads: 2
  observed markdup read/pair counts:
  observed flagstat total/primary/duplicate/proper-pair counts:

UTC start:
UTC end:
Elapsed seconds:
Cloud cost and billing unit:
Teardown confirmation (workspace, job, and temporary objects removed):
Local baseline result, provenance mode, lock/build records, and finalized-byte hashes:
Reviewer:
Release decision:
```

The expected semantic result is four primary reads in two proper pairs, with
one pair (two reads) marked duplicate and zero optical duplicates. Verify the
actual `markdup` stats and `flagstat` text rather than inferring them from the
fixture. Compare all four raw finalized-byte SHA-256 values to the local
baseline only when provenance is disabled on both runs. Under a deterministic
normalization mode, compare the normalized text digests while retaining the
raw finalized hashes. In either mode, the absolute paths, committed lock
digest, Samtools/HTSlib/transitive build records, and environment manifest key
must match.

## Gate Decision

The first-wave nodes stay quarantined unless the local structural gate passes,
the worker image contains the recorded app and website commits, immutable
image/source attestation and the same committed lock and resolved build records
are verified, exact AWS x86_64 `us-east-1` routing controls are verified, a
disposable North America worker completes all seven statuses, and teardown is
confirmed. With `embed_provenance=false`, all four raw finalized-byte hashes
must match. With deterministic normalization, BAM/BAI raw hashes must match
and both text normalized digests must match; retain the differing raw text
hashes for audit. A reviewer must record `HOLD` when any provenance, lock,
path, build, image/source attestation, routing, teardown, or semantic check is
unavailable or disagrees.

Historical cloud-gap evidence is pinned to `$BIONODULO_WEBSITE_ROOT` at commit
`dc188ee05b1dec99e12be61caa3bf9c2f94fb406`. Source-level remediation is pinned
to `e43ed6ceb179954c395a7618b26b8693de0da0d9`, but remains undeployed and has no
cloud execution evidence. Upstream Samtools source evidence is the public
repository at commit
`6efb9b6da35224cf804921dedecf9fb8f411365d`:

- https://github.com/samtools/samtools/commit/6efb9b6da35224cf804921dedecf9fb8f411365d
- https://github.com/samtools/samtools/blob/6efb9b6da35224cf804921dedecf9fb8f411365d/doc/samtools-fixmate.1
- https://github.com/samtools/samtools/blob/6efb9b6da35224cf804921dedecf9fb8f411365d/doc/samtools-markdup.1
- https://github.com/samtools/samtools/blob/6efb9b6da35224cf804921dedecf9fb8f411365d/bam_mate.c
- https://github.com/samtools/samtools/blob/6efb9b6da35224cf804921dedecf9fb8f411365d/bam_markdup.c
