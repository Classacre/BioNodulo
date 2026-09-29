# EMBOSS expansion: 166 nodes from the suite's own parameter definitions

**Date:** 2026-09-26
**Route:** hand-authored contracts, at scale, with real documentation, inputs,
modifiable parameters, outputs and citations — the route that worked.

**Result:** builtins **996 → 1162** (+166 EMBOSS programs, family total 169).
Three fix rounds took the measured run rate on random samples from **42.5% to 75%**.

---

## 1. Why EMBOSS

The gap analysis (`reports/node-expansion/gap-candidates.json`, 20,058 ranked
candidates) surfaced a pattern: `seqret`, `getorf`, `patmatmotifs`, `sixpack`,
`showorf`, `trimest`, `coderet`, `palindrome`, `prettyplot` — all EMBOSS programs,
and BioNodulo had exactly **three** EMBOSS nodes. 253 EMBOSS records sit in the
gap list, all documented at `emboss.open-bio.org`.

EMBOSS is the ideal family for this: one binary per program, one pinned container
for all of them, a single suite citation, and — decisively — **the suite ships
machine-readable parameter definitions**.

## 2. The authoritative source: ACD

Every EMBOSS program has an `.acd` file describing, in a formal grammar:

- the documentation string and functional group,
- every input and output parameter with its **type, required flag, default,
  minimum/maximum and human description**,
- **EDAM relations** (topic / operation / data) chosen by the EMBOSS authors.

That is exactly the four things an admission needs, plus verified ontology
annotations — and it is the upstream authors' own machine-readable statement, not
a scrape of prose. The 259 ACD files were extracted from the **digest-pinned**
`quay.io/biocontainers/emboss:6.6.0--h0f19ade_14`, so the parameter set is tied to
the same build the nodes declare.

## 3. What was produced

| Metric | Value |
| --- | --- |
| ACD programs seen | 259 |
| **Nodes generated** | **166** |
| Skipped — no file input (utility/config/database programs) | 90 |
| Skipped — already hand-written | 3 |
| Generated nodes carrying EDAM operations from the ACD | **166 / 166** |
| Nodes with `KNOWLEDGE` project-wide | 35 → **214** |
| Lint errors (25-node random sample) | **0** |

Each generated node carries the program's real documentation string, its typed
parameters with defaults and ranges, its declared outputs, a documentation URL on
`emboss.sourceforge.net`, the pinned container identity, the EMBOSS suite citation,
and the ACD's own EDAM topic/operation annotations.

Three fix rounds took the count from 136 → 150 → 166 and drove
`skipped_no_declared_output` to **zero**. One program was *lost* along the way —
`seqmatchall` declares only an `outfile` and takes its sequence from a hidden
standard parameter, so with correct classification it has no declared input. That
is the right outcome, not a regression.

## 4. Verification: it runs, and how often

Generation is not admission, so a random 40-node sample was executed through
`scripts/verify_emboss_nodes.py` — each node's **own** `render_command` argv, in
the digest-pinned image, with `--network none`.

| Round | Sample | Passed | Rate |
| --- | --- | --- | --- |
| First run (three generator bugs) | 40 | 17 | 42.5% |
| After the first fix round | 40 | 23 | 57.5% |
| After the section and verifier fixes | 40 | 24 | 60.0% |
| After the `seqset`/scalar/graph fixes | 40 | 30 | 75.0% |
| **Final, on an 80-node sample** | **80** | **61** | **76.3%** |

The 40-node samples use different random seeds, so the last two are not directly
comparable; the 80-node figure is the one to quote.

A node counts as passing only when it exits zero **and** produces every output it
declared. Exit status alone is not enough: `emboss_restover` exits 134 while
producing its file, and `emboss_seqretsplit` exits 0 while producing nothing.
Both are counted as failures.

### Failure taxonomy (19 of 80)

