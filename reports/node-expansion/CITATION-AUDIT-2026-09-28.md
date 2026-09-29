# Does every tool cite a paper? A citation audit of all 140 node families

Historical audit: “reference” below includes documentation links. This is not a
claim that every existing builtin exports a bibliographic citation. The
[2026-09-29 follow-up](RELEASE-VERIFICATION-2026-09-29.md) checks exportable citation
metadata for the 387 additions separately; UniKmer now has an official software
repository citation.

**Date:** 2026-09-28
**Question asked:** do all tools in the catalog have a reference to a paper, and where
there is none, is there at least a link to the tool's own site?
**Answer:** No, not every tool has a paper. Many have none, and for several that is
correct rather than a gap. Every node now carries at least one reference, after the
fixes below. Before the fixes, six nodes carried no reference of any kind.
**Method:** nine subagents read every family directory and reported per tool. I then
checked the flagged DOIs against Crossref myself, because subagent judgement on
whether a DOI "looks real" turned out to be unreliable in both directions.

---

## 1. How references are declared

Two mechanisms, and they are not universal:

- Class attributes `CITATION_DOIS`, `CITATION_URLS`, `CITATION_TEXT`, `DOCUMENTATION_URL`.
- A `KNOWLEDGE` dict with a `citation_evidence` list. This exists only in a handful of
  families (emboss, csvtk, samtools, seqkit, taxonkit, unikmer, vcflib, protein_database,
  pangenomics). Most families have no `KNOWLEDGE` dict at all.

For the seven script-generated families the reference is declared once in the family
adapter and inherited. I verified that directly, because a subagent assigned to it hit a
rate limit and never reported (see section 6):

| Family | Adapter DOI | Node-level overrides |
| --- | --- | --- |
| emboss | `10.1016/S0168-9525(00)02024-2` | 0 |
| vcflib | `10.1371/journal.pcbi.1009123` | 0 |
| seqkit | `10.1371/journal.pone.0163962` | 0 |
| seqfu | `10.3390/bioengineering8050059` | 0 |
| taxonkit | `10.1016/j.jgg.2021.03.006` | 0 |
| csvtk | none (deliberate) | 0 |
| unikmer | none (deliberate) | 0 |

csvtk and unikmer genuinely have no paper. csvtk's own `CITATION_TEXT` says so in as many
words, and a Crossref search for UniKmer returns only unrelated k-mer tools.

## 2. Where there is no paper, and that is correct

Four groups have no DOI and should not be given one:

- **Native BioNodulo nodes.** `flow_control_family` (13), `hpc_family` (2),
  `ml_design_family` (15), `reporting_family` (3), `python_code_family`,
  `utility_*` families, `visualization_family` chart nodes, `workflow_enhancement_family`.
  These wrap no third-party tool. Their reference is a permalink to their own source in
  the BioNodulo repo at a pinned commit, which is the convention `flow_control` and `hpc`
  already used.
- **Format specifications.** `input_family` links FASTQ, FASTA, VCF and GFF3 specs, which
  is the right reference for a format reader.
- **Tools with genuinely no publication.** Snippy, FastQC, barrnap, Filtlong, Shovill,
  Berokka, trim_galore, mlst, autobigs_cli, MetaBAT's helper scripts, BBTools' non-BBMerge
  tools, and the 10X Cell Ranger / Space Ranger pipeline docs. A Crossref query for
  Snippy returns a children's book called "Snippy And Snappy"; there is no paper. FastQC's
  canonical citation (Andrews 2010) has no DOI and appears only inside other papers'
  reference lists.
- **Commercial and hosted services.** Cell Ranger, Space Ranger, and the NIM endpoints.
  The vendor documentation is the only reference that exists.

## 3. The real gap: nodes with no reference at all

Six nodes in `ml_design_family` carried neither a DOI nor a documentation URL:

```
accession_gate, campaign_config_builder, campaign_results_builder,
openvaccine_prepare, paired_stats, training_leakage_check
```

