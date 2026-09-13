# bio.tools registry audit artifacts

- completeness_report.json: registry-wide EDAM annotation completeness
  statistics (34,230 tools, September 2026) plus BioNodulo coverage.
- inference_agreement.json: clause-level agreement between
  registry-inferred draft contracts and the expert seed contracts.
- registry_snapshot.jsonl (NOT committed, 67 MB): the raw crawl snapshot.
  Regenerate with: python scripts/crawl_biotools_registry.py
  (resumable; roughly 10 minutes end to end).