| Cause | Count | Fixable? |
| --- | --- | --- |
| Required parameter genuinely needs a user-supplied value (`-pattern`, a selection list) | 8 | **No — correct behaviour.** The node demands it; a smoke test with one fixture cannot supply it |
| Needs EMBOSS reference data (REBASE enzyme tables, vectors file, codon usage) | 4 | Needs provisioning |
| Other program-specific semantics | 4 | Per-program |
| EMBOSS crashes (`SIGSEGV`/`SIGABRT`) | 2 | No — upstream |
| Needs remote or installed reference data (timed out under `--network none`) | 1 | Needs provisioning |

The largest group is **not a defect**. `fuzznuc`/`fuzzpro`/`fuzztran` require a
`-pattern`; a node that demanded nothing and silently ran without it would be the
bug. The second largest needs EMBOSS's reference databases installed, which is a
provisioning question rather than a converter one.

That is a real shift from the earlier rounds, where most failures *were* converter
bugs. The converter is now good enough that the remaining failures are about the
programs themselves.

## 5. Bugs found and fixed in the generator

These are worth recording because each produced plausible-looking but wrong nodes:

1. **Wrong classification field.** The ACD *declaration kind* (`seqall`, `outseq`)
   is the datatype; the `type:` key inside the block is a sub-type hint
   (`gapany`). Reading the wrong one made all 259 programs look input-less.
2. **Missing output kinds.** EMBOSS names outputs by role, so `seqoutall` — not
   `outseq` — is what `seqret` and `getorf` declare. A fixed list missed 33
   programs; the reliable rule is the `out` substring plus a few roles.
3. **Required scalar parameters were never rendered.** Only optional ones were
   emitted, so `fuzznuc` died with `Bad value for '-pattern'`. Required
   non-file parameters now render.
4. **Plot qualifiers are not filenames.** `-graph <file>` is wrong; `-graph` takes
   a **device** and `-goutfile <basename>` supplies the name, yielding
   `<basename>.1.png`. Established by experiment in the container, not by guessing.
5. **`RETURN_TYPES` length.** Emitting a single `("DIRECTORY",)` for a multi-output
   node failed the linter; types must be one per output.
6. **Self-collision.** The skip-set globbed `emboss_*.py`, so hand-written
   `pepstats.py` and generated `emboss_pepstats.py` both claimed one `NODE_ID`.
   Generated files are now identified by a marker.
7. **`outfile` was listed as an input kind.** It is an output. Listing it as an
   input made `needle`, `water` and `seqmatchall` look output-less, so the two
   flagship EMBOSS alignment programs were silently dropped from the first pass.
8. **Sections were mis-parsed, and they are the only reliable disambiguator.**
   An ACD section is not a bracketed block: `section: name [ ... ]` holds only the
   section's *attributes*, and the parameters follow after that closing bracket.
   Treating the `]` as the end of the section meant no parameter ever knew its
   section. That mattered because EMBOSS reuses one kind for both roles —
   `water` declares its alignment output as `align: outfile` inside
   `section: output`, which a kind-only rule reads as an *input*.
9. **The verifier injected the fixture into optional inputs.** `needle`, `water`,
   `matcher` and `stretcher` have an optional `-datafile` that is a substitution
   matrix, not a sequence; handing it DNA produced `Unable to read matrix`. Only
   inputs the program actually requires are filled now.
10. **A hung tool aborted the whole batch.** `taxgetdown` fetches taxonomy data
    and never returns under `--network none`; the unhandled `TimeoutExpired` killed
    the run and discarded every earlier result. Timeouts are now recorded as a
    result per node.
11. **`matrix` was listed as an output kind.** EMBOSS uses `matrix` for the
    *scoring matrix input* in `dotmatcher`, `prettyplot` and `showalign`, so a
    kind-only rule rendered `-matrixfile <output path>` and the tool died with
    `Unable to read matrix`. It is section-driven now.
12. **Unknown kinds were dropped instead of treated as scalars.** Returning
    `"other"` discarded required parameters such as `fuzznuc`'s `-pattern`, and a
    node that omits a required qualifier fails deep inside the tool with a
    confusing message instead of failing validation up front. Unknown kinds are now
    scalars, so required ones render and the node demands a value.
