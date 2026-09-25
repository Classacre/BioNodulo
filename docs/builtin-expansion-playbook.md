# BioNodulo builtin expansion playbook

This is a bounded, evidence-first assignment for an AI agent working for up to
72 hours. The objective is to account for **every** bio.tools record in a fresh
registry census, add useful, distinct executable BioNodulo operations where the
evidence and runtime permit, and make the resulting builtin catalog navigable
through an evidence-backed knowledge graph. A complete census is attainable; a
promise that every registry entry will execute is not. The final report must
expose the gap between those outcomes rather than hiding it.

On 2026-09-25, the checked-in `bionodulo/nodes/node_index.json` contains **983
builtin node IDs**. A same-day metadata inventory found 983 distinct Python
classes, 55 category strings, 258 nodes with no citation fields, 156 with
multiple DOIs, 796 marking external tools, and 6 marking GPU use. The generated
catalog has 983 active legacy-compatible/importability-verified entries, 976
`evidence_pending`, 7 `promotion_candidate`, and no released typed nodes.
These are BioNodulo node types/operations, not 983 distinct upstream tools, not
a current bio.tools record count, and not proof of 983 executable or
scientifically validated runs. The inventory is metadata-only; do not infer
missing environment pins or licenses from absent manifest fields. Two nodes,
`lineardesign_optimize` and `sirius_formula_id`, report external tools but no
required executables; investigate this contract discrepancy early. Category
names include overlapping `Utility`, `utils`, `utils/dev`, and `utils/format`;
reuse the existing family/category assignments. Any category consolidation
requires an explicit mapping and search regression check, not one worker's
ad hoc relabeling. Recount from the
checkout at the start and end of the assignment.
`reports/biotools_registry/completeness_report.json` is
historical evidence, not a live registry census; see `scripts/README.md`.

## Boundaries that govern the work

