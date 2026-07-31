# Node audit prompt

Prompt for an AI auditing or rebuilding nodes in the BioNodulo catalog. Every
rule below exists because that exact failure shipped and was found only by a
full cloud run — not by the test suite, and not by reading the node.

---

## Mission

Audit node `<NODE_ID>` (or the family `<FAMILY>`). Decide whether it can
actually run, and fix it or deprecate it. A node that cannot run must not sit
in the catalog looking runnable.

You are done when you have **executed the node's real command against real
data** and seen real output. Reading the source is not evidence. A passing unit
test is not evidence — every bug listed here passed its unit tests.

## Hard rules

1. **Verify, never assume.** If you assert a tool is on PATH, a package exists,
   a URL resolves, or a version is current, you must have run the command that
   proves it and shown the output. "Should work" is not a finding.
2. **Report what you find, including the inconvenient.** If a node cannot be
   made to work, say so plainly and say why, with the evidence. Do not quietly
   narrow scope, and do not leave a broken branch in place as decoration.
3. **Absence of an error is not success.** See "Evidence traps" below — several
   of our logging and env-reading paths return empty on success *and* failure.
4. **Do not change a pinned VERSION / GIT_COMMIT casually.** They are asserted
   by family tests and the catalog ledger. Changing one means regenerating
   catalog artifacts and updating those tests in the same commit, with the
   reason in a comment.

## Per-node checklist

### A. Is the tool obtainable at all?

Before anything else, prove an automated pipeline can get the binary:

- Does a conda package exist? Check conda-forge **and** bioconda by name — do
  not trust `EXECUTABLE_TO_CONDA_PACKAGE`; an empty string there means "no
  package", which is a claim to re-verify.
- If no conda package: does the vendor publish a **release asset**? Fetch the
  release API and read the asset list. An empty asset list means there is
  nothing to download.
- If an asset exists, is it **extractable**? A `.dmg`, `.exe`, self-extracting
  `.sh` installer, or Docker image is not usable by a workflow. You need a
  tarball/zip that yields the binary directly.
- If a launcher script exists, read it. Ours ended in
  `exec java -jar iBioSim.jar` with no arguments — that is a GUI, not a CLI.
  Check it accepts the arguments the node passes, headlessly, with no display.

If all of these fail, the node cannot run. Deprecate it with
`DEPRECATED = True` and a `DEPRECATION_MESSAGE` naming exactly what you checked
and what was missing. Do not delete it — saved workflows still need to load.

> Real cases: Cello publishes no asset anywhere (empty list, no JAR, no conda
> package, Docker-only). iBioSim ships a 150 MB zip with a GUI-only launcher.
> Both had full node implementations and passing tests.

### B. Is the pinned version the one that ships a usable artifact?

The newest release is not always the usable one. COPASI Build-300 publishes
only bindings, a `.dmg`, an `.exe` and a self-extracting installer; Build-298
publishes `COPASI-4.45.298-AllSE.tar.gz`. Pin to the newest release with an
extractable binary and **write the reason in a comment**, or someone will
"helpfully" bump it forward and break provisioning.

### C. Declared vs provisioned

A node that lists `REQUIRED_EXECUTABLES` with no conda package and no
`ENVIRONMENT` provisioning spec will never have that binary on PATH. Check
`spec_for(NodeClass)` returns something for any executable whose
`EXECUTABLE_TO_CONDA_PACKAGE` entry is `""`.

For vendor archives, set `executable_path` **explicitly**. Multi-platform
archives contain the same filename under `Linux64/`, `Linux/`, `Darwin-arm/`,
`Darwin-intel/`, `WIN*/` — a search is free to pick the wrong one.

### D. Planned path vs command path

The single highest-frequency bug in this catalog.

- `PLAN_OUTPUTS` receives the **run root** and appends `NODE_ID` itself.
- `render_command` receives `output` **already set to `<run>/<NODE_ID>`**.

Appending `NODE_ID` again in `render_command` produces
`.../starsolo_count/starsolo_count/`. The tool exits 0, writes everything to
the wrong directory, and the node fails on missing planned outputs — after
paying for the full compute.

