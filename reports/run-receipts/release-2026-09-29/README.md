# Bounded eight-family execution sample (2026-09-29)

Fourteen node commands were rendered from the current node classes and executed in
locally available, digest-pinned Linux containers with networking disabled. Each
`receipt.json` records raw and container argv, image digest, input and output
hashes, exit code, and output verification. `python verify.py` rechecks all
artifact hashes and 14 small independent content expectations; `oracle.json`
records the last result (28/28 passing).

| Family | Nodes and checked content |
| --- | --- |
| CSVtk | `csvtk_cut`: selected columns match direct TSV projection |
| SeqKit | `seqkit_mutate`: base 2 changes from C to T |
| SeqFu | `seqfu_shred`: two pairs of nonempty 8-base FASTQ reads |
| vcflib | `vcflib_vcfuniq`: unique input records retained exactly |
| EMBOSS | `emboss_water`: two identical 12-base sequences align 12/12 with default options and explicit `brief=false` (`-brief N`) |
| HTSlib | `tabix_query`: two records inside chr1:100-200 |
| UniKmer | `encode`, `count`, `count` with TaxId 562, `split`, `grep`, `tsplit`: binary outputs decode to the expected k-mer set or selected ACG |
| TaxonKit | `taxonkit_list`: Bacteria contains E. coli in a tiny taxonomy dump |

`fixtures/mini.unik` was produced from `mini.fa` by the pinned UniKmer image
with `count --kmer-len 3 --sort --out-prefix /work/mini /work/mini.fa`.
`fixtures/mini-taxid.unik` is a byte copy of the `unikmer-count-taxid` node's
captured binary output. Both remain tiny and reproducible. The TaxonKit dump is a
three-record NCBI-format fixture, not a production taxonomy database.

The harness follows `CommandNode.run`'s output-directory injection and checks
planned outputs plus node-specific `VERIFY_OUTPUTS`. Binary stdout is retained
byte-for-byte as `work/stdout.bin`. Before the current grep fix, the same rendered
operation exited 0 but wrote binary stdout and no directory artifact. With the
node's explicit output prefix it now writes `output.unik` in the planned directory.
SeqFu shred with a 20-base sequence and default 500-base fragment length also
exited 0 but produced two empty files; this receipt uses a 16-base fragment length
to exercise actual paired reads.

These receipts cover the node command contract in local Docker. They do not prove
the app queue, cloud provisioning, all parameter combinations, or broad scientific
correctness. They also do not erase failures recorded in earlier batch samples.
