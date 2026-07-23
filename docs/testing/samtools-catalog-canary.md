# Samtools catalog canary

This is a bounded promotion-candidate execution path, not a catalog release.
It accepts only the committed fixture at
`tests/fixtures/samtools_first_wave/workflow.json`: one pinned HTTPS
`input_file` prelude followed by exactly one each of Samtools View, Collate,
Fixmate, Sort, Markdup, Index, and Flagstat.

## Normal run submission

The editor or website must use the normal `POST /api/runs` path and add this
top-level field to the request body:

```json
{
  "name": "Samtools Catalog Canary",
  "workflow": "<the parsed workflow.json object>",
  "no_cache": true,
  "catalog_canary": {
    "profile": "samtools-first-wave",
    "catalog_digest": "sha256:f070be36e0215603d7b5affb371fd1c6c528b02f996e4a1f145e6b2d2d467530"
  }
}
```

Do not place the selector under `workflow`, `parameters`, or an arbitrary
`options` field. `RunCreateRequest` validates the selector and the run route
copies it into queue and ARQ execution options as `options.catalog_canary`.
The fixture needs no browser-local file or runtime workflow parameter.

The bridge fails before tool execution when the profile/digest is wrong, the
fixture URL is changed, any node is missing or duplicated, any other node is
present, a node is muted/bypassed, or generated promotion metadata disagrees.
It does not fall back to the legacy registry. Canary nodes always bypass the
normal result cache and workflow provenance embedding is disabled so output
bytes remain stable for hashing.

## Worker image requirements

The disposable cloud worker must contain:

- Linux amd64; ARM workers are rejected.
- The exact application revision used to build the image, including all six
  generated catalog documents and this canary bridge.
- Pixi and the committed environment bundle at
  `bionodulo/environments/locks/7d209cfa47f8a01a/`.
- `pixi.lock` SHA-256
  `918389cd4bc1f2a934e953317c4e160b505232fb8fc3e2795d9897a3b87a32b7`.
- Samtools package `samtools-1.23.1-ha83d96e_0.conda`, SHA-256
  `2cb721907a2df7c54580298d655ae7587dbed593bd5536fa8ef4a22c9ae2a496`.
- The environment installed during image build with the committed lock
  (`pixi install --locked`), with that environment's `samtools` on the worker
  process `PATH`. Runtime execution must not perform a fresh solve.
- Outbound HTTPS access to the commit-pinned `tiny.sam` raw GitHub URL in the
  fixture. The bridge verifies downloaded bytes against SHA-256
  `0b621dee8e14e8ebf5e52772c3c6695b47c312e5190b52591644ce872ee422c7`.

Run metadata records the catalog digest, required lock/package identities,
and for every Samtools node the catalog node ID, machine ID, promotion status,
execution factory, contract digest, and plan digest. A real Samtools or cloud
run remains `NOT RUN` until the disposable worker image is built and submitted.
