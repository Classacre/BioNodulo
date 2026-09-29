# Galaxy ingestion: measured findings

**Date:** 2026-09-26
**Question asked:** hand-curate nodes until BioNodulo rivals Galaxy's tool count.
**Answer:** not reachable by importing Galaxy's tools, and the reason is structural,
not a matter of effort. This report is the measurement behind that claim.

---

## 1. The goal I set, and what the baseline actually is

| Ecosystem | Count | What it really measures |
| --- | --- | --- |
| Galaxy ToolShed | **7,912** repositories | Every uploaded wrapper, including duplicates, abandoned uploads and trivial shells |
| Galaxy curated wrappers | **2,865** | tools-iuc 2,549 + galaxy main 172 + tools-devteam 144 |
| BioNodulo executable builtins | **996** | Hand-authored contracts with ports, runtimes and citations |
| BioNodulo reference definitions | **34,248** | `biotools_<hex>` definitions; **execution is refused by design** |

So on *discoverable definitions* BioNodulo already exceeds Galaxy more than
fourfold (34,248 vs 7,912). The gap is **executable depth**: 996 vs ~2,865 curated
wrappers.

**Goal set:** close that executable gap by importing Galaxy's own wrapper corpus
rather than hand-writing thousands of node classes.

## 2. What was built

Three scripts, all committed and re-runnable:

| Script | Purpose |
| --- | --- |
| `scripts/fetch_galaxy_wrappers.py` | Extracts tool XML from a Galaxy repo without a working-tree checkout |
| `scripts/analyze_galaxy_wrappers.py` | Source-shape census of wrapper features |
| `scripts/convert_galaxy_wrappers.py` | Macro-resolving conversion census, with optional node emission |

A working-tree checkout of tools-iuc **fails on Windows**: Galaxy test data
legitimately contains filenames like `input.chrM:4000-8300.bam` and
`transcriptome?02.fasta`, which are invalid paths here. The fetcher reads the git
tree and pulls only XML blobs, so those paths are never materialised. Two bugs were
fixed en route: `subprocess.Popen` does not accept `timeout`, and writing 2,549
requests before reading any response **deadlocks** on a full stdout pipe (fixed by
chunking at 64).

## 3. The measurement

tools-iuc at `3b33d7ed516b50878d74fe28b0bb929cb7c89a1d`:

| Stage | Count |
| --- | --- |
| XML files under `tools/` (excluding test-data) | 2,549 |
| …that are actually tool wrappers (have a tool id) | **2,053** |
| …importing a `<macros>` file | **2,472** |
| …using `<expand …>` | 1,815 |
| …with Cheetah control flow in `<command>` | **1,433** |

Macro resolution was implemented before judging anything, because requirements and
inputs routinely live in `macros.xml` and a naive parser sees almost nothing. With
macros resolved:

| Conversion outcome | Count | Why |
| --- | --- | --- |
| **executable** (static argv possible) | **84** | — |
| definition (command uses Cheetah control flow) | **1,433** | argv depends on parameter values |
| definition (no conda requirement or container to pin) | 442 | no runtime to bind |
| definition (no statically declared input/output pair) | 79 | — |
| rejected (not a tool wrapper) | 496 | macros/library files |
| rejected (no command) | 11 | — |
| rejected (XML parse error) | 4 | — |

## 4. And then the 84 collapsed too

Inspecting the 84 "executable" wrappers:

| Defect | Count |
| --- | --- |
| Command contains shell operators (`&&`, `\|`, `>`, `;`) | **34** |
| Command invokes a helper script shipped in the wrapper repo | **29** |
| Duplicate input port names (nested/macro XML not flattened) | **66** |
| **Clean single-argv, no helper script, no duplicate ports** | **11** |

And of those 11, **10 are one tool family** (`enzywizard_*`). Command first-tokens
across the 84: `python` 13, `Rscript` 9, unresolved `@CMD_LINK_INPUT_NAME@` 8,
`cp` 4, `cat` 3 — the "tool" is usually a script shipped alongside the wrapper,
not a binary in a container.

**Honest yield of importing 2,549 Galaxy wrappers: 0 verified executable
operations, and at most 11 unverified contracts.**

I emitted the 84 as nodes to test the pipeline, then **deleted them**. They failed
to load (my base class declared `RETURN_NAMES` as a method where the registry
expects a tuple) and 66 carried malformed ports. Shipping them would have been
exactly the count-inflation this project's own playbook forbids. The tree is back
to a clean 996 nodes with the index, catalog and tests passing.

