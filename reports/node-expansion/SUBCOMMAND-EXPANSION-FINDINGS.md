# Subcommand expansion: 50 csvtk nodes from its own `--help` tables

**Date:** 2026-09-27
**Route:** the same method as EMBOSS — read a machine-readable upstream
declaration rather than hand-writing contracts.
**Result:** builtins **1162 → 1212** (+50 csvtk nodes).

---

## 1. Why csvtk

The gap analysis showed csvtk had **3 nodes** while the tool ships **53
subcommands**. That is the same shape as EMBOSS — one pinned image, many
operations — but with subcommands instead of separate binaries. `seqkit` (8 nodes
of ~30 subcommands) and `seqfu` (3 of ~20) have the same gap.

## 2. The declaration: cobra flag tables

`csvtk` is a Go/cobra program, and cobra prints its flags as a table:

```
Flags:
  -w, --decimal-width int    limit floats to N decimal points (default 2)
  -f, --fields strings       operations on these fields. e.g -f 1:count,1:sum
  -i, --ignore-non-numbers   ignore non-numeric values like "NA" or "N/A"
```

That gives short name, long name, value type and default for every flag — a
declaration, not prose. `scripts/generate_subcommand_nodes.py` reads it and emits
one node per subcommand.

The help pages were dumped from the **digest-pinned**
`quay.io/biocontainers/csvtk:0.31.0--h9ee0642_0`, so the parameter set is tied to
the same build the nodes declare.

## 3. What was produced

| Metric | Value |
| --- | --- |
| Subcommands seen | 53 |
| **Nodes generated** | **50** |
| Skipped — already hand-written (`cut`, `headers`) | 2 |
| Skipped — subcommand already covered (`summary` → `csvtk_stats`) | 1 |
| Nodes with empirically-probed required flags | 11 |
| Lint errors (20-node sample) | **0** |

`csvtk` project-wide: **3 → 53 nodes**.

## 4. The interesting part: cobra does not mark required flags

The first verification round scored **14/24 (58%)**, and seven of the ten failures
were the same thing:

```
[ERRO] flag -n (--name) needed
```

Every flag had been declared optional, because **cobra's help output does not mark
which flags are required**. There is nothing in the table to read.

So I asked the tool instead. Running each subcommand with no flags and reading
`flag -X (--Y) needed` from stderr gives the required set empirically — iterating,
because cobra reports one missing flag at a time:

```sh
for i in 1 2 3 4; do
  out=$(timeout 6 csvtk "$s" $extra /w/mini_table.tsv 2>&1)
  need=$(printf "%s\n" "$out" | sed -n "s/.*flag[s]* \(-[a-zA-Z]\+\) (--\([a-z0-9-]*\)) needed.*/\2/p" | head -1)
  [ -z "$need" ] && break
  extra="$extra --$need 1"
done
```

That found required flags on **11 subcommands** (`mutate --name`,
`filter --filter`, `sample --proportion`, `fold --vfield`, `rename2 --pattern`, …).
The probe results are committed under `artifacts/csvtk-required/` and fed back into
the generator, so the nodes now *demand* those values instead of failing inside the
tool.

**This is the same lesson as EMBOSS's plot device**: when a declaration is silent,
ask the tool. A probe beats a guess.

## 5. Verification

| Round | Sample | Passed | Rate |
| --- | --- | --- | --- |
| First run | 24 | 14 | 58.3% |
| **After the required-flag work** | **24** | **18** | **75.0%** |

A node passes only when it exits zero **and** produces every declared output.

Remaining failures are program-specific rather than converter bugs:
`csvtk plot` writes images not tables, `csvtk csv2xlsx` needs a `.xlsx`
destination, and `csvtk version` is not a data operation at all and should not have
been generated.

## 6. Bugs found

1. **Nested tuple in `OUTPUT_FILENAMES`.** Writing
   `OUTPUT_FILENAMES = ({f"{node_id}.out",!r},)` produced `(('x.out',),)` — a
   repr'd string wrapped in another tuple — and every node died with
   `TypeError: unsupported operand type(s) for /: 'WindowsPath' and 'tuple'`.
   All 24 sampled nodes failed on this one line.