13. **`seqset` was missing from the input kinds.** `needleall` declares
    `seqset: asequence`, which classified as unknown and left the program with no
    primary input at all. Adding `seqset`/`seqsetall` recovered 16 programs.
14. **Graph outputs are unreliable and should not be required.** `-graph png
    -goutfile x` yields `x.1.png` for `banana` but writes nothing at all for
    `charge`, with both exiting zero. A plot is now declared as an output only when
    the program has no other output; otherwise the report is the contract and the
    plot is still requested (so EMBOSS does not fall back to an interactive device
    and hang) without being required.

## 6. Registration

The 166 ids live in `bionodulo/nodes/generated/emboss_node_ids.json`, and
`compile_catalog.py` reads that file rather than holding a literal. A
hand-maintained list drifts the moment the generator changes which programs it can
express; the count now follows the generator. `BASELINE_NODE_COUNT` stays 943 as
forensic history.

Three traps hit while wiring this up:

- A helper used inside the `POST_BASELINE_NODE_IDS` set literal must be defined
  **above** it, or the module raises `NameError` at import.
- When the generator's id set changes, `node_metadata.json` can retain a key the
  index no longer has (`emboss_seqmatchall`), and `compile_catalog.py` rejects the
  mismatch with *"legacy node metadata IDs differ from the forensic baseline"*.
  Deleting both generated JSON files and regenerating resolves it.
- The sandbox **blocks bulk deletion at roughly 50 files per turn**, so a
  cleanup-and-regenerate can silently leave stale modules behind and produce an
  orphan. Verify the file count after any regeneration.

`gen_node_index.py --check` and `compile_catalog.py --check` are both clean at
**1162 nodes**; **345 tests pass, 10 skipped**; 25/25 sampled nodes lint clean.

## 7. What this is and is not

**Is:** 166 real, lint-clean, discoverable nodes with upstream-authored
documentation, typed parameters, declared outputs and EDAM annotations, tied to a
pinned container, of which a measured **76.3%** actually run on a DNA fixture.

**Is not:** 136 verified operations. There is **no independent oracle** for any of
them, so no biological correctness has been established. They are contracts, and
the generated module docstring says so in the file itself. `executable_admitted`
in the ledger is unchanged.

## 8. Where the next yield is

The same method applies wherever an upstream project publishes formal parameter
definitions — that is the difference between this and the Galaxy wrapper route,
which failed because Galaxy wrappers are *programs for a runtime* rather than
declarations. EMBOSS had one container and 259 declarative programs. The
`EMBOSS`-style pattern (single binary per operation + machine-readable parameter
file) is the highest-yield target; suites with Cheetah-style templating are not.

Reproduce:

```sh
export PYTHONPATH="$PWD"
docker run --rm -v "$PWD/artifacts/emboss-acd:/out" --entrypoint sh \
    quay.io/biocontainers/emboss:6.6.0--h0f19ade_14 \
    -c 'cp /usr/local/share/EMBOSS/acd/*.acd /out/'
python scripts/generate_emboss_nodes.py --acd-dir artifacts/emboss-acd \
    --nodes-dir bionodulo/nodes/builtin/emboss_family \
    --manifest reports/node-expansion/emboss-generated.json \
    --snapshot reports/biotools_registry/current/registry.jsonl
python scripts/verify_emboss_nodes.py --manifest reports/node-expansion/emboss-generated.json \
    --nodes emboss_seqret,emboss_getorf,emboss_sixpack \
    --fixture tests/nodes/emboss_family/fixtures/dna.fasta \
    --image quay.io/biocontainers/emboss:6.6.0--h0f19ade_14 \
    --digest sha256:a9bf499a690de7950a3f553793ea45daa947c63946a43edaefdbcfb0e9960a97 \
    --receipt-dir reports/run-receipts/emboss-batch
```
