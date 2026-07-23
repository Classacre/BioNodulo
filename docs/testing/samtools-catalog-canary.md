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
    "catalog_digest": "sha256:bee248d86257ab760c9492f0774ab5195d82f0743f46412ed81726ecba50ce52"
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
  `bionodulo/environments/locks/40db091121c94941/`.
- `pixi.lock` SHA-256
  `da58ebe2f489d3d740f23c302e9495ab23068491bad714f605438a92fb8afaa4`.
- Samtools package `samtools-1.23.1-ha83d96e_0.conda`, SHA-256
  `2cb721907a2df7c54580298d655ae7587dbed593bd5536fa8ef4a22c9ae2a496`.
- The environment installed during image build with the committed lock
  (`pixi install --locked`) under
  `/opt/bionodulo-catalog-envs/40db091121c94941`. The canary validates the
  committed manifest and lock bytes and invokes that environment's absolute
  `samtools` path. Runtime execution must not perform a fresh solve or fall
  back to an ambient `samtools`.
- Outbound HTTPS access to the commit-pinned `tiny.sam` raw GitHub URL in the
  fixture. The bridge verifies downloaded bytes against SHA-256
  `0b621dee8e14e8ebf5e52772c3c6695b47c312e5190b52591644ce872ee422c7`.

Run metadata records the catalog digest, required lock/package identities,
and for every Samtools node the catalog node ID, machine ID, promotion status,
execution factory, contract digest, and plan digest. A real Samtools or cloud
run remains `NOT RUN` until the disposable worker image is built and submitted.
