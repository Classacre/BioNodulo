# BioNodulo Code Audit — `optimbionodulo`

Date: 2026-06-13. Scope: full-app audit (execution engine, AI assistant, frontend,
node system & bioinformatics correctness, API & security, environments/HPC/converters),
plus a prioritized remediation plan. Baseline health: backend imports clean; frontend
`tsc --noEmit` clean; pytest **1443 passed, 5 failed** (all CWL export — root cause below).

The goal of this branch: make BioNodulo a genuinely bioinformatics-native workflow
manager that matches or beats Snakemake/Nextflow on performance, and turn the AI
assistant into an autonomous agent (paper-reproduction, auto-debug, workflow optimization).

---

## Headline verdict

The codebase is large (≈72k LOC Python, ≈55k LOC TS) and surprisingly complete in
breadth (≈360 nodes, real converters, env isolation), but it is held back by four
load-bearing problems:

1. **The execution engine is serial.** It topo-sorts the DAG then runs nodes one at a
   time in a `for` loop. Independent branches do not run concurrently. This alone makes
   it non-competitive with Snakemake/Nextflow.
2. **The cache is not content-addressed.** It keys on file *paths*, not contents/tool
   versions — so it returns stale results when a file changes in place. This is a
   scientific-correctness hole, not just a perf miss.
3. **The AI assistant is ~15% of the stated vision.** It is a 6-round ReAct chatbot that
   can *draft* graph edits but cannot run workflows, read logs, install anything, write
   nodes, search papers, or download data — and has no subagents and no autonomous loop.
4. **The API is unauthenticated by default for dangerous endpoints.** Workflow execution
   (arbitrary shell), the workspace file browser, and package/git install are reachable
   with no auth unless `collab.enabled` is flipped on.

Everything below is organized so the highest-leverage, lowest-risk fixes come first.

---

## 1. Execution engine (`bionodulo/execution/`, `bionodulo/workflow/graph.py`)

**Verdict:** Not competitive as-is. Correct-ish but serial, with a stale-cache hazard,
inside a 3,308-line god-object (`executor.py`).

**Critical**
- **No DAG parallelism.** `execute()` iterates `execution_order` sequentially
  (`executor.py:376`); the topo sort (`executor.py:2979`, `graph.py:121`) flattens the
  DAG and discards wave/level info. The only intra-run concurrency is the explicit
  `ParallelFor` node. → wave/ready-set scheduler with `asyncio.TaskGroup` + `Semaphore`.
- **Cache keys on paths, not content.** `cache_key_for_node` (`cache.py:103-114`) hashes
  `node_type + params + input *paths* + upstream_keys`; no file content/mtime/size, no
  tool version (only `sha256` use in the package). Editing an input in place → false hit
  → stale output. → hash file contents (or size+mtime fast tier) + tool version.
- **Sync `node.run()` blocks the event loop.** `_execute_node` (`executor.py:2779-2782`)
  calls a non-coroutine `run()` inline; a CPU/IO-bound node freezes the server, WS emits,
  and the queue. → `await asyncio.to_thread(...)`.

**Major**
- `executor.py` god-object: scheduling, caching, key derivation, input resolution,
  loop/while/parallel-for/try-catch interpreters, checkpoint/resume, dry-run, previews,
  artifacts, env isolation, retry — one class. `execute()` ≈615 lines.
- No subprocess resource limits / sandbox (`subprocess_runner.py`): no rlimit/cgroup/nice;
  a runaway tool can OOM the host. (Output streaming itself is well done.)
- Repeated O(E) graph scans: `_build_adjacency`/`_build_indegree` (`graph.py:99-118`) and
  `_upstream/_downstream_closure` rebuild maps per call; `_find_loop_body`
  (`executor.py:1396`) scans all edges per node.

## 2. AI assistant (`bionodulo/ai/`) — owner's #1 priority

**Verdict:** A competent single-agent read-mostly chatbot, ~15% toward the three goals
(autonomous debug, paper-reproduction, autonomous optimize).

**What exists:** 6-round ReAct loop (`assistant.py:436` `MAX_TOOL_ROUNDS=6`) on a trivial
2-node LangGraph (`assistant.py:668`); 24 tools (`tools.py:616`), all read-only or
*draft-only* graph edits (applied only via UI "Apply", `assistant.py:573`); history trim
+ tool-result truncation (good); `/ai/chat` + a fake `/ai/chat/stream` that replays steps
after the blocking loop (`ai_routes.py:113`). Stale model defaults (`gpt-4.1-mini`,
`claude-3-5-sonnet-20241022`).

