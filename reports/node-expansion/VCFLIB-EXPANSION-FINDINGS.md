# vcflib expansion: 85 nodes from 121 binaries, and the four that are not there

**Date:** 2026-09-28
**Route:** the subcommand method, adapted. vcflib is not one binary with
subcommands, so the binary *is* the operation and the flat mode of the shared node
emitter is used.
**Result:** builtins **1289 → 1374** (+85 vcflib nodes).
**Verification:** 26 of 27 smoke-run vcflib tools exit 0 in the pinned image. One
segfaults, and that is a real finding rather than a harness problem.

---

## 1. Why vcflib

The coverage scan showed vcflib at **zero nodes** while the package installs **121
executables**. It was the largest single gap in the catalog, and it is exactly the
shape the method handles well: each tool documents its own interface.

An earlier attempt was abandoned because vcflib's `doc/*.md` and `man/*.1` have an
**empty OPTIONS section**:

```
# OPTIONS

```

Type: transformation
```

Upstream docs are therefore not a declaration source here. The binary's own
`--help` is, and that needed the container, which needed Docker to be running.

## 2. Four help dialects, not one

vcflib has no single help format. Counting the 92 tools whose `--help` produces
something usable:

| Dialect | Tools | What it gives |
| --- | --- | --- |
| `options:` table (args.hxx) | 26 | short name, long name, uppercase metavar |
| `INFO:` blocks (GPAT++) | 14 | the same, **plus which flags are required** |
| `Params:` blocks | 2 | explicit `<TYPE>` metavars |
| no declaration at all | 50 | nothing, or an `[options]` marker with no list |

The `INFO:` dialect is the best declaration in the whole project so far, because it
is the only one that states requiredness:

```
INFO: required: t,target     -- a zero based comma separated list of target individuals
INFO: optional, r,region     -- a tabix compliant genomic region
```

Note the separator after `required` is a colon in some tools and a comma in others,
in the same file. Boolean flags are not marked, so they are identified from the
tool's own usage line: a flag that appears there with no following value is a
switch (`genotypeSummary --type PL --target 0,1,2,3,4,5,6,7 --file my.vcf --snp`).

Three parser traps, each of which silently produced flagless nodes before it was
fixed:

- **A blank line is not the end of an options table.** Several tools put one
  immediately after `options:`. Treating it as a terminator lost `vcfcheck`,
  `vcfleftalign`, `vcfcombine` and `vcfcreatemulti`.
- **The comma after the short flag is optional.** `vcfcombine` prints `-h --help`.
- **The separator before a description can be a single space.** Long flag names
  leave the column-aligned padding at one space: `--exclude-failures If a record
  fails`. Distinguishing the metavar from the description works because a metavar is
  all uppercase, so `If` is not one.

## 3. What was produced

| Metric | Value |
| --- | --- |
| Executables in the package | 121 |
| Tools whose `--help` yields a usable page | 92 |
| **Nodes generated** | **85** |
| Skipped, read stdin only | 3 |
| Skipped, output shape not expressible | 1 |
| Skipped, shell wrappers | 3 |
| Smoke-run in the pinned image | 27 |
| Of those, exited 0 | **26** |

## 4. The four tools that are deliberately absent

**Three read stdin only.** `vcfdistance`, `vcfgeno2alleles` and
`vcfgenosummarize` document input redirection rather than a positional argument:

```
usage: vcfdistance [customtagname] < [vcf file]
usage: vcfgeno2alleles <[vcf file]
usage: vcfgenosummarize <[input file] >[output vcf]
```

A generated node appends its input path as a positional argument, which never
reaches these tools. Running `vcfdistance t.vcf` treats `t.vcf` as the tag name and
then blocks on stdin; `vcfdistance < t.vcf` works and returns three records. So the
tool is fine and the node shape is what does not fit. Expressing them needs a shell
redirect (`SHELL = True`), which is a contract change rather than a generator tweak,
so they are skipped with the reason recorded in the manifest instead.

**`vcf2fasta` writes one FASTA per sample** (`sample_seq:N.fa`) and its only related
flag is `-p, --prefix`, which names a prefix rather than a file. The node contract
declares a single output and cannot name those files, so generating it would have
produced a node whose declared output never appears.

Distinguishing `<vcf file>` from `< [vcf file]` matters here: the first is vcflib's
metavariable for a positional argument (`vcffilter [options] <vcf file>` accepts a
path and works), the second is redirection. An initial pass that treated both as
stdin flagged 46 tools, which would have thrown away half the family.

## 5. A real defect in the pinned build

**`vcfinfosummarize` segfaults on every valid invocation.** Exit 139, no output:

```
vcfinfosummarize -f DP -i SUMM t.vcf          -> 139
vcfinfosummarize -f DP -i DPX -a t.vcf        -> 139
vcfinfosummarize -f DP -i DPX -m t.vcf        -> 139
vcfinfosummarize t.vcf                        -> 1, "both a sample field and an info field are required"
vcfinfosummarize --help                       -> 0
```

The `--help` case is the control: the binary starts, parses flags and prints its
interface, then crashes as soon as it does any work. That is a tool defect in
`quay.io/biocontainers/vcflib:1.0.15--h3fa9d83_1`, not a mistake in how the node
calls it.

The node is kept, because its contract matches the documented interface, and the
crash is recorded in `vcflib_family/adapter.py`, in
`reports/node-expansion/vcflib-smoke.json`, and here. A run of that node will fail.

## 6. Three generator bugs this batch exposed

### 6.1 A tool flag can collide with the generator's own port

`bgziptabix` declares `-o, --output FILE`, and the generator owns the name `output`
for its own output-directory port. Both ended up in `INPUT_TYPES`, so
`render_command` would have read the user's chosen output file as the run
directory. Tool flags whose names collide with `output`, `output_dir` or the input
port are now renamed (`output_flag`) with the mapping recorded in
`FLAG_TOKENS` and in the manifest's `flags_renamed`.

### 6.2 Short-only flags rendered as `--f`

Some GPAT tools declare a short flag with no long form:

```
INFO: required: -f            -- Output from iHS or XPEHH
INFO: optional: -s            -- Max AF diff for window [0.01]
```

The default renderer emitted `--f`, which the tool does not accept. Nodes now carry
`FLAG_TOKENS` when any flag needs a literal token. This also picked up the trailing
`[0.01]` and `(150)` conventions as parameter defaults.

### 6.3 A switch and a value flag look identical in the help

This one produced a wrong command that still looked plausible. `vcffilter` documents:

```
    -f, --info-filter     specifies a filter to apply to the info fields of records,
    -k, --keep-info       used in conjunction with '-g', keeps variant info
