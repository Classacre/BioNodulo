# Complete registry synchronization and discovery

The application distinguishes registry metadata from executable node implementations. The bio.tools browser in Nodes is a discovery view: all downloaded accessions are searchable, but only explicitly linked definitions already in `node_index.json` can be added to a graph. Registry metadata alone is never registered as a runnable node.

Run from the repository root:

```powershell
python scripts/sync_biotools_registry.py --output-dir reports/biotools_registry/current --workers 2
python scripts/audit_biotools_coverage.py --snapshot-dir reports/biotools_registry/current --output-dir reports/biotools_registry/current/coverage --public-dir web/public/biotools-registry --check-imports
python scripts/sync_biotools_registry.py --output-dir reports/biotools_registry/current --search "sequence alignment"
```

The first command downloads every page from the [official API](https://biotools.readthedocs.io/en/latest/api_reference.html). It checks page lengths, stable start/end counts, unique accessions, and first-page order. Failed or inconsistent crawls do not replace previously published snapshots. It uses bounded worker batches and SQLite so the entire raw registry is never loaded into RAM. This is a fresh crawl, not an append-only merge or a resumable crawl. The manifest records the non-transactional crawl window, record count and SHA-256 of deterministic JSONL ordered by accession.

The second command verifies that hash and compares every accession against every indexed app node. It writes a complete JSONL gap ledger, a node inventory, machine-readable totals, refreshed declared-link metadata and the compact browser dataset. Declared links and exact-name/package **candidates requiring review** remain separate. `--check-imports` imports indexed Python classes; it does not run tools. Windows PATH checks neither inspect WSL/Conda/container environments nor establish scientific correctness.

The compact browser dataset is generated into `web/public/biotools-registry/index.json`, copied into production by Vite and fetched only when the user opens registry discovery. Search covers IDs, names, tool types, topics and short description excerpts, with exact names ranked first. SQLite search covers the complete raw descriptions. The interface renders 40 results at a time; metadata-only entries have no Add button.

The 2026-09-19 audit downloaded 34,242 records across 343 pages. The stored `completeness_report.json` and `inference_agreement.json` from the older `crawl_biotools_registry.py` pipeline are historical artifacts, not proof of current complete coverage, execution, scientific validation or Cohen's kappa. That older crawler skips already-seen accessions and can retain stale metadata; use the verified pipeline above for current evidence.

Attribution: bio.tools registry contributors, [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/). The registry contains databases, websites, ontologies and other resources as well as command-line tools. Tool-specific installation, execution, licensing and validation still need their own evidence.