The shared base adapter written for the attempt (`_galaxy_wrapped_adapter.py`) was
removed too. Its design was proven inadequate by the defects above — it assumed one
port per name and a shell-free argv, neither of which Galaxy wrappers guarantee.
An unused, untested, known-broken module in the tree is a liability, not
scaffolding; §5 lists what a correct one would actually have to do.

## 5. Why the ceiling is structural

A Galaxy tool wrapper is **not a tool definition. It is a program for Galaxy's
execution engine.** Copying the file does not copy the engine. To run the 1,433
Cheetah-conditional wrappers you would need to reimplement, at minimum:

1. **The macro system** — `<token>`, `<xml>`, `<expand>`, recursive imports.
2. **A Cheetah evaluator** — `#if`/`#else`/`#for`/`#set` over Galaxy's parameter
   model, including nested conditionals and repeats.
3. **Galaxy's input model** — `data`, `data_collection` (list/paired/list-of-pairs),
   `select`, `conditional`, `repeat`, and their runtime value semantics.
4. **A conda → container resolver** — only 14 of 2,549 wrappers declare a
   `<container>`; the rest declare conda packages and Galaxy resolves the image
   separately through BioContainers, pinning by build hash.
5. **Helper-script staging** — 29 of the 84 need scripts that live in the wrapper
   repository, not in the image.
6. **Test-data extraction** — 2,002 wrappers carry `<tests>` with real inputs and
   expected outputs, which is genuinely valuable, but reading it requires all of
   the above.

That is Galaxy's 15-year-old tool-parsing layer. It is a multi-week engineering
project, not a session task, and no amount of parallel agents substitutes for it —
the work is per-tool semantic resolution, not per-tool typing.

## 6. What this means for the goal

**Rivaling Galaxy's executable count by import is not achievable, and the 10k
figure is misleading.** Galaxy's number counts wrappers in a format that only
Galaxy can execute. Two ecosystems can both have "10,000 tools" while one of them
cannot run a single one of them elsewhere.

The three honest routes, in descending order of value per unit of effort:

1. **Keep doing what worked.** Hand-authored operations with a real run and an
   independent oracle. This session added 13 that way, plus 7 verified in a pinned
   container. That is slow but it is the only route that produces capability rather
   than a number.
2. **Build the Cheetah + macro + conda-resolver layer.** This is the only path that
   would unlock the 1,433 conditional wrappers, and it is a real project. It should
   be scoped as one, with the census in §3 as its success metric: if it cannot move
   `executable` from 84 to >1,000 on tools-iuc, it is not working.
3. **Import wrappers as definitions only** — discoverable, clearly labelled,
   execution refused, exactly like the existing 34,248 `biotools_` definitions.
   Cheap, honest, and adds nothing to executable capability.

What I would **not** do is generate thousands of nodes that render an argv no
container can satisfy. That would raise the count and lower the truth.

## 7. What was actually delivered

- **3 committed scripts** forming a working, re-runnable Galaxy ingestion pipeline.
- **A dated, reproducible census** of 2,549 wrappers with the full tier breakdown
  (`reports/galaxy-ingestion/wrapper-analysis.json`, `conversion.json`).
- **A named blocker per wrapper**, so any future attempt starts from evidence
  rather than from a fresh survey.
- **No change to the node count.** It remains 996. I did not inflate it, and I
  think that is the correct outcome to report.

Reproduce:

```sh
export PYTHONPATH="$PWD"
git clone --depth 1 --no-checkout https://github.com/galaxyproject/tools-iuc.git artifacts/galaxy-tools-iuc-full
python scripts/fetch_galaxy_wrappers.py --repo artifacts/galaxy-tools-iuc-full \
    --output-dir artifacts/galaxy-wrappers --manifest artifacts/galaxy-wrappers-manifest.json
python scripts/analyze_galaxy_wrappers.py --wrappers-dir artifacts/galaxy-wrappers \
    --manifest artifacts/galaxy-wrappers-manifest.json \
    --output reports/galaxy-ingestion/wrapper-analysis.json
python scripts/convert_galaxy_wrappers.py --wrappers-dir artifacts/galaxy-wrappers \
    --manifest artifacts/galaxy-wrappers-manifest.json --output-dir reports/galaxy-ingestion
```