- A bio.tools **record** describes software and may represent a command-line
  tool, suite, library, web app, API, database portal, or workflow. One record
  may contain multiple functions, and a suite may need several distinct nodes.
  A record is neither an invocation contract nor an installed environment.
  bio.tools explicitly asks curators for coarse primary operations and allows
  different interfaces in one entry ([curation guide](https://biotools.readthedocs.io/en/latest/curators_guide.html),
  checked 2026-09-25).
- Separate record, function/operation, tool family, software version, interface,
  descriptor revision, environment, builtin node, workflow run, and publication.
  Keep those identities separate in data and counts. Do not infer identity from
  display-name similarity. Preserve source accession, URL, retrieval date,
  revision/hash, and the reason for each join.
- A registry entry may link to source, package, container, CWL/Galaxy wrapper,
  API specification, or test data; those download fields are optional. EDAM
  operation is required *inside an annotated function*, while the function
  list itself is optional ([bio.tools model](https://biotools.readthedocs.io/en/latest/api_usage_guide.html),
  checked 2026-09-25). Missing annotations are `unknown`, not evidence of no
  capability.
- The existing bio.tools toolbox is reference-only. Its nodes refuse
  execution. Native CWL, CWL reference, experimental OCI, and typed builtin
  operations have different admission rules. Follow `docs/tool-integration.md`,
  `docs/generated-biotools.md`, and `docs/testing/node-verification.md`.
  Never relabel a reference entry as executable because it has a URL or EDAM
  term.
- Prefer a dedicated operation with a typed `NodeSpec` when the command and
  biological contract are known. Use the existing family adapter and shared
  executor. The Samtools family at `bionodulo/nodes/builtin/samtools_family/`
  and `bionodulo/nodes/catalog/tools/samtools/common.py` show class and typed
  catalog patterns. Reuse the declarative CWL path when an authentic descriptor
  fits its supported profile. Do not create a second execution framework or
  tool-name branches in the shared engine.

## Start: freeze a reproducible census

From the repository root, inspect `git status`, Python environment, free disk,
available RAM, target platforms, existing index, and current reports. Preserve
user changes. Read `scripts/README.md`, `reports/biotools_registry/SYNC.md`,
`docs/tool-integration.md`, `docs/generated-biotools.md`, and the node
verification guide. The registry API offers paginated public GET responses with
`count`, `next`, and `list`; mutation requires authentication
([API quickstart](https://biotools.readthedocs.io/en/latest/api_quickstart.html),
checked 2026-09-25). Use the existing sync, then audit its completeness:

```sh
python scripts/sync_biotools_registry.py --output-dir reports/biotools_registry/current --workers 2
python scripts/audit_biotools_coverage.py --snapshot-dir reports/biotools_registry/current --output-dir reports/biotools_registry/current/coverage --check-imports
python -c "import json; print(len(json.load(open('bionodulo/nodes/node_index.json'))))"
```

Record retrieval start/end UTC, API base URL, query/sort, page URLs, HTTP
status, retries/failures, reported total, unique IDs, duplicate IDs, raw page
hashes, and raw record hashes. Follow `next` until exhausted; reconcile its
results with `count`. The API documents page/per_page and exact ID query rules,
including case-sensitive parameters ([API reference](https://biotools.readthedocs.io/en/latest/api_reference.html),
checked 2026-09-25). An API count changing during pagination is a census
discrepancy to disclose and retry; it is not permission to silently discard
records. Keep a versioned snapshot and compare additions, updates, removals,
and absent pages on later syncs. Do not use the retired crawler or the old
static website index as live data.

Build a **one-record-per-accession** ledger using the companion
`builtin-expansion-task-template.md`; link child rows for each function,
interface, software version, descriptor, and candidate node. Every registry ID
must end in one of these states: `reference_only`, `candidate`,
`executable_admitted`, `blocked`, or `retired_or_missing_on_resync`. A candidate
is unfinished and needs an owner and next step. A blocked row needs a precise
reason such as `no_machine_invocation`, `license_or_access`,
`missing_exact_version`, `unsupported_descriptor`, `unsupported_platform`,
`dependency_resolution_failed`, `reference_data_unavailable`, or
`scientific_oracle_missing`. Do not count a blocked or merely indexed record as
an executable builtin.

## Assignment phases and ownership

The clock is a work limit, not a deadline for claiming coverage. Use short
cycles and checkpoint a durable ledger after each one. One coordinating agent
owns census integrity, stable IDs, package policy, graph rebuild, and final
denominators. Tool-family workers may own disjoint accession ranges/families;
only one worker edits a family adapter or a shared runtime at a time. A review
pass independent of the author checks scientific claims and citation identity.
Avoid concurrent lock regeneration or catalog writes. If only one agent is
available, run the same roles sequentially.

| Timebox | Deliverable | Gate before moving on |
| --- | --- | --- |
| Hours 0–6 | Environment audit, source snapshot, complete ID ledger, baseline index and tests | API pages reconciled or documented discrepancy; no untracked record silently dropped |
| Hours 6–12 | Identity reconciliation and prioritized cohorts | Existing nodes, aliases, suites, versions and interfaces mapped with explicit evidence |
| Hours 12–54 | Repeated acquisition, implementation, and real-run cycles | Each admitted operation has a descriptor or documented command, pinned runtime, focused test, queued run, oracle, and citation check |
| Hours 54–64 | Graph/materialization and cross-tool review | Graph built from the full builtin metadata catalog; candidate edges labelled; representative compositions checked |
| Hours 64–72 | Rebuild, audit, failure triage, final report | All records have a state; generated files current; claims match receipts |

Prioritize high-utility missing operations by research use, installability,
clear CLI/API contract, open test data, and meaningful output oracle. Choose
several interface classes to test the design. Report the selection method and
unprocessed tail. Once a batch's failures show a common missing profile,
improve the shared profile only if it does not weaken existing contracts.
Otherwise keep precise abstentions. A broad wave of metadata-only nodes is
useful for discovery but does not satisfy executable expansion.

After the first 10–20 operations, measure completed admissions per worker-hour,
download size, solve/install time, queue time, and reviewer time. Project the
remaining work using observed rates and report the estimate with uncertainty.
Unlimited model quota does not remove upstream rate limits, missing licenses,
GPU availability, finite RAM/disk, unavailable reference data, or review time.
Use public metadata APIs with bounded concurrency, caching, backoff, and
resumable requests. Keep credentials in existing local secret stores; never
copy browser cookies, access tokens, or licensed material into commits or
node metadata. Request user involvement only for an actual access blocker.

Do not ship tens of thousands of empty executable wrappers to satisfy a node
count. Preserve complete registry visibility through the reference toolbox
while promoting tested operations into the executable builtin catalog. At
larger scales, profile payload size, startup time, search latency, and memory;
the current atlas loads the builtin metadata response. If that response becomes
too large, add a versioned, paginated metadata/index API while preserving
deterministic IDs and graph inclusion, rather than hiding the long tail.

## Reconcile identity before writing code

For each record, collect bio.tools ID and URL, title, tool types, EDAM function
groups, version labels, homepage, repository/download/wrapper links,
publications, and retrieval date. Match existing BioNodulo nodes through
explicit upstream IDs, pinned source, tool homepage/repository, and manual
review; use names as search hints only. Track `existing_exact`,
`existing_related_operation`, `new_operation`, `duplicate_record`,
`ambiguous`, or `no_existing_node`. A version label on a registry record is not
an installable version or an environment lock. GA4GH TRS likewise separates
tool and tool version/descriptors ([TRS data model](https://ga4gh.github.io/tool-registry-service-schemas/DataModel/),
checked 2026-09-25).

Keep `NODE_ID` stable for saved workflows. Do not take an old ID for a new
operation. Place new modules in the appropriate `*_family`, share adapter code
where behavior genuinely overlaps, use discoverable display names and
`SEARCH_ALIASES`, and retain deprecated aliases only with an explicit
migration/deprecation route. The index generator rejects duplicate class
owners. Decide whether a suite deserves one family and several command nodes,
whether a web API has a stable authorized endpoint, and whether a library
needs a supported operation wrapper. A homepage, source repository, or API
endpoint alone cannot be run safely as a local node.

Each operation pull request must contain these concrete deliverables:

| Deliverable | Required content / location |
| --- | --- |
| Implementation | `bionodulo/nodes/builtin/<existing_family>/<operation>.py`; stable `NODE_ID`, task-specific `DISPLAY_NAME`, existing `CATEGORY`, accurate `DESCRIPTION`, useful `SEARCH_ALIASES` |
| Port and parameter contract | `INPUT_TYPES` required/optional/hidden inputs with real types, defaults, bounds and help; `RETURN_TYPES` / `RETURN_NAMES` in matching order; sidecars, lists, compressed formats and union alternatives represented faithfully |
| Runtime | Existing family adapter and shared execution engine; deterministic argv without interpolated shell strings; validated output plan, actionable failure, cancellation, resource and secret handling; appropriate `SHELL` and external-tool flags |
| Typed specification | Existing `NodeSpec` identity, presentation, artifact/semantic ports, parameter and environment contracts; retain both catalog stable ID and discoverable builtin `NODE_ID` in the ledger |
| Installation | Required executables/packages plus exact source/runtime pins and the actual environment provisioning record; a package name alone is not a lock |
| Citations and graph | Checked `CITATION_*`, documentation/source URLs, optional validated `KNOWLEDGE`; source evidence and citation roles in the ledger |
| Verification | `tests/nodes/<family>/...`, legal tiny fixtures, invalid-input cases, actual queue-run receipt and independent oracle; check exported citations in all supported formats |
| Generated artifacts | Refreshed node index/metadata and relevant compiled catalogs/locks, made by the existing generators; no hand-maintained second catalog |
| Handoff | Ledger child row, limitations, changed files, exact commands/results, receipts, and next actions for unresolved blockers |

Use a real neighboring family implementation as the executable template,
not a generic `run(): pass` scaffold. `samtools_family/sort.py` demonstrates
command construction, `adapter.py` shared provisioning and output handling,
and `catalog/tools/samtools/sort.py` the typed specification. Pick the pattern
that matches the interface instead of forcing an HTTP API or Python library
into a CLI wrapper. Re-read `family-assignment-rules.json` and the current
metadata category values before assigning a new operation; avoid duplicate
categories created by capitalization, punctuation, or a new spelling.

## Admission of an executable operation

For each proposed node, make a compact source dossier: official invocation
documentation, exact source release/commit or wrapper digest, expected
arguments, inputs/outputs, error modes, license/access terms where relevant,
package/container identity, reference-data dependency, and a real fixture.
Pin exact packages or immutable image digests and verify the executable from
the installed environment, not the host PATH. The node contract must cover
controls, file staging, output planning, output publication, resources,
secrets, and version-specific behavior. Use `NodeSpec` and the shared
environment/artifact/evidence models. Unknown biological properties remain
unknown; reject known incompatible ones.

CWL can supply a machine-readable command contract. CWL v1.2 requires input
and output schemas and treats unmet requirements as fatal
([CWL specification](https://www.commonwl.org/v1.2/CommandLineTool.html),
checked 2026-09-25). Preserve unsupported CWL, Galaxy, API, shell, network,
or container semantics as a rejection reason. Do not silently omit them. A
fragmentary `function.command` in bio.tools is not a full argument binding.
Avoid running untrusted fetched code merely to inspect it; installation and
execution require an explicit profile and source review.

Implement and verify in this order:

1. Add or extend the family operation and typed `NodeSpec`; maintain exact
   runtime and source evidence. Ensure ports and command rendering derive from
   one declared operation rather than diverging copies.
2. Add a tiny legal fixture and an independent expected result. Test invalid
   inputs, output paths with spaces, planned-versus-rendered paths, and a
   relevant failure mode. The node verification guide notes that planning
   receives the run root while `render_command` receives the node output dir.
3. Run the actual tool from its locked environment through the normal
   BioNodulo queue. Retain the job, rendered command, environment lock,
   input/output hashes, logs, software version, exit status, and timestamps.
   Assert biological or numerical content, not merely exit zero or a file.
4. Check the corresponding API discovery and editor metadata. Refresh the
   generated index before compiling the catalog, because the catalog digest
   includes `node_metadata.json`. Use the commands in `scripts/README.md` and
   the appropriate family, registry, catalog, and conformance tests.
5. If scientific behavior cannot be independently checked, keep the row
   `candidate` or `blocked`, with structural checks recorded separately.

`python scripts/gen_node_index.py` refreshes both the builtin index and editor
metadata; `python scripts/gen_node_index.py --check` detects drift. Run
`python scripts/node_linter.py <node_id>` for focused node checks. Inspect
`scripts/compile_catalog.py --help` and the script map before catalog writes.
Use focused `pytest` for the family and `tests/test_node_index.py`, then only
the broader gates relevant to changed shared code. Record skipped platform
tests honestly. On a memory-limited host use the repository's small worker
counts, avoid simultaneous environment solves and whole-suite tests, bound
parallel API fetches, and leave room for the app/editor process. Do not load
all builtin Python modules for every graph query: use the generated metadata
file and lazy node index.

## Knowledge graph and citation contract

Build the graph automatically from **all** builtin metadata, not from a
selected list. Use stable builtin IDs as node keys; preserve aliases as
search terms, not new entities. Materialize descriptive `KNOWLEDGE` metadata
when present and label inferred edges separately. The optional class field
`BaseNode.KNOWLEDGE` is validated and exposed in both `metadata()` and registry
object info. The implemented [Tool Atlas guide](tool-atlas.md) specifies every
field, relationship direction, validation limit, and UI behavior. Its v1 shape is:

```json
{
  "schema_version": 1,
  "tool_id": "https://bio.tools/samtools",
  "topics": [],
  "operations": [],
  "relations": [],
  "citation_evidence": [],
  "reviewed_at": "2026-09-25"
}
```

The JSON above illustrates shape only; it does not assert any annotation for
Samtools. Omit unverified fields. Allowed
relation kinds are `alternative_to`, `complements`, `documented_successor`,
and `superseded_by`; a relation may also name `source_port` and `target_port`.
The validator rejects unknown keys, duplicate entries, malformed EDAM URI,
URLs without public DNS hostnames, and invalid dates (`bionodulo/nodes/knowledge.py`). `tool_id`
is a public bio.tools URL when verified. `citation_evidence` records why a
citation was selected; it does not populate the bibliography exporter. Set
`CITATION_DOIS`, `CITATION_URLS`, and `CITATION_TEXT` only after checking the
intended software version or primary publication. The current
`bionodulo/converter/references.py` groups by the first DOI of a node; RIS
reuses node citation text for each DOI, while BibTeX places additional DOIs in
a note. With 156 multi-DOI nodes in the baseline, this is a material fidelity
limit: verify each exported record, fix the exporter before claiming accurate
multi-work bibliography, and keep separate publication roles. The focused
contract is covered by `tests/test_references_export.py`.

EDAM distinguishes Topic, Operation, Data, and Format and maintains
operation-input/output and format-data relations
([EDAM relations](https://edamontology.org/relations-and-properties.html),
checked 2026-09-25). Pin the ontology release: the EDAM site distinguishes
rolling and versioned OWL files ([EDAM downloads](https://edamontology.org/),
checked 2026-09-25). Generate default format/data edges as **discovery
candidates only**. They cannot assert executable composability, units,
strandedness, reference assembly, coordinate convention, normalization state,
or required parameter compatibility. Confirm composition with actual ports,
semantic predicates, a workflow run, and an independent output check.

For citations, resolve DOI/PMID/PMCID against authoritative metadata and
compare title, authors, year, type, and association with the exact tool or
version. bio.tools distinguishes primary, method, usage, benchmarking, and
review publications ([curation guide](https://biotools.readthedocs.io/en/latest/curators_guide.html),
checked 2026-09-25). A software paper is not automatically the artifact used
in a run. FORCE11 recommends identifying the version used and distinguishes
version, concept, and article identifiers
([Software Citation Principles](https://force11.org/info/software-citation-principles-published-2016/),
checked 2026-09-25). Consult a project's `CITATION.cff` when present and
cross-check DOI metadata through [Crossref](https://www.crossref.org/documentation/retrieve-metadata/rest-api/)
or [DataCite](https://support.datacite.org/docs/versioning) (checked
2026-09-25). Record unresolved or conflicting citations; never invent a DOI.
Store retrieval date and source URL near each graph or citation assertion.

Use provenance edges to distinguish source assertion, model inference,
human review, and actual run. W3C PROV-O provides `used`, `wasGeneratedBy`,
and `wasDerivedFrom` for such chains ([PROV-O](https://www.w3.org/TR/prov-o/),
checked 2026-09-25). A graph query should return why an edge exists, the
source revision/date, its evidence level, and whether it is safe merely to
discover or to execute. Reject or abstain on contradictory known facts.

## Honest completion and stop conditions

Stop admitting new operations when the remaining time cannot cover a real
environment install, queue run, scientific oracle, citation check, and
rebuild. Spend the final interval reconciling the ledger and report. Also stop
an individual attempt when an upstream license or access rule bars use, when
an exact runtime cannot be reproduced, when necessary data are unavailable,
or when a command needs unsupported unsafe semantics. Keep the registry row
visible with its reason and a tractable future action.

The final report must give a dated snapshot and separate totals for registry
records; unique functions and EDAM operations; tool families; versions;
interface/platform classes; existing builtins; new typed operations;
reference-only rows; acquired descriptors; installable environments; real
queued runs; independent scientific passes; failed/abstained candidates; and
unreviewed records. Include numerator **and denominator** for each rate,
including acquisition, installation, run success, citation verification,
false admissions, abstentions, and manual review effort. Cite the exact
fixture/run receipts and source revisions. Show representative useful
cross-tool paths and at least one blocked path, with the graph's evidence
labels. State unresolved risks and all tests skipped. Do not turn the final
report into a claim that every bio.tools record became an executable node.

This program can improve tool discovery, reproducibility, and composition
evidence. It does not by itself demonstrate a novel biological method or
validate a PhD claim. Keep any thesis-level hypothesis, benchmark design,
held-out evaluation, expert review, and scientific conclusion as separately
specified work with its own evidence.

## Research baseline and a testable contribution

Do not claim novelty merely for connecting tools with ontology annotations.
[APE](https://pmc.ncbi.nlm.nih.gov/articles/PMC7304703/) already synthesizes
workflow candidates from semantically described tools. The primary
[APE in the Wild study](https://pmc.ncbi.nlm.nih.gov/articles/PMC8041394/)
applied bio.tools/EDAM annotations to proteomics workflow exploration and
reported erroneous combinations from broad or incomplete annotations. This
supports treating format matches as hypotheses and evaluating constraints,
not presenting every graph path as runnable. These papers were checked on
2026-09-25; this is an initial related-work baseline, not an exhaustive
novelty review.

An explicit proposed research question is whether source-backed relationships,
versioned contracts, execution receipts, and honest abstention improve tool
selection and composition over keyword search and format-only matching.
Before collecting outcomes, specify tasks, held-out tool families/versions,
expert judgments, and success/failure criteria. Compare the ordinary node
library, metadata-only atlas, and evidence-enriched atlas. Measure task
completion time, correct tool selection, false compatibility suggestions,
abstention/coverage tradeoffs, reproducible execution, and user understanding
of uncertainty. Keep train/development and evaluation tools separate. Record
confidence intervals and failed tasks, not just attractive graph examples.
This is a proposed evaluation design, not a claim of demonstrated benefit or
completion of the PhD proposal.

## Copy-paste master prompt for the 72-hour agent

> Use the BioNodulo checkout containing this handbook and Tool Atlas. Create
> an isolated branch/worktree for expansion, preserving existing work, and
> work for at most 72 hours.
> Follow `docs/builtin-expansion-playbook.md` and
> `docs/builtin-expansion-task-template.md`. First make a fresh, verifiable
> bio.tools census and one ledger row for every accession. Reconcile existing
> builtin identities before coding. Prioritize useful missing executable
> operations; use existing typed `NodeSpec`, family adapters, or supported
> descriptor profiles, with exact source and environment pins. Admit each new
> operation only after focused tests, a real BioNodulo queued run,
> independently specified output checks, and citation verification. Build a
> knowledge graph from all builtins; keep inferred EDAM compatibility edges
> discovery-only and attach source evidence. Checkpoint the ledger after each
> batch. At the deadline, stop new work and report separate census,
> implementation, installation, execution, and scientific denominators plus
> every blocked/unprocessed record and reason. Preserve user changes, avoid
> duplicate frameworks, and make no claim of universal executable coverage
> unless the evidence actually establishes it.