**Write a test that asserts the planned path string appears in the rendered
command.** Not that both are "reasonable" — that they are the same path. This
class has now hit `starsolo_count`, `metaphlan`, and `krona`.

### E. Under-declared transitive dependencies

Your dev box has system packages that the locked environment does not. Solve
the lock in a **clean pixi environment** and import/run the tool there.

> `pysbol3` → `pyshacl 0.18.1` → `import pkg_resources` → removed by
> `setuptools 81`. The node declared only `pysbol3` and died with
> `ModuleNotFoundError` before reading a single file. The fix was pinning
> `setuptools` **backwards**, because `pysbol3` hard-pins `pyshacl` and the
> solver refuses to move it forward.

Also check the executable→package alias table: `bunzip2` ships in `bzip2`,
`RRA` and `mageckGSEA` ship in `mageck`. An unmapped binary name becomes an
unsolvable dependency that a dev box hides by resolving from `/usr/bin`.

### F. Tool version vs reference data version

Tools reject data from the wrong database generation, and the error only
appears at run time.

> HUMAnN 3.9 accepts a taxonomic profile **only** from MetaPhlAn database v3 or
> vJun23. Our pipeline fed it a profile from the vJan21 TOY database and got
> "not generated with the database version v3 or vJun23". The real vJun23 index
> is ~20 GB, so the answer was a v3-era profile matching the DEMO database we
> already fetch — not a bigger download.

State the acceptable data versions in the node docstring or template note.

### G. Does the data actually produce a result?

A pipeline can be wired perfectly and still yield nothing.

> SARS-CoV-2 reads against a DEMO database containing two *Bacteroides* species
> map nothing. The run "succeeded" with empty output.

Demo data must match the reference the node uses. Verify a non-trivial result
(counts > 0, non-empty matrix, more than a header row), not just exit 0.

### H. Exit 0 is not success

Add `VERIFY_OUTPUTS` that fails on empty/degenerate output: a zero-cell matrix,
a report with only a header, a FASTA with no records.

> CopasiSE exits 0 having written **no report at all** unless a task is
> scheduled — an imported SBML model defines no report output. `--scheduled-task
> Time-Course` is what makes the file exist.

Never publish to a shared cache before verification. We published a reference
build on exit 0, and one bad build poisoned that reference permanently for
every user, with no self-repair because staging skipped the rebuild.

### I. Environment assumptions

Do not assume paths without spaces, a writable HOME, a display, or network at
run time. A path containing a space broke `bowtie2`'s perl wrapper
(`Can't exec "/home/mika/Downloads/Bionodulo"`). Test from a path that differs
structurally from the dev checkout.

## Evidence traps

Absence of evidence is not evidence in this codebase:

- Module-level `logger.info` **never reaches** `workflow_runs.logs`.
- Run logs are **truncated** — a missing line may simply be cut off.
- `vercel env pull` returns `""` for sensitive variables whether or not they
  are set.
- `--check` on generated artifacts is **order-dependent**: `compile_catalog`
  digests `node_metadata.json`, so `gen_node_index` must run first or the
  check reports STALE on freshly written files.

Before concluding "there is no log line, so it did not happen", prove the log
path can carry that line at all.

## Deployment reality

A new or changed node needs **both** the worker image and the editor Lambda
image rebuilt. The editor serves the catalog used by preflight; if it is stale,
`POST /api/runs` rejects the workflow with "uses unregistered type '<id>'"
before anything provisions. Also: `WORKER_APP_COMMIT` ≠ `BIONODULO_APP_COMMIT`,
and the app commit must be **pushed** before deploying — the site build clones
it and fails with git exit 128 otherwise.

## Output format

For each node audited, report:

| field | content |
|---|---|
| verdict | `works` / `fixed` / `cannot run — deprecate` |
| evidence | the command you ran and the real output proving the verdict |
| bug class | which section above it hit, if any |
| changed | node source / env contract / template data / nothing |
| residual risk | what you could not verify and why |

If the verdict is `cannot run`, state exactly what you checked to establish
that no artifact exists. A verdict of "probably fine" is not a verdict.
