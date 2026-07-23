# Samtools cloud canary

This fixture verifies the same execution path used by an ordinary user
workflow. It is not a privileged catalog mode and it has no tool-specific
worker image or executor bypass.

The committed workflow at
`tests/fixtures/samtools_first_wave/workflow.json` contains one HTTPS
`input_file` followed by Samtools View, Collate, Fixmate, Sort, Markdup, Index,
and Flagstat. Import it through the editor and submit it with the normal cloud
Run control. The request must not contain a `catalog_canary` selector.

## What the canary proves

The generic worker must:

- load the submitted workflow and normal node registry;
- derive `samtools=1.23.1` from the nodes' package constraints;
- select environment `40db091121c94941`;
- materialize its committed `pixi.toml` and `pixi.lock` into the job workspace
  or content-addressed shared cache;
- run `pixi install --locked --all` at runtime when that environment is not
  already cached;
- execute the seven normal node implementations and upload their outputs; and
- record immutable source, catalog, environment-lock, and output identities in
  the run attestation.

The generic image contains only BioNodulo's worker runtime, Pixi, application
source, and committed environment definitions. Samtools itself must not be
preinstalled in the image.

## Fixed evidence

- Samtools version: `1.23.1`
- Environment ID: `40db091121c94941`
- Environment lock SHA-256:
  `da58ebe2f489d3d740f23c302e9495ab23068491bad714f605438a92fb8afaa4`
- Samtools package SHA-256:
  `2cb721907a2df7c54580298d655ae7587dbed593bd5536fa8ef4a22c9ae2a496`
- Input `tiny.sam` SHA-256:
  `0b621dee8e14e8ebf5e52772c3c6695b47c312e5190b52591644ce872ee422c7`

A real cloud run remains `NOT RUN` until the workflow has completed through
the production UI and all SkyPilot resources have been torn down.
