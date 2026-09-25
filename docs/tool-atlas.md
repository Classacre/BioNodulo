# Tool Atlas

Open **Nodes → Open Tool Atlas** in the editor. The atlas indexes every builtin
in the editor's object-info response automatically. It does not maintain a
second curated tool roster. The initial catalog has 983 node definitions in
55 existing categories; several operations can belong to the same upstream
tool. Reference-only bio.tools entries and workspace custom nodes are outside
this view.

## Finding something useful

Start with a category or search by name, alias, description, declared format,
or supplied ontology term. Select an operation to explore its neighborhood.
Use **Data flow candidates** to inspect possible predecessors and successors;
filter by format or direction to narrow broad types such as FASTA and TSV.
Use **Related tools** for shared categories, citations, ontology terms,
explicit tool identity, and documented relationships.

The graph shows at most six neighbors per page. All matching neighbors remain
available through pagination. Click a neighbor to explore it, use Back to
retrace your steps, or inspect the equivalent keyboard-accessible list beneath
the graph. Click an edge or a list explanation to inspect its reason and any
recorded source. A single visual edge can summarize several port matches;
the list retains each reason. Use zoom/pan on narrow screens or read the list.

**Add to workflow** inserts the selected builtin through the normal node-library
action. It neither creates connections nor runs the tool. **Export view** saves
JSON containing the visible neighborhood, filters, metadata, evidence, counts,
and limitations. From the overview it exports the builtin metadata inventory
with no edges; it is not a full all-pairs edge dump. To export a bibliography,
add the desired nodes to a workflow and choose **Export → References**.

## What a connection means

| Connection | Evidence | What it does not prove |
| --- | --- | --- |
| Dashed teal, port format | An output and input declare a common type | Matching schema, reference assembly, units, sample identity, sort state, parameters, cardinality, installation, or successful execution |
| Dashed violet, related metadata | Same category, DOI, EDAM term, or explicitly supplied canonical tool URI | Interchangeability, a recommended workflow, or scientific validity |
| Solid amber, documented relationship | A node author records a source URL, check date, and explanation | That BioNodulo has run this composition or that every parameterization works |

Arrowheads on format edges indicate producer → consumer. Documented successor
and replacement relationships also retain their original direction; reverse
exploration does not reverse the assertion. Alternative/complementary and
shared-metadata edges are displayed without arrowheads. The selected node is
the center of exploration, not necessarily the source of an edge.

Union types such as `SAM|BAM` contribute candidates for their declared members.
Lists, compressed formats, and uncompressed formats stay distinct. Generic
`FILE`, `STRING`, `JSON`, `TXT`, and similar unconstrained types do not form
data-flow edges. No tool-specific compatibility rule is hidden in the graph.
Unknown ports or unavailable metadata can therefore leave a node without
data-flow candidates; its category and recorded references still support
discovery.

Existing citations are displayed as recorded, not silently reverified.
The citation-check counter counts nodes with at least one recorded check,
not nodes with complete bibliographies. The initial Samtools annotations
include checked sources and a conditional sort → index relationship. The
underlying tools, runtime contracts, and scientific admission gates are unchanged.

## Authoring nodes that appear here

Keep the normal builtin class, family, `NODE_ID`, `CATEGORY`, ports, aliases,
and citation fields. Run `python scripts/gen_node_index.py` and
`python scripts/compile_catalog.py --write`; check both outputs before committing.
Do not edit the generated JSON by hand. Once the editor reloads its catalog,
the new builtin appears without an atlas code change.

Optional `KNOWLEDGE` enriches that automatic view. Its runtime validator is
`bionodulo/nodes/knowledge.py`; the frontend mirrors this contract in
`web/src/utils/nodeKnowledge.ts`. This information is descriptive and does not
participate in execution admission. Omit unverified optional fields instead
of using empty strings or fabricated values.

