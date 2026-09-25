# Per-record task and completion templates

Copy this template into a durable work ledger. Keep one parent record per
bio.tools accession, with child entries for functions, versions, interfaces,
descriptors, and proposed BioNodulo operations. Use `null` for unknown facts;
do not fill gaps with plausible values. Source URLs must identify what was
actually read, and every `checked_at` is the date of that check. The sample
identifiers below are placeholders, not verified science.

## JSON work ledger row

```json
{
  "schema_version": 1,
  "biotools_id": "REPLACE_WITH_ACCESSION",
  "record_url": "https://bio.tools/REPLACE_WITH_ACCESSION",
  "snapshot": {
    "retrieved_at_utc": "2026-09-25T00:00:00Z",
    "source_page_url": "https://bio.tools/api/tool/?page=1",
    "raw_sha256": "REPLACE_WITH_64_HEX_DIGITS",
    "reported_count": null
  },
  "registry_identity": {
    "name": null,
    "tool_types": [],
    "homepage": null,
    "version_labels": [],
    "functions": [],
    "publication_identifiers": [],
    "download_urls": []
  },
  "reconciliation": {
    "status": "unreviewed",
    "existing_node_ids": [],
    "family": null,
    "identity_evidence": [],
    "aliases_or_duplicates": [],
    "reviewer": null
  },
  "candidate_operations": [],
  "state": "reference_only",
  "blockers": [],
  "next_action": "Assess available interfaces and executable descriptors",
  "owner": null,
  "updated_at_utc": "2026-09-25T00:00:00Z"
}
```

Use the source format's real raw hash and timestamps. `reported_count` is the
API's count for the census query, not a per-tool estimate. Suggested
`reconciliation.status` values: `unreviewed`, `existing_exact`,
`existing_related_operation`, `new_operation`, `duplicate_record`,
`ambiguous`, `no_existing_node`. Suggested parent `state` values:
`reference_only`, `candidate`, `executable_admitted`, `blocked`,
`retired_or_missing_on_resync`. An `executable_admitted` parent may still have
other candidate or blocked functions; retain their child rows.

## Candidate operation child row

```json
{
  "function_key": "record-id:function-index:interface:version",
  "edam_operations": [],
  "edam_input_data": [],
  "edam_input_formats": [],
  "edam_output_data": [],
  "edam_output_formats": [],
  "interface": "command_line|cwl|galaxy|web_api|other",
  "upstream_version": null,
  "descriptor": {
    "url": null,
    "revision_or_digest": null,
    "identity_link_evidence_url": null,
    "supported_profile": null,
    "unsupported_semantics": []
  },
  "proposed_node_id": null,
  "node_spec_path": null,
  "family_adapter_path": null,
  "environment": {
    "platform": null,
    "package_or_image": null,
    "exact_pin_or_digest": null,
    "lock_or_receipt_path": null,
    "probe_result": "not_run"
  },
  "ports_and_semantics": {
    "input_contract": null,
    "output_contract": null,
    "biological_predicates": [],
    "unknown_predicates": []
  },
  "verification": {
    "focused_test_command": null,
    "focused_test_result": "not_run",
    "queued_run_id": null,
    "run_receipt_path": null,
    "fixture_source_url": null,
    "fixture_sha256": null,
    "oracle_description": null,
    "oracle_source_url": null,
    "oracle_result": "not_run",
    "output_sha256": null
  },
  "citations": [],
  "knowledge_review": {
    "tool_id_verified": false,
    "edam_release": null,
    "relations_checked": false,
    "citation_evidence_checked": false
  },
  "decision": "candidate",
  "blocker_code": null,
  "blocker_detail": null,
  "reviewed_by": null,
  "reviewed_at": null
}
```

For each citation, retain `identifier`, `kind` (`software_version`,
`software_concept`, `primary_article`, `method`, `usage`, `benchmark`, or
`review`), `metadata_source_url`, `source_citation_url`, `checked_at`,
`title_match`, `version_match`, and a short explanation. A resolved DOI
establishes that an object exists; it does not prove that the object describes
this executable revision. Use `CITATION_*` fields for the current reference
exporter and the optional `KNOWLEDGE.citation_evidence` field for provenance.

## Per-operation admission checklist

- [ ] Explicit upstream identity and exact operation/interface; no name-only
  match or ambiguous suite mapping.
- [ ] Stable new `NODE_ID`, family placement, aliases, and typed `NodeSpec`
  (or supported declarative descriptor) reviewed against existing nodes.
- [ ] Source docs/revision and exact package or image pinned; available on
  target platform; installed executable probed inside the selected runtime.
- [ ] Inputs, controls, output paths, resources, secrets, and errors represented
  faithfully; unsupported required behavior blocks admission.
- [ ] Legal minimal fixture with hashes and an independent expected content or
  numerical result.
- [ ] Focused tests pass; real ordinary-queue run and retained provenance pass.
- [ ] Output checked beyond presence and exit status; scientific unknowns stay
  unknown and known mismatches fail.
- [ ] Citation object/role/version verified and export tested where applicable.
- [ ] API/editor discovery, node index, metadata, catalog, graph, and saved
  workflow identity checks pass.
- [ ] Reviewer records residual limitations and admission decision.

## Batch checkpoint and final report

At every batch boundary store the updated census ledger, source snapshot
manifest, code revision, tests, run receipts, known blockers, and next batch
selection. Resume from the ledger's last completed state; reverify changed
upstream sources, descriptors, package locks, and ontology versions before
reusing old evidence. Do not retry an unchanged blocked record indefinitely.

Use this final report skeleton, replacing every placeholder with measured
values and links to retained artifacts:

```text
Snapshot start/end UTC:
bio.tools API query and snapshot manifest:
Pages fetched / expected; discrepancies; unique records:
Builtin index before / after (node IDs, not distinct tools):
Records by state (reference-only / candidate / admitted / blocked / retired):
Functions and unique EDAM operations:
Families, versions, interface and platform counts:
Existing exact matches; new operation IDs; duplicate/ambiguous identities:
Descriptors acquired / evaluated; environments installed / attempted:
Queued executions passed / attempted; independent oracles passed / attempted:
Citation identifiers verified / attempted; unresolved or conflicting citations:
Graph node and edge counts by asserted/inferred/reviewed; ontology release:
Representative validated compositions and blocked candidate paths:
False admissions detected; abstentions; manual review hours:
Focused tests, catalog/index checks, relevant broader tests, and skipped gates:
All blocked and unprocessed records with machine-readable reason and next action:
Remaining reproducibility and scientific risks:
```

Report the census denominator separately from operation and executable
denominators. A run with exit zero is a run result, not automatically an
independent scientific pass. A graph edge supported only by EDAM data/format
annotations remains a discovery suggestion, not an executable workflow.
