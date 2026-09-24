# Generated bio.tools toolbox

The toolbox includes one automatically generated definition for every record in
the verified 24 September 2026 bio.tools snapshot: **34,248 / 34,248**. No accession
allowlist, tool-name guessing, per-tool Python module, or manually maintained
port template is involved. Existing executable nodes remain separate.

Each definition has a stable accession-derived ID, description, tool types,
EDAM topic/operation annotations, original source record, source-record SHA-256,
snapshot SHA-256, structured-source candidates and explicit execution blockers.
It can be searched, added to the canvas and saved in a workflow. Class creation
and metadata loading happen only when that node is requested. Pagination uses
the server catalog, so startup does not import 34,248 Python classes or download
the entire registry to the browser.

## What the count proves

The committed [coverage receipt](../reports/registry-toolbox/coverage.json)
records exhaustive comparison with the verified source snapshot. Every source
record has one matching definition, every definition's actual app metadata
round-trips through workflow JSON, and every shared adapter refuses execution.
The verifier also samples actual lazy registry lookups deterministically.
The full packaged projection and its digest are checked in CI.

This is **100% definition coverage of a dated snapshot**, not 100% executable
coverage. The crawl is not transactional: start/end counts, page lengths,
unique accessions and first-page order were verified, but source metadata can
change during the recorded 15-minute crawl. The package does not silently fetch
new registry content at runtime.

bio.tools descriptions do not necessarily contain commands, arguments, output
contracts, version-pinned environments, test inputs or expected biological
results. They also describe libraries, database portals and web applications.
The generator preserves those records without inventing runnable interfaces.
EDAM annotations are retained as annotations; they are not fabricated command
line ports. See the [bio.tools minimum information standard](https://bio-tools.github.io/Tool-Information-Standards/use_cases.html).

Generated definitions use the reserved `biotools_<32 hexadecimal digits>`
namespace. They show **Reference only** on the canvas. App run admission,
dependency readiness, HPC submission and the direct executor reject this
namespace, including nested subgraphs and forged saved readiness flags. The
website independently rejects these IDs before preflight, storage staging or
paid worker submission. Executable adapters have distinct contract-derived IDs;
an exact accession link does not imply their runtime is installed or their
outputs are scientifically validated.

## Reproduce and refresh

```powershell
python -m scripts.sync_biotools_registry --output-dir <snapshot-directory> --workers 2
python -m scripts.generate_registry_toolbox --snapshot <snapshot-directory>/registry.jsonl --manifest <snapshot-directory>/manifest.json
python -m scripts.verify_registry_toolbox --snapshot <snapshot-directory>/registry.jsonl --manifest <snapshot-directory>/manifest.json --report reports/registry-toolbox/coverage.json
python -m scripts.acquire_typed_cwl_links --help
```

Generation validates the complete source digest, count and case-insensitive
accession uniqueness before atomically publishing the catalog. Identical input
produces an identical compressed catalog. Failed generation leaves the previous
catalog intact. The compressed SQLite file is included in the Python package,
desktop backend staging and container source. A private temporary directory
holds its read-only expanded database, without network access on startup.
`BIONODULO_REGISTRY_CATALOG` can select another locally generated catalog.

The acquisition command visits every explicitly typed CWL source link in the
verified snapshot. It records exact source bytes, hashes, retrieval failures and
parser outcomes. It restricts retrieval to bounded public HTTPS targets, pins
the resolved address, refuses redirects, and rechecks cached content hashes.
The fresh full-registry pass found eight typed links in five records: six exact
CWL files were fetched and parsed, two directory links require repository-level
acquisition. None of the six declares the explicit pinned package identity
required by the native execution importer. No execution admission was inferred.

## PhD acceptance boundary

The v4 proposal additionally requires empirical container probes, observed file
reads/writes, expert confirmation, biological reference tests, four workflow
format round trips, reproducibility measurements and human research. Generating
registry definitions closes none of those by itself. The separate 65-criterion
acceptance assessment preserves the original 62 requirement IDs and adds three
previously grouped promises. A PhD-complete claim remains unsupported.

Automatic wrappers also have prior art: [ToolDog](https://github.com/bio-tools/ToolDog)
generates CWL/Galaxy templates, and [aCLImatise](https://pmc.ncbi.nlm.nih.gov/articles/PMC8016486/)
infers wrappers from command-line help. The research claim must be evaluated on
demonstrated execution, semantic fidelity, measured maintenance costs and
scientific/user-study outcomes, not on the existence of generated node labels.