| Field | Format and meaning |
| --- | --- |
| `schema_version` | Required integer `1` |
| `tool_id` | Verified canonical public HTTP(S) tool URI, normally `https://bio.tools/<accession>`; never infer this from a similar name |
| `topics` | Array of `{uri, label}`; URI must identify an EDAM `topic_...` |
| `operations` | Array of `{uri, label}`; URI must identify an EDAM `operation_...` |
| `relations` | Array of the relationship objects below; targets use builtin object-info keys / `NODE_ID`, not typed `NodeSpec.identity.stable_id` |
| `citation_evidence` | Array of `{identifier, source_url, checked_at, note}`; records the check that supports choosing a citation |
| `reviewed_at` | Optional actual annotation review date, `YYYY-MM-DD` |
| `introduced_at` | Optional actual integration date, `YYYY-MM-DD`; not a publication date or a claim to live upstream monitoring |

All arrays allow at most 1,024 entries, with no duplicate terms or relations.
Text is trimmed and nonempty. Dates must be valid calendar dates. Source URLs
use public DNS hostnames and HTTP(S), without embedded credentials; localhost,
private/internal hosts, and IP literals are rejected. Unknown schema keys or
relation kinds fail backend validation; the frontend ignores malformed optional
knowledge without dropping the builtin itself. These checks validate structure,
not truth: a reviewer still has to open and assess the cited source.

Relationship format:

```json
{
  "target_node_id": "samtools_index",
  "kind": "documented_successor",
  "source_port": "sorted_bam",
  "target_port": "bam",
  "evidence": {
    "url": "https://www.htslib.org/doc/samtools-sort.html",
    "checked_at": "2026-09-25",
    "note": "Indexing requires the default coordinate sort; name/tag sorting is unsuitable. This is a documented next step, not a validated BioNodulo run."
  }
}
```

`source_port` and `target_port` are optional. When supplied, review them against
the actual source output and target input; the structural validator cannot
prove a target exists in another deployment. Dangling targets are omitted from
the visible graph, so the batch reviewer must detect and repair them.

The allowed kinds have distinct meanings:

- `alternative_to`: a documented alternative for a stated task; explain
  differences in inputs, assumptions, accuracy, and licensing.
- `complements`: tools used together for a stated purpose; no execution order
  or compatible ports is implied.
- `documented_successor`: source operation can precede the target under the
  conditions stated in the evidence note.
- `superseded_by`: source has a documented successor/replacement; do not use
  this merely because the target is newer or more popular.

For an executable in-repository example, inspect `SamtoolsCommandNode.KNOWLEDGE`
in `bionodulo/nodes/builtin/samtools_family/adapter.py` and
`SamtoolsSortNode.KNOWLEDGE` in `sort.py`. Shared family annotations are inherited;
do not inherit a citation check into a subclass whose citation no longer matches.
Keep exporter data in `CITATION_DOIS`, `CITATION_URLS`, and `CITATION_TEXT` too.
`citation_evidence` never fabricates missing bibliographic metadata.

## Maintenance and limits

The frontend uses inverted indexes by type, category, citation, tool URI, and
ontology term. It computes edges only for the selected operation, rather than
materializing every pair of nodes. React Flow is the existing visualization
library; the atlas adds no graph database or dependency. Search is paginated
at 40 results and the graph at six neighbors, independently of catalog size.

This first version does not poll publications, infer scientific equivalence,
recommend entire pipelines, verify tool installation, or collapse registry
records into unique software products. Upstream additions require the registry
census and authoring process in the [expansion playbook](builtin-expansion-playbook.md).
Later feed features should compare dated snapshots and retain removals,
retractions, duplicate identities, and stale evidence rather than silently
rewriting history. Do not present publication recency as tool quality.

Tests cover the full current builtin inventory, union/generic ports, evidence
validation, metadata API normalization, graph navigation, reference links,
export, workflow insertion, and narrow-screen layout. Browser tests use the
real generated metadata while stubbing unrelated host APIs; they do not
execute every bioinformatics tool.
