# Cleanup and node-expansion handoff verification

This is the earlier audit snapshot. See the later
[builtin release verification](node-expansion/RELEASE-VERIFICATION-2026-09-29.md)
for repaired blockers, the final candidate count and publication validation.

Verified on 2026-09-29 against the local repositories, retained receipts, configured
MCP launchers, GitHub release assets, and fresh tests. The preceding cleanup report
is an account to verify, not an instruction to delete further material.

## Actual checkout and release state

| Location | Verified state |
| --- | --- |
| `BioNodulo`, main at `ade3b9e5` | 983 built-ins; copied OCI evidence remains untracked |
| `BioNodulo-knowledge-graph`, `feat/tool-knowledge-graph` at `0f93d0ae` | 1,372 built-ins in uncommitted work; 389 additions to the committed 983-node catalog |
| Generated family manifests | 375 generated additions; the other 14 additions are separately implemented nodes |
| Website catalog snapshot | 983 nodes; do not publish 1,372 as the deployed count |
| PR #13 | Open; its completed CI checks apply to `0f93d0ae`, not the uncommitted expansion or these repairs |

No merge, deployment, or commit was performed during this verification. Existing
work was preserved. Counts denote node operations, not distinct bio.tools records.

## Regressions repaired

### Missing EMBOSS file ports

The generator declared every source ACD file in `REQUIRED_PATH_INPUTS`, but exposed
only the first file in `INPUT_TYPES`. A static audit found 68 generated nodes with
unexposed file inputs; 35 included a missing ACD-required file. For example,
`emboss_water` and `emboss_needle` could not receive their required second sequence
through the editor. `emboss_primersearch` had the same problem for its primer input.

Updated `scripts/generate_emboss_nodes.py` and regenerated the 166 generated EMBOSS
modules from retained ACD files. All file ports are exposed; source-required inputs
are mandatory and additional optional files remain optional. The primary input is
still required by the existing node contract. Tests cover all generated file-port
contracts and the rendered arguments for water, needle and primersearch. This does
not certify all conditional ACD semantics or all scientific parameter combinations.

Fresh container execution also passed for water and needle using the generated
commands and two identical 12-base sequences. An independent check found alignment
length 12 and identity 12/12 (100%) in each report. The exact immutable image,
commands, source hashes, fixture hashes and output hashes are retained in
[the two-operation receipt](run-receipts/handoff-2026-09-29-emboss-multi-input/receipt.json).
This is container execution of rendered commands, not an app queue or cloud run.

### Directory outputs

`seqfu_shred` returned no planned output for its declared directory. Three UniKmer
nodes (`grep`, `split`, `tsplit`) appended the node ID to an output directory that
the execution engine had already assigned, so actual output and advertised output
could diverge. A pre-created empty outer directory could pass output verification.

Fixed the generator, the four affected modules, and the SeqFu/UniKmer adapters.
Directory arguments now use the engine-assigned directory; a filename prefix is
placed inside it. Directory output verification requires an actual file beneath
the directory. Regression tests exercise `CommandNode.run` and reject a successful
exit that produces no file. These tests use a fake command executor and do not
establish real SeqFu/UniKmer execution or scientific correctness.

### Stale capabilities and ineffective manifest checks

The handoff claimed that all three inventories contained 1,372 nodes. In fact,
`node_capabilities.json` contained 1,374 and still listed the two deleted vcflib
nodes. Regenerated it to 1,372 and added `export_capabilities.py --check` plus a
live-registry regression test. Checks now detect additions, removals and changes
to GPU/executable requirements rather than testing only a few known entries.

The documented manifest-check command also failed when the app was not installed
or supplied through `PYTHONPATH`: the script did not add the repository root to
its import path. It also silently skipped missing manifest files. The checker now
works from another directory without `PYTHONPATH`, fails for missing manifests or
zero checked nodes, and fails when a generated record has no parameter contract.
Two subprocess tests cover the normal and incomplete-manifest cases.

### Generated-code lint

Full backend/test Ruff found 121 errors: 118 unused local variables and three
unused imports. Corrected the generators' unused path setup for stdout-only nodes,
updated 116 generated modules, and removed the remaining unused bindings/imports.
Full Ruff now passes. This preserves generation as the source of changes rather
than fixing only emitted files.

## Restored evidence and local integrations

### The deleted coverage file was recoverable

The claim that `coverage-e2e-before-normalization-version.json` was permanently
lost was incorrect. Its recycle metadata named the exact original path and its
payload matched the reported size and SHA-256 prefix. Copied it back to:

`D:\AI\BioNodulo\phd-verification-2026-09-19\coverage-e2e-before-normalization-version.json`

- Size: **11,315,796 bytes**.
- SHA-256: `3fdfc30540304be04e33ac68c63a0b5a6fbb651c4c891e26e930924ab85229f8`.
- Restored copy hash equals the recycle payload hash; JSON parses successfully and
  contains coverage data for 1,514 files.
- The recycle payload was retained; no other evidence file was overwritten.

This restores the original payload, not a reconstructed or newly generated report.
It does not independently verify the preceding cleanup's total reclaimed bytes or
file count. Sampling two files from an archive is also insufficient to certify
whole-archive duplication; keep that distinction when interpreting the old report.

### Deleting the MCP venv broke active configuration

