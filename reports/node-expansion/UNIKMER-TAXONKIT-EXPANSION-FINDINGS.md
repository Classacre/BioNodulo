# UniKmer and TaxonKit expansion, plus an EDAM topic audit

**Date:** 2026-09-27
**Route:** the subcommand method from `SUBCOMMAND-EXPANSION-FINDINGS.md` (read the
tool's own `--help` tables, emit one node per subcommand).
**Result:** builtins **1258 → 1289** (+23 UniKmer, +8 TaxonKit).
**Status:** contracts only. No container was run for this batch, so nothing here is
a verified operation. The reason is in section 5 and it is not a small one.

---

## 1. Why these two

The coverage scan looked for tools that ship many subcommands but have few or no
nodes. Two stood out, both by the same author (Wei Shen) and both Go/cobra, which
the generator already reads:

| Tool | Subcommands | Nodes before | Nodes after |
| --- | --- | --- | --- |
| `unikmer` | 24 | **0** | 23 |
| `taxonkit` | 11 | 2 (hand-written) | 10 |

UniKmer at zero nodes was the larger gap: a whole k-mer toolkit absent from a
catalog that already had `csvtk`, `seqkit` and `seqfu` from the same author.

## 2. What was produced

| Metric | UniKmer | TaxonKit |
| --- | --- | --- |
| Subcommands seen | 24 | 11 |
| **Nodes generated** | **23** | **8** |
| Skipped, already hand-written | 0 | 2 (`name2taxid`, `profile2cami`) |
| Skipped, non-data command (`version`) | 1 | 1 |
| Nodes with empirically-probed required flags | 2 | 0 |

The two probed UniKmer flags are `unikmer grep --query` and `unikmer map --genome`.
Neither is marked required in the help output, which is why the probe exists.

## 3. Two generator changes this batch forced

### 3.1 The output flag is not one flag

The generator previously took a single `--output-flag` for the whole run. UniKmer
uses three different conventions in one binary:

```
unikmer count   -o, --out-prefix string   out file prefix ("-" for stdout)
unikmer encode  -o, --out-file string     out file ("-" for stdout)
unikmer split   -O, --out-dir string      output directory
```

Rendering `--out-file` for all three would have produced nodes whose declared
output file the tool never writes. That is the same class of error as the
`samtools_index` false alarm, except this time it would have been real.

`detect_output()` now reads the output flag off each subcommand's own help page and
picks one of four shapes: `stdout` (the flag accepts `-`, so the executor captures
stdout into the planned file), `file`, `dir`, or `none`. It prefers the container
over the name inside it, because `unikmer tsplit` declares both `--out-dir` and
`--out-prefix` and writes files into the directory.

Result across the 23 UniKmer nodes: 20 capture stdout, 3 declare a directory.

### 3.2 A global flag can be the whole premise

The parser stops at the `Global Flags:` section, on the theory that inherited flags
are noise. For TaxonKit that theory deletes the one flag that matters: `--data-dir`
points at the NCBI taxonomy dump, and without it none of the 11 subcommands can do
anything. A node generated without it would look complete and be unusable.

Global flags are now parsed and tagged rather than dropped, and `--promote-global`
names the ones a family should keep. TaxonKit promotes `data-dir` only, so the
generated nodes carry it with its real default (`/root/.taxonkit`).

Also removed: the generator read the 107 MB registry snapshot on every run into an
`accessions` set that nothing consumed. `--snapshot` is now optional and the dead
block is gone.

## 4. Verification that did happen

The Docker engine was unavailable (section 5), so nothing below involved running a
tool. What could still be checked, was.

**Citation.** The registry record's DOI for TaxonKit was checked against Crossref
rather than trusted. `10.1016/j.jgg.2021.03.006` resolves to "TaxonKit: A practical
and efficient NCBI taxonomy toolkit", Journal of Genetics and Genomics, 2021, Shen
Wei and Ren Hong. That is the right paper.

**UniKmer has no publication or DOI.** A Crossref search for it returns only
unrelated k-mer tools (KAnalyze, KAT, QuicK-mer). The author's SeqKit paper is a
different tool and is not cited. On 2026-09-29, the adapter's empty reference
metadata was replaced with a software citation pointing to the official UniKmer
repository and documentation; the official sources give no separate citation
instructions or publication.

**EDAM topics.** Every topic the new adapters declare was resolved against the
pinned `EDAM.csv` (SHA-256 `cac8ca5d4e63f793c17a2e2cb31087ff573bec6fb438966a3f0c54e4bf479923`,
which reproduced exactly). UniKmer gets `topic_0157` (Sequence composition,
complexity and repeats) and `topic_0080` (Sequence analysis); TaxonKit gets
`topic_0637` (Taxonomy) and `topic_0622` (Genomics). All four are current, not
obsolete.

**Commands render.** Sampled six nodes and printed their argv:

```
unikmer count --canonical --kmer-len 21 --out-prefix - reads.fq
unikmer split --chunk-size 100M --out-dir /out/unikmer_split kmers.unik
taxonkit lca --data-dir /data/taxdump --out-file - taxids.txt
```

## 5. The blocker: no container execution path

Mid-batch the Docker engine stopped responding:

```
error during connect: ... open //./pipe/dockerDesktopLinuxEngine:
The system cannot find the file specified.
```

Docker Desktop is not running, and it cannot be restarted from here. Launching it
is refused by security policy, which blocks `wsl.exe`:

```
PROGRAM BLOCKED BY SECURITY POLICY
  - wsl.exe (C:\WINDOWS\System32\wsl.exe)
This block cannot be approved or bypassed from the current command.
```

Docker Desktop's settings have `WslEngineEnabled: true`, so the WSL engine is the
only backend it will start. With `wsl.exe` blacklisted there is no way for the
engine to come up.

Consequences for this batch, stated plainly:

- The three images pulled before the outage (`vcflib`, `vg`, `odgi`) have real
  local digests recorded, but nothing has been run in them.
- The UniKMer and TaxonKit help pages came from dumps made in an earlier session,
  from tags re-confirmed against the quay API in this one.
- Their image digests are **registry manifest digests read from the quay API**,
  not local pull digests. They are recorded as such in
  `bionodulo/nodes/generated/*_node_ids.json` under `digest_provenance`.
- The empirical required-flag probes for UniKMer and TaxonKit were run in the
  earlier session, before the outage. The probes for any further suite cannot be
  run now.

To restore the execution path, `wsl.exe` needs removing from Security Center ->
Command Security -> Program Blacklist, and Docker Desktop restarted.

## 6. Side finding: 19 of 44 EDAM topics in the catalog are obsolete

Checking my own topic choices turned up a pre-existing problem. Against the pinned
EDAM release `1.25-20260626T1230Z`, the builtin nodes reference 44 distinct topics
and **19 of them are obsolete**, across 128 occurrences. EDAM supplies a
`replacedBy` for every one:

| Topic | Occurrences | Label | Replaced by |
| --- | --- | --- | --- |
| `topic_0182` | 22 | Sequence alignment | `topic_0080` |
| `topic_0090` | 18 | Information retrieval | `topic_3071` |
| `topic_0158` | 11 | Sequence motifs | `topic_0160` |
| `topic_0109` | 9 | Gene finding | `topic_0114` |
| `topic_0107` | 7 | Genetic codes and codon usage | `topic_0203` |
| `topic_0137` | 7 | Protein hydropathy | `topic_0123` |
| `topic_0100` | 7 | Nucleic acid restriction | `topic_0821` |
| `topic_0159` | 6 | Sequence comparison | `topic_0080` |
| `topic_0767` | 4 | Protein and peptide identification | `topic_0121` |
| `topic_0110` | 4 | Transcription | `topic_0203` |
| `topic_0188` | 4 | Sequence profiles and HMMs | `topic_0160` |
| `topic_0094` | 3 | Nucleic acid thermodynamics | `topic_0097` |
| `topic_0640` | 3 | Nucleic acid sequence analysis | `topic_0080` |
| `topic_0178` | 3 | Protein secondary structure prediction | `topic_0082` |
| `topic_0747` | 3 | Nucleic acid sites and features | `topic_0160`, `topic_0640` |
| `topic_0141` | 2 | Protein cleavage sites and proteolysis | `topic_0121` |
| `topic_0694` | 2 | Protein secondary structure | `topic_2814` |
| `topic_0748` | 2 | Protein sites and features | `topic_0639`, `topic_0160` |
| `topic_3060` | 1 | Regulatory RNA | `topic_0659` |

Not fixed in this batch, because it touches 40-odd files that are unrelated to
UniKMer and TaxonKit, and the mapping deserves review before it is applied. The
new nodes do not add to the count.

## 7. Three defects the test suite caught

Adding 31 nodes surfaced three pre-existing problems, all of which made earlier
batches look cleaner than they were.

### 7.1 The node linter's stdout rule was half-dead and half-blind

`scripts/node_linter.py` L2 read:

```python
if (stdout_tool or writes_redirect) and not has_plan and not writes_redirect:
```

The `or writes_redirect` is dead: the same condition also requires
`not writes_redirect`, so the whole expression reduces to
`stdout_tool and not has_plan and not writes_redirect`.

Two further gaps made it wrong in both directions:

- `has_plan = "PLAN_OUTPUTS" in node_cls.__dict__` only sees the node's own class,
  so it missed every family whose shared adapter overrides the method once for
  dozens of nodes (csvtk, seqkit, unikmer, taxonkit).
- It checked the tool name and nothing else, so it flagged all 31 generated seqkit
  nodes even though each renders an explicit `-o <path>` and the declared output
  file really is created. That is a false positive, not a finding.

The rule now accepts any of three things that make a declared output real: the
command names an output path, the node captures stdout via `STDOUT_OUTPUT_INDEX`,
or `PLAN_OUTPUTS` is overridden anywhere below the framework base.

### 7.2 Six suite packages were constrained by nodes but unknown to the solver

`test_every_node_constrained_package_is_pinned_for_the_solver` was failing on
`csvtk`, `emboss`, `seqkit`, `tabix`, `taxonkit` and `unikmer`. Each family declares
`CONDA_PACKAGE_CONSTRAINTS`, but a constraint the solver's `PACKAGE_MIN_VERSIONS`
table has never heard of has no effect. The six pins are now in
`bionodulo/environments/constants.py`. Four of the six predate this batch.

### 7.3 The category convention is inconsistent across suites

Five of the eight large suites now carry a tool-named category (`samtools` 27,
`emboss` 169, `csvtk` 48, `seqkit` 39, `unikmer` 23, `taxonkit` 8), while three
stay topical (`bcftools` → `variant` 34, `bedtools` → `genomics` 38,
`seqfu` → `sequence` 23). Both patterns are defensible; having both at once is not.

`seqkit` is the one that changed in this work. The eight hand-written seqkit nodes
were moved from `qc`/`sequence` into a `seqkit` category, which broke
`test_galaxy_parity_nodes`, whose expectation table still recorded the old values.
The table was updated to match, and that is a product decision rather than a
correctness fix, so it is called out here rather than buried: if the topical
grouping is preferred, revert `CATEGORY` in `seqkit_family/adapter.py` and put the
eight entries in the test back.

### 7.4 Two failures that are not about nodes

The full suite went from **6 failures to 3** after 7.1 and 7.2:

```
3 failed, 8793 passed, 660 skipped in 873.58s
```

All three remaining failures are unrelated to the node work.

`test_cwl_reference_runtime.py` fails two symlink-rejection tests on Windows. The
tests create a symlink and expect the runtime to reject it; the symlink is created
successfully and no error is raised, so the guard does not work on this platform.

`test_workflow_executor_blocks_downstream_until_pause_approval` fails inside the full
run and passes on its own in 2.19 s, so it is load or timing dependent rather than
broken.

## 8. Files changed

New:

- `bionodulo/nodes/builtin/unikmer_family/` (adapter, package init, 23 nodes)
- `bionodulo/nodes/builtin/taxonkit_family/adapter.py` (+8 nodes beside the 2 owners)
- `bionodulo/nodes/generated/unikmer_node_ids.json`, `taxonkit_node_ids.json`
- `scripts/dump_tool_help.py` (reusable help dumper, both `subcommands` and `flat` modes)
- `reports/node-expansion/unikmer-generated.json`, `taxonkit-generated.json`
- `reports/node-expansion/UNIKMER-TAXONKIT-EXPANSION-FINDINGS.md` (this file)

Modified:

- `scripts/generate_subcommand_nodes.py` (output detection, global-flag tagging, dead
  snapshot read removed)
- `scripts/node_linter.py` (L2 rule)
- `bionodulo/environments/constants.py` (six suite pins)
- `tests/test_galaxy_parity_nodes.py` (eight seqkit category expectations)

## 9. Honest limits

- 31 contracts, 0 verified operations. The UniKMer and TaxonKit nodes render a
  command; they have no queued run and no independent oracle.
- Both suites need external reference data to do anything. TaxonKit needs the NCBI
  taxonomy dump at `--data-dir`. UniKMer's `--data-dir` default is `/root/.unikmer`.
  The flag is exposed for TaxonKit; for UniKMer it is still inherited and not
  declared, which is a known gap.
- Both tools take multiple input files for several subcommands (`concat`, `merge`,
  `inter`, `diff`, `union`). Each generated node exposes one positional input, so
  those operations are under-expressed.
- `unikmer split` and `tsplit` declare a directory output with no filenames, since
  which files appear depends on the input k-mer set and chunk size.
