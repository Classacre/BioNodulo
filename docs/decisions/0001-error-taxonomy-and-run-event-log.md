# 0001 — Error taxonomy and durable run-event log

Date: 2026-08-17
Status: accepted

## Context

An audit of execution failures (the deepseek-harness study) found that the
engine classified node failures by string-matching exception text, that runs
cancelled mid-flight could leave planned nodes with no per-node status at all,
and that everything the UI showed about a run lived only in memory plus a
best-effort `run_metadata.json` — after a restart nothing but the run row
survived, and retry events were unrecoverable.

## Adopted

1. **Typed error taxonomy** (`bionodulo/execution/errors.py`): `NodeError`
   base with `code`; `NodeTimeoutError`, `NodeMemoryError`,
   `NodeExitCodeError`, `NodeCancelledError` subclasses. The subprocess runner
   raises typed errors (OOM detected via exit 137/SIGKILL or known stderr
   patterns); retry dispatch is `isinstance`-first with the legacy
   text-matching kept only as a fallback for third-party nodes raising generic
   exceptions. Existing exception classes were re-parented onto the taxonomy
   (`CommandCancelledError` under `NodeCancelledError`,
   `CommandExecutionError` under `NodeExitCodeError`, plus
   `CommandOOMError`) so old import paths and handlers keep working.
2. **`skipped_cancelled` markers**: after a terminal run state, every planned
   node the scheduler never started gets an explicit
   `skipped_cancelled` status in node results, run metadata, the emitted event
   stream, and the run-event log. No node is left statusless.
3. **Durable run-event log**: `run_events` table in the RunStore SQLite
   database (`runs.db`), appended per run with dense per-run sequence numbers,
   pruned to the last 1000 events, served via `GET /api/runs/{run_id}/events`.
   Node retries, typed node errors, cancellation markers, queue lifecycle
   transitions, and memory escalations are persisted. Existing databases
   upgrade in place (`CREATE TABLE IF NOT EXISTS`).
4. **Recovery policy**: `execution.on_interrupt` setting
   (`BIONODULO_EXECUTION__ON_INTERRUPT`), default `manual` (today's
   behaviour). `auto_resume` resubmits checkpointed interrupted runs and
   re-enqueues never-started pending runs. Decision on pending runs: they are
   re-enqueued **only** in `auto_resume` mode — in `manual` mode re-enqueueing
   would make a restart auto-execute work a user may have queued before an
   intentional shutdown, an unpredictable behaviour change for the default
   path.
5. **Capability metadata**: `REQUIRES_GPU` class attribute on nodes,
   surfaced in node metadata, `dry_run` `requirements` aggregation, and a
   generated `node_capabilities.json` artifact (`make catalog`).
6. **OOM escalation hook**: retry policies may declare
   `escalate: {memory_multiplier}`; on a `NodeMemoryError` retry the engine
   records a `node_escalate` event and applies the multiplier to the node's
   `memory` directive parameter where one exists (the `hpc_submit_job` family
   feeds it into the scheduler's mem directive on resubmission). Nodes without
   a memory directive record the escalation intent only — no fake bumps.

## Rejected

- **Plugin architecture for failure classification** (third parties
  registering classifiers): the taxonomy has four stable classes driven by
  what the subprocess runner can actually observe (timeout, exit code, OOM
  evidence, cancellation). A plugin surface would add an API to maintain for
  a problem that does not need extensibility; the legacy text-matching
  fallback already covers arbitrary third-party exceptions.
- **Interceptor refactor of the emit fan-out** (wrapping the
  `emit` callback to derive persistence from the stream): every event
  producer would then depend on an interceptor contract, and persistence would
  break silently whenever a producer bypassed the wrapper. A targeted
  `_record_run_event` hook at each persistence point is smaller and keeps the
  WebSocket path unchanged.
- **Auto-resume as the default**: restarting a server should not silently
  re-execute interrupted work (potentially expensive cluster jobs) without an
  explicit opt-in.