**Critical gaps:** Cannot **run** a workflow, **read run logs** as a tool
(`get_run_history` is a stub returning `[]`, `tools.py:599`), **install** deps, **write**
nodes, **search** the web/papers (PubMed exists only as a *node*, not an AI tool), or
**download** datasets. No subagents, no autonomous run→diagnose→fix loop, no real
streaming. The full `/runs`, `/runs/{id}/logs`, `/runs/{id}/retry` REST API already
exists and is simply not wired to the assistant.

**Target architecture:** an orchestrator + tool-rich executor agent with an explicit
verify→debug cycle (run → on failure fetch logs → diagnose → edit → re-run, budgeted),
parallel subagents for paper-reproduction (DatasetAgent / WorkflowBuilderAgent /
NodeAuthorAgent), a paper-parsing pass → typed `ReproductionPlan`, real token streaming,
and per-task model routing.

## 3. Frontend (`web/src/`)

**Verdict:** Architecture is sound but leaks performance and maintainability. The canvas
*can* scale to low-thousands of nodes; the un-virtualized DOM overlay undermines it.

- **`App.tsx` god-component** (3,373 lines; 59 `useCallback`/30 `useMemo`/26 `useEffect`):
  owns collab, history/undo, run submission, panel layout, subgraph nav, command palette,
  and the whole shell render. Decompose into `useCollabSession`, `useWorkflowHistory`,
  `useRunController`, `useAppCommands`, `useSubgraphNavigation`, `AppShell`.
- **Canvas** (`WorkflowCanvas.tsx`): hybrid Canvas2D (grid/edges/bodies, with viewport
  culling `:897`, transform pan/zoom) + DOM overlay for widgets/previews/cursors. The DOM
  overlay does `graphNodes.filter().map()` over **all** nodes with **no `React.memo`** and
  **no virtualization** (`:3291,:3331,:3370`); `WorkflowCanvas` itself is not memoized
  (`:3964`), so every `App` re-render re-renders it. HTML-preview iframes per node are a
  hard ceiling.
- **Tailwind configured but used in 2/62 files**; real styling is a 4,028-line `index.css`.
  Pick one. **React Compiler not enabled** — the single cheapest win (auto-memoizes).
- **Triple state copy**: graph truth in `useWorkflow` `useState`, mirrored into Yjs, plus
  history — feedback-loop guards (`suppressLocalSeed`, `isDraggingRef`) are a symptom.

## 4. Node system & bioinformatics correctness (`bionodulo/nodes/`)

**Verdict:** Solid ComfyUI-derived abstraction (~360 nodes), mostly-correct commands, but
several real bugs and a reproducibility gap.

- **Bio command bugs (correctness):**
  - **cuteSV malformed** (`variant.py:918`): emits `--genome/--sample` which are not valid
    flags and wrong positional order → fails. (SVIM nearby is correct.)
  - **BWA-MEM** (`alignment.py:101-114`): `-T 30` hardcoded as a mislabeled "min_score"
    silently drops alignments; `-M` placed after positionals (works under shell only).
  - **`samtools merge`** input typed singular `BAM` (`samtools.py:487`) — multi-BAM merge
    is fragile; no list type.
  - **Missing reference prep:** nothing runs `samtools faidx` / GATK
    `CreateSequenceDictionary`; callers (`variant.py:1842`, mpileup, Mutect2) need
    `.fai`/`.dict` → runtime failures.
  - **VCF_GZ not tabix-indexed:** most callers emit `.vcf.gz` without `tabix`; chained
    variant workflows break (only `delly_call` indexes).
- **Type system** (`types.py`): bio-aware directed compatibility graph (good), but rich
  BioTypes collapse to `"STRING"` sockets in the UI (`registry.py:524`) and `INDEX_DIR`
  is one generic type for non-interchangeable BWA/Bowtie2/STAR/Salmon indices.
- **Reproducibility gap:** per-node `VERSION` is cosmetic; manifest pins are `>=`/`*`, not
  exact. Reproducibility depends entirely on retaining `pixi.lock`.
- **n8n/ComfyUI smells:** positional output tuples force post-`run` file-rename shims
  (`alignment.py:576`, `rna_seq.py:119`); paired-end reads crammed into one `FASTQ_LIST`
  port; declarative `schema_api.py` is unused.

## 5. API & security (`server.py`, `bionodulo/api/`, `core/`)

