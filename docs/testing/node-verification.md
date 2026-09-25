# Verifying a node

Use this checklist when adding or changing an executable node. Preserve stable
node IDs needed by saved workflows. If a node is no longer runnable, record its
deprecation and reason rather than silently reassigning its ID.

## Provisioning

- Verify the exact package or vendor artifact exists for the target platform
  and provides a headless executable accepting the node's arguments.
- Check that each required executable has an environment provisioning spec.
  Specify the executable path inside multi-platform vendor archives explicitly.
- Test from the locked environment, including transitive dependencies. A binary
  on the developer's PATH is not evidence that the deployed environment has it.
- Record why an older version is pinned when newer releases do not provide a
  compatible artifact. Update source locks and family tests together.
- Match reference-data versions to the tool, and use fixtures compatible with
  those references.

## Execution and outputs

- Compare planned paths with rendered command paths. `PLAN_OUTPUTS` receives
  the run root; `render_command` receives the node's output directory. Appending
  the node ID twice produces outputs outside the planned location.
- Execute the real command with representative inputs and independently check
  meaningful output: records, nonempty matrices or expected measurements.
  Successful exit and file existence alone are insufficient.
- Verify outputs before publishing shared cache entries.
- Exercise paths containing spaces and avoid assumptions about a display,
  writable home directory or network access during execution.

## Catalog and deployment

Generate the node index before compiling the catalog: the compiler includes
`node_metadata.json` in its input digest. See the
[maintenance script guide](../../scripts/README.md).

Cloud changes may require both worker and editor images to be rebuilt. The
editor's catalog participates in preflight admission. Record and compare the
application revisions used by both deployments before diagnosing an
unregistered node. See the [Samtools canary](samtools-catalog-canary.md) for an
end-to-end fixture.

## Reporting evidence

Record the source/runtime version, command, fixture, output check and remaining
limitations. Distinguish unit tests, environment checks and actual execution.
Use the run's supported event/log path: module logging may not reach stored
workflow logs, and retained logs may be truncated.