Their siblings link the library they lean on (`random`, `statistics`, `numpy.linalg`), so
the family had a convention that these six missed. They are BioNodulo's own code, so I
added the native-node convention to `MLDesignNode` in
`ml_design_family/adapter.py`: `GIT_URL`, `GIT_COMMIT`, `DOCUMENTATION_URL` and
`SOURCE_URL` pointing at
`https://github.com/Classacre/BioNodulo/tree/a32a426c.../bionodulo/nodes/builtin/ml_design_family`.
All six inherit it, and the nodes with their own library links keep them.

## 4. Citations that were wrong

Worse than a missing citation is one pointing at the wrong paper. Four were.

**`bioext_family` cites a different tool, deliberately.** `_wrapped_tool_utils.py` has
`BIOEXT_CITATION_URL = "http://hyphy.org/"` and
`BIOEXT_CITATION_TEXT = "HyPhy: Hypothesis Testing using Phylogenies."` while
`BIOEXT_DOCUMENTATION_URL` correctly points at `github.com/veg/BioExt`. The nodes call
BioExt, not HyPhy.

I first changed this, then reverted it. BioExt is a support library from the HyPhy group
with no publication of its own, so the HyPhy paper is the only paper reference available.
My change replaced a real paper citation with a plain description of the software, which
takes a reference away rather than improving one. `tests/test_galaxy_parity_nodes.py`
asserts the current values at lines 35691-35693 and 35735-35737, so the choice was
deliberate. The values stand, with a comment added at the constant explaining that the
reader should read it as "cite the parent project".

**`hmmer_family` cited the web server for command-line tools.** The family cited only
`10.1093/nar/gkr367`, "HMMER web server: interactive sequence similarity searching", while
the nodes run `hmmsearch`, `hmmscan`, `hmmbuild` and friends. The HMMER3 paper,
`10.1371/journal.pcbi.1002195` "Accelerated Profile HMM Searches", is the right primary
reference; the web-server paper is retained as a secondary.

**`checkm_family/checkm.py` had no citation while its siblings had one.** The hand-written
node subclasses `MetagenomicsCommandNode` rather than the CheckM contract in
`checkm_family/adapter.py`, so it inherited nothing. The adapter's other contracts all
carry `10.1101/gr.186072.114`. Added to the node.

**`assembly_family` Assembly Stats** uses `10.5281/zenodo.322347` with
`CITATION_TEXT = "rjchallis/assembly-stats 17.02."`, which is a repository and version
string rather than a title. Not changed, because the Zenodo deposit is the only reference
the tool has; flagged here so it is not mistaken for a paper title.

## 5. Citations added

All Crossref-checked on 2026-09-28 before being written. Twenty-two nodes gained a paper.

| Tool | DOI | Paper |
| --- | --- | --- |
| kallisto | `10.1038/nbt.3519` | Near-optimal probabilistic RNA-seq quantification |
| salmon | `10.1038/nmeth.4197` | Salmon provides fast and bias-aware quantification of transcript expression |
| Biopython | `10.1093/bioinformatics/btp163` | Biopython: freely available Python tools for computational molecular biology |
| STRING | `10.1093/nar/gkaa1074` | The STRING database in 2021 |
| UCSC Genome Browser API | `10.1093/nar/gkae974` | The UCSC Genome Browser database: 2025 update |
| minigraph | `10.1186/s13059-020-02168-z` | The design and construction of reference pangenome graphs with minigraph |
| Panaroo | `10.1186/s13059-020-02090-4` | Producing polished prokaryotic pangenomes with the Panaroo pipeline |
| Panacus | `10.1093/bioinformatics/btae720` | Panacus: fast and exact pangenome growth and core size estimation |
| vg (5 nodes) | `10.1038/nbt.4227` | Variation graph toolkit improves read mapping |
| HMMER (CLI) | `10.1371/journal.pcbi.1002195` | Accelerated Profile HMM Searches |
| CheckM | `10.1101/gr.186072.114` | CheckM: assessing the quality of microbial genomes |
| Clustal Omega | `10.1038/msb.2011.75` | Fast, scalable generation of high-quality protein multiple sequence alignments |
| MUSCLE | `10.1093/nar/gkh340` | MUSCLE: multiple sequence alignment with high accuracy and high throughput |
| trimAl | `10.1093/bioinformatics/btp348` | trimAl: a tool for automated alignment trimming |
| FastTree | `10.1093/molbev/msp077` | FastTree: computing large minimum evolution trees |
| RAxML | `10.1093/bioinformatics/btu033` | RAxML version 8 |
| RAxML-NG | `10.1093/bioinformatics/btz305` | RAxML-NG: a fast, scalable and user-friendly tool |
| ModelTest-NG | `10.1093/molbev/msz189` | ModelTest-NG: a new and scalable tool for model selection |
| ANNOVAR | `10.1093/nar/gkq603` | ANNOVAR: functional annotation of genetic variants |
| InterProScan | `10.1093/bioinformatics/btu031` | InterProScan 5: genome-scale protein function classification |
| eggNOG-mapper | `10.1093/molbev/msx148` | Fast genome-wide functional annotation through orthology assignment |
| MLDesign (6 nodes) | none | BioNodulo source permalink, not a paper |

