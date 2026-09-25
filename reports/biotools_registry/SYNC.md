# Registry synchronization and discovery

The editor browses the packaged bio.tools catalog through the paginated
`/api/registry/nodes` endpoint. Each generated definition can be added to a graph
as a reference-only node; execution is refused. Explicitly linked executable
nodes are shown separately. The [toolbox guide](../../docs/GENERATED_REGISTRY_TOOLBOX.md)
documents generation, admission rules and verification.

## Refresh and audit a snapshot

Run from the repository root:

```powershell
python scripts/sync_biotools_registry.py --output-dir reports/biotools_registry/current --workers 2
python scripts/audit_biotools_coverage.py --snapshot-dir reports/biotools_registry/current --output-dir reports/biotools_registry/current/coverage --check-imports
python scripts/sync_biotools_registry.py --output-dir reports/biotools_registry/current --search "sequence alignment"
```

Synchronization downloads every API page and checks page lengths, stable
start/end counts, unique accessions and first-page order. Inconsistent crawls do
not replace previous snapshots. Bounded worker batches and SQLite avoid loading
the complete raw registry into memory. The manifest records the non-transactional
crawl window, record count and SHA-256 of the accession-ordered JSONL.

The audit verifies the snapshot hash and compares accessions against indexed
app nodes. It writes a gap ledger, node inventory, totals and discovery metadata
under the selected output directory. Declared links and name/package candidates
requiring review remain separate. `--check-imports` imports Python classes; it
does not execute tools or validate biological results.

These commands prepare and audit data. Follow the [toolbox generation and
verification commands](../../docs/GENERATED_REGISTRY_TOOLBOX.md#reproduce-and-refresh)
to update the packaged catalog. The browser no longer uses a static JSON copy in
`web/public/biotools-registry/`.

## Historical reports

The older `completeness_report.json` and `inference_agreement.json` remain dated
evidence. Their retired resumable crawler could retain stale metadata. They do
not prove current complete coverage, execution, scientific validation or
chance-corrected agreement. Use a new verified snapshot for current measurements.

Attribution: bio.tools registry contributors, CC BY 4.0. Registry records include
databases, websites and other resources as well as command-line tools. Each
tool's installation, execution, licensing and validation need separate evidence.