The configured BioNodulo, GitHub and Vercel MCP launchers all referenced
`BioNodulo/mcp/.venv/Scripts/python.exe`, which no longer existed. Recreated the
environment with `uv sync --locked` using the existing lockfile and Python 3.13.
No credentials or MCP registrations were replaced.

Verified with actual stdio clients:

| Service | Result |
| --- | --- |
| BioNodulo | 38 tools discovered; `get_service_health` returned `status: ok` |
| GitHub | 27 tools discovered |
| Vercel MCP | Launcher now starts, but remote authentication returns HTTP 401 |
| Vercel CLI | `vercel whoami` succeeds; CLI access is distinct from MCP authentication |

The MCP launcher reads `apps/web/.env.robust-pull`, so that file is actively used.
It is also referenced by `robust-work/mint_clerk.py`. The three other named env
variants and Clerk keyless file remain untracked and ignored; this audit did not
delete them or claim that their credentials are revoked. Secret values were not
included in output or this report. Clients that failed MCP startup may need to
reconnect after the environment restoration.

### Preserve the running WSL distribution

`wsl --list --verbose` and the Windows WSL registry both identify the large disk as
belonging to the running `BioNodulo-PhD-Audit` distribution at
`phd-implementation-2026-09-23/runtime/wsl`. Unregistering WSL deletes the
distribution's data; it is not a verification step that makes that data disposable.
No termination, unregister, disk deletion, or archive deletion was performed.

## Website corrections

Verified the public GitHub release `desktop-v0.1.1-alpha.1`: it includes arm64/x64
macOS DMGs, a Windows x64 setup executable, and Linux amd64 AppImage/DEB assets.
Corrected the contradictory no-installers statement and removed unverified
Homebrew/winget commands. Installer/update docs now point to actual release assets
and describe the implemented user-initiated install/restart behavior.

Also aligned the Professional team-workspace comparison with the entitlement
source and corrected unsupported privacy-retention wording. Preserved the six
pre-existing website edits. The catalog count remains the website's 983-node
snapshot. The docs build produced 63 pages; website lint passed with two existing
hook warnings. These are local edits, not published website changes.

## Validation and remaining limits

The focused Python commands cover catalog consistency, capability requirements,
manifest invocation, the generated EMBOSS/directory contracts, retained run
oracles, and the pinned-source HMMER contract. They do not rerun every external
tool merely because a retained receipt test passes.

```text
python scripts/gen_node_index.py --check
python scripts/export_capabilities.py --check
python scripts/compile_catalog.py --check
python scripts/check_generated_manifests.py reports/node-expansion
python -m ruff check bionodulo tests
python -m pytest tests/test_node_index.py tests/test_node_conformance.py tests/test_package_constraints_reach_solver.py tests/test_capability_metadata.py tests/test_generated_manifests.py tests/nodes/emboss_family tests/nodes/test_generated_directory_outputs.py -q
python -m pytest tests/nodes/csvtk_family tests/nodes/seqfu_family tests/nodes/htslib_tabix_family tests/nodes/samtools/test_chain_receipt_oracle.py tests/nodes/samtools/test_container_receipt_oracle.py tests/nodes/protein_database/test_receipt_oracle.py tests/nodes/wrapped_protein_taxonomy/test_hmmer_search_wave.py -q
npm test -- toolKnowledgeGraph
```

The two Python groups passed 219 and 72 tests respectively; a final combined run
passed all 291 after the repairs. Nine Tool Atlas graph tests passed.
Generated index/metadata/capabilities agree at 1,372, and the manifest
checker reports 375/375. Whitespace checks allow the existing CRLF style in files
already stored that way; no whole-file formatting conversion is claimed as a fix.

Retained batch receipts have limited scopes and include failures:

| Family | Successful / attempted in retained sample |
| --- | --- |
| EMBOSS | 61 / 80 |
| csvtk | 18 / 24 |
| SeqKit | 11 / 24 |
| SeqFu | 15 / 20 |
| vcflib | 26 / 27 |

Receipt hashes checked during this audit matched retained artifacts (17 standalone
receipt files, 31 protein-workflow artifacts, and 11 Samtools-chain artifacts).
Batch samples do not include independent scientific oracles for every result.
The two new alignment checks above are separate from those historical samples.

Release blockers and follow-up work:

1. **Execution coverage remains incomplete.** The compiled catalog records 1,365
   evidence-pending nodes, seven promotion candidates and zero released typed
   nodes. Importability/legacy compatibility is not execution admission.
2. **23 new UniKmer nodes lack citation fields.** Their documentation URL and
   ontology annotations exist, but they do not supply a bibliography reference.
   Verify an appropriate software/documentation citation; do not invent a paper
   or substitute the author's unrelated publication.
3. **HMMER coverage is contract-only.** Removing five permanently skipped test
   bodies was justified; their replacement explicitly declares
   `contract-checked-no-external-execution`, not an executed HMMER workflow.
4. **Vercel MCP authentication still needs repair.** Working CLI authentication
   does not prove the MCP endpoint accepts the same credential.
5. **New work is uncommitted and not deployed.** Full CI and broad real queue,
   cloud, installation and scientific validation must run against the eventual
   expansion commit before making wider coverage or production-readiness claims.

There is no basis here for an all-bio.tools or PhD-complete claim. The repaired
generators and retained evidence provide a more reliable starting point for the
next verification wave.