That is 37 nodes across 14 families. The phylogeny family went from 7 tools with a DOI
and 10 without, to 14 with and 3 without.

## 6. What the subagents got wrong

Nine subagents read 140 family directories. Their reading was good; their judgement about
whether a DOI was legitimate was not, and it failed in both directions.

**False alarms.** Flagged as "placeholder-like" or "future-dated", then verified real:

- HyPhy PRIME `10.64898/2026.03.09.710461` is a real 2026 paper. The unusual prefix and
  date-stamped suffix made it look fabricated.
- Evo2 `10.1038/s41586-026-10176-5` is a real Nature 2026 paper, "Genome modelling and
  design across all domains of life with Evo 2". Flagged as future-dated, but the current
  date is September 2026.
- Zenodo, Bioconductor, CRAN and arXiv DOIs (`10.5281/zenodo.*`, `10.18129/B9.bioc.*`,
  `10.32614/CRAN.*`, `10.48550/arXiv.*`) are legitimate identifiers, repeatedly flagged as
  suspicious.
- Six alignment nodes reported as having empty citations (`bwa`, `bowtie2`, `minimap2`,
  `LAST`, `STAR`, `bwa_mem2`) all carry their DOIs. False positive.
- EMBOSS reported as a mismatch. Its DOI resolves to exactly the EMBOSS paper.
- `metaphlan_family`'s two `CITATION_TEXT` variants for one DOI, and `mash_family`'s
  4-clause text against 3 DOIs, are real but cosmetic.

**My own recall was worse.** I tried to supply missing DOIs from memory and got **seven of
about thirty wrong**, each caught by Crossref:

| I thought | It actually is |
| --- | --- |
| `10.1038/nbt.2727` kallisto | Chromosome-scale scaffolding of de novo genome assemblies |
| `10.1038/nbt.3519` (corrected) | Near-optimal probabilistic RNA-seq quantification |
| `10.1093/nar/gkab1028` UCSC | The reactome pathway knowledgebase 2022 |
| `10.1093/nar/gky1016` MetaboAnalyst | CADD: predicting the deleteriousness of variants |
| `10.1038/s41587-020-0591-3` MZmine | Generalizing RNA velocity to transient cell states |
| `10.1186/s12859-021-04316-z` BLAST+ | Ribovore: ribosomal RNA sequence analysis |
| `10.1534/genetics.112.145037` BayeScan | Ancient Admixture in Human History |
| `10.1038/s41592-019-0616-3` CAMI | Learning representations of microbe-metabolite interactions |

That is the argument for the check, and the reason section 7 lists verified DOIs rather
than more citations I wrote from memory.

## 7. Verified DOIs not yet applied

Looked up through the Crossref API and confirmed, but not yet written into the nodes.
They are recorded here so the values do not have to be looked up again.