2. **Required parameters were not rendered.** `render_command` iterated only the
   `optional` block, so every empirically-required flag was silently dropped. This
   is the *same* bug the EMBOSS generator had — worth checking in any new generator
   before trusting its output.
3. **Filename-based duplicate detection was not enough.** `stats.py` renders
   `csvtk summary`, so a filename check produced a duplicate `csvtk_summary`. The
   generator now reads the subcommand each hand-written node actually invokes.
4. **A hung subcommand blocked the probe.** `csvtk watch` waits for file changes
   and never returns; a per-call `timeout` was needed before the probe could finish.

## 7. A self-inflicted wound worth recording

While generalising the generated-id loader I sliced `compile_catalog.py` by string
index:

```python
old = s[s.index("def _generated_emboss_node_ids()"):s.index("EXPECTED_NODE_COUNT")]
```

That span contained the entire `POST_BASELINE_NODE_IDS` definition, so the
replacement deleted it and the module stopped importing. It was recovered from
`git show HEAD:` plus the 13 ids added since, but the lesson is concrete:

**Do not slice a source file by index between two anchors.** Anchor on the exact
text being replaced, and assert the result still imports before writing it back.
A one-line assertion would have caught it immediately.

The loader is now `_generated_node_ids()`, which reads every
`bionodulo/nodes/generated/*_node_ids.json`, so a new generated family needs no
change to `compile_catalog.py` at all.

## 8. What this is and is not

**Is:** 50 real, lint-clean, discoverable nodes with upstream-declared parameters,
including 11 that correctly demand a user-supplied value.

**Is not:** 50 verified operations. There is **no independent oracle** for any of
them, so no biological or numerical correctness has been established. They are
contracts. `executable_admitted` in the ledger is unchanged.

## 9. Second suite: seqkit (31 nodes)

`generate_subcommand_nodes.py` was generalised from csvtk-specific to
`--base-class` / `--input-port` / `--output-flag` / `--tabular` / `--documentation-url`
/ `--skip-subcommands`, and applied to seqkit 2.13.0 — the version the existing
eight hand-written owners already pin.

| Metric | Value |
| --- | --- |
| Subcommands found | 45 (5 of them extraction false positives) |
| **Nodes generated** | **31** |
| Skipped — already hand-written | 8 (`fx2tab`, `grep`, `head`, `locate`, `sort`, `split2`, `stats`, `translate`) |
| Skipped — no `Flags:` section, i.e. not a real subcommand | 5 (`bzip`, `format`, `gzip`, `xz`, `zstd` → `unknown command`) |
| Skipped — non-data | 1 (`version`) |
| seqkit project-wide | **8 → 39 nodes** |

The five false positives are worth noting: my subcommand extractor matches any
indented two-space line, so prose in the help text was picked up. They were caught
because their "help page" is an error message with no `Flags:` section — the
generator's existing guard, not a new check.

### The probe needed two fixes for seqkit

seqkit phrases missing requirements differently from csvtk, and the first probe run
scored only **8/24 (33%)**:

```
[ERRO] both flags -s (--step) and -W (--window) needed
[ERRO] one of flags -n (--number) and -p (--proportion) needed
[ERRO] one of the options needed: -r/--region, --bed, --gtf
[ERRO] one of the flags needed: -i/--new-start or -s/--start-with
```

1. **The regex only matched `flag -X (--Y) needed`.** Broadened to take any
   `--long` from a line containing "needed" or "should be given", which covers all
   four phrasings.
2. **It re-added the same flag.** For `sliding`, the first `--long` on the line was
   always `--step`, so the probe emitted `--step` five times and never found
   `--window`. It now skips candidates already present.

After both fixes the probe found required flags on **10 subcommands** (up from 3),
and the rate went **33% → 46%**.

### Remaining seqkit failures are structural, not converter bugs