**Verdict:** Effectively unauthenticated by default for dangerous endpoints. Intended as a
local single-user tool, but `CORS=*`+credentials and a public-tunnel collab feature make
accidental exposure catastrophic.

- **CRITICAL — Unauthenticated RCE** via `POST /api/runs` / `/api/hpc/submit`:
  `_require_execute_permission` is a no-op when `collab.enabled` is false
  (`routes.py:247-256`); submitted workflows run shell commands.
- **CRITICAL — No-credential token mint**: `POST /api/auth/token` issues a 24h editor JWT
  for any `name` (`auth_routes.py:17-32`).
- **CRITICAL — Path-traversal root reset**: `POST /api/workspace/root` (unauth) sets
  `project_root` to any path (`routes.py:1160`); set it to `/` → whole-FS read/write/delete
  via the file routes.
- **CRITICAL — SSRF**: `http_request` node (`http_request.py:197`) takes a fully
  user-controlled URL, follows redirects, reaches `169.254.169.254`/loopback/RFC-1918.
- **High:** `ensure_within` symlink-trustful (`paths.py:41`); unauth git clone / pkg /
  pixi install (`routes.py:1384,1442,1528`); LLM API key stored plaintext at rest
  (`config.py:242,280`) — responses *are* redacted (good).
- **Medium:** `CORS=*` + credentials and `--cors-origins` parsed but never wired
  (`server.py:156`, `main.py:30`); slowapi applied to only 3 endpoints; WS has no
  backpressure. `routes.py` is a 2,271-line monolith; blocking FS I/O in async handlers.

## 6. Environments / HPC / converters

**Verdict:** Env isolation + resolver are genuinely good; HPC is a façade; converter
*export* is real, *import* is shallow regex.

- **CWL export bug (the 5 failing tests):** `cwl_converter.py:265` hardcodes
  `["python3", "-m", ...]`; under the project venv `bionodulo` isn't importable by the
  bare `python3` on PATH → `ModuleNotFoundError` → returncode 1. **Fix:** use
  `sys.executable`. (Sibling `test_cwl_node_runner_*` tests already use `sys.executable`.)
- **Env isolation (strong):** content-addressed per-workflow pixi envs (`manifest.py:40`),
  manifest→lock→install sequencing, stale-lock deletion. Pins are floor-only (`>=`/`*`).
- **Resolver (good):** node types deduped + resolved concurrently (`resolver.py:374`);
  conflict-solving delegated to `pixi lock` (reasonable).
- **Installer (risk):** `install_managed_pixi` pipes `https://pixi.sh/install.sh` to
  `bash` with no checksum/version pin (`runtime_installer.py:129`) — supply-chain hole.
- **HPC (façade):** correct SLURM/PBS/SGE *script generators*, but `submit_job` accepts
  `dependency/array/hold` that nothing ever passes; the executor never imports the HPC
  backends. No per-node DAG→job mapping, no `afterok` chaining. This is the biggest gap
  vs Snakemake/Nextflow cluster executors.
- **Converters:** export builds real rule/process graphs and raises on unsupported nodes;
  import (`snakemake/nextflow`) is a brittle line/regex scanner that mis-parses real
  Snakefiles/`main.nf` (no `expand()`, wildcards, includes, nested braces) and collapses
  edges to `"default"`.

---

## Prioritized remediation plan (this branch)

Ordered for value × confidence; each lands green and committed.

1. **Correctness quick wins** — CWL `sys.executable` (unblocks 5 tests); cuteSV/BWA/merge
   command fixes; wrap sync `node.run()` in `asyncio.to_thread`. *(S)*
2. **Parallel DAG scheduler** — ready-set + `TaskGroup` + `Semaphore`; the headline
   competitive feature. *(L)*
3. **Content-addressed cache** — hash contents + tool version; correctness + speed. *(M)*
4. **AI assistant overhaul** — run/logs/retry/edit/install/write-node/research/dataset
   tools; verify→debug autonomous loop; subagent orchestrator for paper-reproduction;
   refreshed models + real streaming. *(L)*
5. **Security hardening** — auth on execute/mutate/file routes regardless of collab; kill
   `/workspace/root`; SSRF egress guard; wire `--cors-origins`; secrets off plaintext. *(M)*
6. **Frontend perf** — enable React Compiler; memoize `WorkflowCanvas`; memoize+cull the
   DOM widget overlay; then decompose `App.tsx`. *(M→L)*
7. **Reference-prep + tabix nodes + tool-version pinning + real HPC DAG submission**. *(L)*

See per-area sections above for exact `file:line` anchors.