| Tool | Family | DOI |
| --- | --- | --- |
| ColabFold | protein_structure_design | `10.1038/s41592-022-01488-1` |
| ProteinMPNN | protein_structure_design | `10.1126/science.add2187` |
| MetaboAnalyst | metabolomics | `10.1093/nar/gkae253` (v6.0, 2024) |
| MZmine | metabolomics | `10.1038/s41587-023-01690-2` (MZmine 3) |
| MS-DIAL | metabolomics | `10.1038/nmeth.3393` (2015, the software paper) |
| SIRIUS | metabolomics | `10.1038/s41592-019-0344-8` |
| CheRRI | chira | `10.1093/gigascience/giae022` |
| MetaPhlAn 4 | metaphlan | `10.1038/s41587-023-01688-w` |
| cutadapt | trimming | `10.14806/ej.17.1.200` |

**Deliberately not applied: the BLAST+ paper.** `ncbi_family/blast.py` and `blast_parse.py`
are clients of the **BLAST URL API** (`https://blast.ncbi.nlm.nih.gov/doc/blast-help/urlapi.html`),
not of the BLAST+ command-line suite. The BLAST+ 2009 paper would be the wrong citation for
a web-service client, so those nodes keep the API documentation as their reference. This is
the same distinction that made HMMER's web-server citation wrong in the other direction.

For reference, the alignment family already carries bwa, Bowtie 2, minimap2 and STAR; they
appear in the table in section 6 only because I verified them while checking a subagent's
false positive.

## 8. Other defects found, not fixed

- **`genomics_family` bigwig_outlier** cites the pybigtools library paper for a node that
  wraps a Galaxy helper script.
- **`http_request_family`** documents MDN's generic HTTP pages while its `GIT_URL` points
  at `encode/httpx`.
- **`input_family` Sample Sheet** links `Lib/shutil.py` from CPython as its reference.
- **`epigenomics_family` bam_to_scidx** links a generic Penn State centre page and has no
  DOI; the whole `epigenomics_family` (9 nodes) has no citation even though Cooler,
  cooltools, DSS, HiC-Pro, Juicer, MethylDackel and Modkit all have papers.
- **`heinz_family`** has two of four nodes documenting the Galaxy wrapper repo rather than
  the Heinz project, and the four nodes disagree about which DOIs apply.
- **`llm_family` AI Variant Interpretation** cites the ACMG guideline but inherits the
  LiteLLM documentation URL, so its documentation and its citation describe different
  things.
- **`metagenomics_family` Kraken2 Build DB** has no DOI while Kraken2 has
  `10.1186/s13059-019-1891-0`.
- **`mmseqs2_family` Easy Linclust** lists `10.1038/s41467-018-04964-5` twice.
- **`kraken_family`** carries an unused `_CentrifugeContract` with no node.
- **`pangenomics_family`** `PangenomicsCommandContract.__init_subclass__` silently
  overwrites every subclass's literal `DOCUMENTATION_URL` from its `NODE_EVIDENCE`
  dataclass, so the literals in those node files are not the effective values.

## 9. Verification state

| Check | Result |
| --- | --- |
| Builtin nodes | 1374 (unchanged) |
| Generated nodes vs manifests | 377 / 377 agree |
| Node index drift | clean |
| Catalog projections | 1374 / 1374 operational |
| Family directories audited | 140 (102 with an adapter, 36 without, 2 non-tool) |

## 10. Honest limits

- **One subagent failed and its assignment is incomplete as delegated.** Explore-3 hit a
  Crossref/API rate limit (429) and never reported on the citation inheritance of the seven
  largest generated families. I ran that check myself by reading the adapters and counting
  node-level overrides, which is section 1. It is a narrower check than the one Explore-3
  was given, which also asked for per-node spot checks of the generated bodies.
- **Coverage is verified per family, not per node.** The subagents read every family
  directory and reported per tool, but a family-level DOI is asserted to reach every node
  by inheritance. I confirmed that for the seven generated families and spot-checked
  elsewhere; I did not walk all 1374 nodes.
- **Section 7 is work not yet done.** Nine verified DOIs remain unapplied, along with the
  defect list in section 8.
- **A DOI resolving is not a DOI being right.** Crossref confirms that
  `10.1038/nbt.3519` is titled "Near-optimal probabilistic RNA-seq quantification". It does
  not confirm that this is the paper the kallisto maintainers want cited. Where a tool has
  a version-specific paper, the choice is a judgement I made and have stated.
