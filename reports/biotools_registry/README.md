# bio.tools registry audit artifacts

For complete, verified current synchronization and app discovery, use [SYNC.md](SYNC.md).
The reports listed below are historical snapshots; they do not prove that every
registry entry has a working or scientifically validated executable node.

- completeness_report.json: registry-wide EDAM annotation completeness
  statistics (34,230 tools, September 2026) plus BioNodulo coverage.
- inference_agreement.json: clause-level agreement between
  registry-inferred draft contracts and the expert seed contracts.
- registry_snapshot.jsonl (NOT committed, 67 MB): the raw crawl snapshot.
  Regenerate with: python scripts/crawl_biotools_registry.py
  (resumable; roughly 10 minutes end to end).