`seqkit common` and `seqkit concat` need **two or more files**; `seqkit pair` takes
its inputs as flags rather than a positional argument; `seqkit convert` only works
on **FASTQ** and the fixture is FASTA; `seqkit bam` needs BAM. A one-fixture,
one-positional-input smoke test cannot exercise those, and forcing it would not
tell us anything true. They stay as contracts.

## 10. Third suite: seqfu (3 → 23 nodes)

seqfu is **not cobra** — it is Nim, and its help style differs in three ways that
each silently broke the parser:

| | cobra | seqfu |
| --- | --- | --- |
| Flag section | `Flags:` | `Options:`, and also arbitrary headings like `Name and comment search:` and `Input files:` |
| Default | `(default X)` | `[default: X]` |
| Value type | Go type (`int`, `strings`) | uppercase metavar (`MODE`, `INT`, `R1`) |

The third difference mattered most: gating the flag parse on a known section header
meant **every flag under a custom heading was dropped**, so `grep`, `orf`, `rotate`
and `trim` looked flagless and were skipped. Parsing now starts immediately and
relies on the flag-line pattern itself, stopping only at the inherited-global
section.

seqfu also has **no output flag** — it writes to stdout, and the existing owners use
`STDOUT_OUTPUT_INDEX = 0`. The generator now supports `--output-flag=` (empty) and
sets that attribute instead.

| Metric | Value |
| --- | --- |
| Subcommands found | 28 |
| **Nodes generated** | **20** |
| Skipped — already hand-written | 3 (`count`, `list`, `stats`) |
| Skipped — non-data | 3 (`less`, `msa`, `view`) |
| Skipped — no flags after the fix | 2 (`deinterleave`, `interleave`) |
| seqfu project-wide | **3 → 23 nodes** |
| Smoke rate | **15 / 20 (75%)** |

Remaining failures are structural again: `tofasta` takes an output **directory** as a
second positional, `amplicheck` needs two FASTQ files, `metadata` needs a directory,
and `check`/`tabcheck` need specific input types.

## 11. Where this leaves the catalog

| | Before this work | Now |
| --- | --- | --- |
| Builtins | 996 | **1258** |
| EMBOSS | 3 | 169 |
| csvtk | 3 | 48 |
| seqkit | 8 | 39 |
| seqfu | 3 | 23 |
| Nodes with `KNOWLEDGE` | 35 | 310 |

One generator, `scripts/generate_subcommand_nodes.py`, now covers three different
help dialects across three tools, driven entirely by CLI flags.

## 12. What this is and is not

**Is:** real, lint-clean, discoverable nodes with upstream-declared parameters,
including those that correctly demand a user-supplied value.

**Is not:** verified operations. There is **no independent oracle** for any
generated node, so no biological or numerical correctness has been established.
`executable_admitted` in the ledger is unchanged.

## 13. Next

`seqkit` (8 nodes, ~30 subcommands) and `seqfu` (3 nodes, ~20 subcommands) are the
same shape and use the same cobra help format, so `generate_subcommand_nodes.py`
should apply to them with only the fixture and binary changed — roughly 40 further
nodes available for one probe run each.

*(seqkit done — §9. `seqfu` remains.)*

Reproduce:

```sh
docker run --rm --network none -v "$PWD/artifacts/csvtk-help:/out" \
    --entrypoint sh quay.io/biocontainers/csvtk:0.31.0--h9ee0642_0 -c \
    'csvtk --help | sed -n "s/^  \([a-z0-9][a-z0-9-]*\)  .*/\1/p" | sort -u > /out/_subcommands.txt;
     while read -r s; do csvtk "$s" --help > "/out/$s.txt" 2>&1; done < /out/_subcommands.txt'
python scripts/generate_subcommand_nodes.py --help-dir artifacts/csvtk-help --binary csvtk \
    --family bionodulo/nodes/builtin/csvtk_family \
    --manifest reports/node-expansion/csvtk-generated.json \
    --snapshot reports/biotools_registry/current/registry.jsonl \
    --commit v0.31.0 --required-dir artifacts/csvtk-required
```