```

Neither line prints a metavar, so the parser typed both as switches. The node then
rendered `vcffilter --info-filter in.vcf`, silently dropping the filter expression
the flag exists to carry. `--info-filter` takes a value; `--keep-info` does not.

The help cannot settle it, so the tool is asked. Run the flag bare and args.hxx
answers:

```
$ vcffilter --info-filter
vcffilter: option '--info-filter' requires an argument
```

`scripts/dump_tool_help.py` gained `probe_value_flags`, which does this for every
metavar-less flag (72 flags across 21 tools) and caches the verdicts under
`artifacts/vcflib-argprobe/`. The result matches the documented semantics exactly:
`info-filter`, `genotype-filter`, `region`, `tag-pass`, `tag-fail` and `allele-tag`
take values; `keep-info`, `invert`, `or`, `filter-sites` and `append-filter` do not.

The first version of the probe returned `false` for everything, because it invoked
`vcffilter info-filter` without the dashes and the tool treated it as a positional
argument. A probe that always answers "switch" is worse than no probe, so the cache
is worth spot-checking against the help text after any change to it.

### 6.4 GPAT tools take their input through a flag

`abba-baba` documents `usage: abba-baba --tree 0,1,2,3 --file my.vcf --type PL`. There
is no positional argument. A node that appends its input path positionally produced
`... --file in.vcf in.vcf`, naming the input twice.

Measured in the pinned image: the trailing positional is ignored rather than
rejected, so both forms exited 0 with identical output. The command was still wrong
in what it said. A required flag named `file`, `input`, `infile` or `vcf-file` is now
promoted to the node's input port, so the rendered command is
`abba-baba --tree 0,1,2,3 --type PL --file in.vcf`.

## 7. A tooling defect found on the way

`gen_node_index.py` could never shrink `node_metadata.json`. `object_info()` seeds
itself from the manifest already on disk and overlays the nodes it loaded, so a node
whose module was deleted stayed in the manifest forever. Deleting four vcflib
modules produced a 1378-key metadata file for a 1374-node index, and
`compile_catalog.py` then refused to build:

```
ERROR: legacy node metadata IDs differ from the forensic baseline
```

The generator now prunes metadata keys that are not in the index, and says which
ones it dropped. This is the root cause of a workaround recorded on 2026-09-25
("delete both generated JSONs and regenerate").

## 8. New guard: generated nodes are checked against their manifests

Regenerating a family overwrites files in place, and a template change can silently
alter them. This batch did exactly that: an early version of the flat-mode change
renamed every node, turning `seqfu_head` into `head`, and nothing caught it because
a regenerated file has no previous version to diff against.

`scripts/check_generated_manifests.py` compares each generated node module to its
manifest record: node id, and the parameter set. It reads both manifest schemas (the
cobra `flags_exposed` and the ACD `tunable_params`/`required_params`), knows that
the output flag is consumed rather than exposed, and applies the recorded renames.
It currently passes for **377 of 377** generated nodes.

It found four real discrepancies while being written, including `seqfu shred
--out-prefix`, which writes `<prefix>_1.fq` and `<prefix>_2.fq`, so declaring a
single output file was wrong. That case now declares a directory.

## 9. Files

New:

- `bionodulo/nodes/builtin/vcflib_family/` (adapter, package init, 85 nodes)
- `bionodulo/nodes/generated/vcflib_node_ids.json`
- `scripts/generate_vcflib_nodes.py` (four dialect parsers, reusing the node emitter)
- `scripts/smoke_vcflib_nodes.py`
- `scripts/check_generated_manifests.py`
- `scripts/dump_tool_help.py` (help dumper, `subcommands` and `flat` modes)
- `reports/node-expansion/vcflib-generated.json`, `vcflib-smoke.json`
- `artifacts/vcflib-help/` (92 help pages), `artifacts/vcflib-binaries.txt`

Modified:

- `scripts/generate_subcommand_nodes.py` (flat mode, output detection, global-flag
  promotion, parameter renames, flag tokens)
- `scripts/gen_node_index.py` (metadata pruning)
- `scripts/node_linter.py` (the stdout rule)
- `bionodulo/environments/constants.py` (six suite pins)
- `tests/test_galaxy_parity_nodes.py` (eight seqkit category expectations)

## 10. Honest limits

- **85 contracts, and the smoke test covers 27 of them.** The other 58 render a
  command that has never been executed. Exit 0 on a three-record fixture shows a
  tool runs; it is not evidence that any output is scientifically correct.- **50 of the 92 tools declare no flags.** Their nodes expose the data ports and
  stdout and nothing else. `vcfbreakmulti` prints
  `usage: vcfbreakmulti [options] [file]` and then lists no options, so its real
  parameter set is unknown. Those nodes are thinner than the rest of the family and
  the manifest says so per tool.
- **One positional input port per node.** Several tools take more than one file
  (`vcfcat`, `vcfoverlay`, `vcfcommonsamples`), so those are under-expressed.
- **The 121 vs 92 gap is unexplained per tool.** 29 binaries produced no usable help
  page. Some are helper scripts (`vcf2bed.py`, `vcf_strip_extra_headers`), but that
  is an assumption, not a measurement.

## 11. State after this batch

| Check | Result |
| --- | --- |
| Builtin nodes | **1374** (was 1289) |
| Typed contract nodes | 7 |
| Generated nodes checked against their manifests | **377 / 377 agree** |
| Node index drift | clean |
| Catalog projections | 1374 / 1374 operational |
| Full test suite | **2 failed, 8879 passed, 660 skipped** |
| vcflib smoke runs | **26 / 27 exit 0** |

The two test failures are `tests/nodes/test_cwl_reference_runtime.py` symlink tests,
which do not work on Windows: the test creates a symlink and expects the runtime to
reject it, the symlink is created, and no error is raised. They are unrelated to the
node work and were failing before this batch.

Regression check on the shared emitter: csvtk and seqkit still regenerate
**byte-identically** after the flat-mode, input-flag and flag-token changes. seqfu
cannot be compared that way, because it was generated by an earlier revision of the
template and its files changed once to bring them up to date; its parameter sets match
its manifest exactly, which is what the manifest checker verifies.
