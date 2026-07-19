"""Pinned authorities for focused phylogeny node contracts."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TypeVar


@dataclass(frozen=True)
class PhylogenyEvidence:
    version: str
    source_url: str
    source_paths: tuple[str, ...]
    package_constraints: tuple[str, ...] = ()
    git_url: str = ""
    git_commit: str = ""
    source_sha256: str = ""
    contract_date: str = ""
    caveats: tuple[str, ...] = ()


NODE_EVIDENCE = {
    "clustalo": PhylogenyEvidence(
        version="1.2.4",
        git_url="https://github.com/GSLBiotech/clustal-omega.git",
        git_commit="f20adc69b0802d4b7795f0928f786eac1f21a033",
        source_url=(
            "https://github.com/GSLBiotech/clustal-omega/tree/"
            "f20adc69b0802d4b7795f0928f786eac1f21a033"
        ),
        source_paths=("src/clustal-omega.c", "src/mymain.c"),
        package_constraints=("clustal-omega==1.2.4",),
    ),
    "muscle": PhylogenyEvidence(
        version="5.3",
        git_url="https://github.com/rcedgar/muscle.git",
        git_commit="2cf9d33078c9a85697e38a6f3ad827e6862420df",
        source_url=(
            "https://github.com/rcedgar/muscle/tree/"
            "2cf9d33078c9a85697e38a6f3ad827e6862420df"
        ),
        source_paths=("src/help.txt", "src/myopts.h", "src/align.cpp"),
        package_constraints=("muscle==5.3",),
        caveats=(
            "The retained diags and stable inputs are legacy compatibility flags not listed by the MUSCLE 5.3 help source.",
        ),
    ),
    "trimal": PhylogenyEvidence(
        version="1.4.1",
        git_url="https://github.com/inab/trimal.git",
        git_commit="f7b4a27747af5e95427c8c3f0f3b725029c7bdae",
        source_url=(
            "https://github.com/inab/trimal/tree/"
            "f7b4a27747af5e95427c8c3f0f3b725029c7bdae"
        ),
        source_paths=("source/main.cpp", "source/readAl.cpp"),
        package_constraints=("trimal==1.4.1",),
    ),
    "fasttree": PhylogenyEvidence(
        version="2.1.11",
        git_url="https://github.com/morgannprice/fasttree.git",
        git_commit="e374aac5a817b3a7a025e95ad2cf4b4c49c73323",
        source_url=(
            "https://github.com/morgannprice/fasttree/blob/"
            "e374aac5a817b3a7a025e95ad2cf4b4c49c73323/old/FastTree-2.1.11.c"
        ),
        source_paths=("old/FastTree-2.1.11.c", "ChangeLog.txt"),
        package_constraints=("fasttree==2.1.11",),
    ),
    "raxml": PhylogenyEvidence(
        version="8.2.12",
        git_url="https://github.com/stamatak/standard-RAxML.git",
        git_commit="a33ff40640b4a76abd5ea3a9e2f57b7dd8d854f6",
        source_url=(
            "https://github.com/stamatak/standard-RAxML/tree/"
            "a33ff40640b4a76abd5ea3a9e2f57b7dd8d854f6"
        ),
        source_paths=("axml.c", "README"),
        package_constraints=("raxml==8.2.12",),
    ),
    "raxml_ng": PhylogenyEvidence(
        version="1.2.2",
        git_url="https://github.com/amkozlov/raxml-ng.git",
        git_commit="805318cef87bd5d67064efa299b5d1cf948367fd",
        source_url=(
            "https://github.com/amkozlov/raxml-ng/tree/"
            "805318cef87bd5d67064efa299b5d1cf948367fd"
        ),
        source_paths=("README.md", "src/CommandLineParser.cpp"),
        package_constraints=("raxml-ng==1.2.2",),
        caveats=(
            "The retained tree_search=false renderer is compatibility-only; RAxML-NG --evaluate requires a --tree input that the stable node does not expose.",
        ),
    ),
    "modeltest_ng": PhylogenyEvidence(
        version="0.1.7",
        git_url="https://github.com/ddarriba/modeltest.git",
        git_commit="2d069962282cb3696c0021d298df044623bf5e38",
        source_url=(
            "https://github.com/ddarriba/modeltest/tree/"
            "2d069962282cb3696c0021d298df044623bf5e38"
        ),
        source_paths=("src/meta.cpp", "README.md"),
        package_constraints=("modeltest-ng==0.1.7",),
        caveats=(
            "The stable boolean ascertainment_bias input cannot encode ModelTest-NG's required correction argument.",
            "The source declares -m, -s, and -T mutually exclusive.",
        ),
    ),
    "astral": PhylogenyEvidence(
        version="5.7.8+galaxy0",
        git_url="https://github.com/smirarab/ASTRAL.git",
        git_commit="068a4b2497f61c866c4727bfbfd78b4361ba27c8",
        source_url="https://github.com/smirarab/ASTRAL/raw/master/Astral.5.7.8.zip",
        source_sha256="7b3d89ca4fee42b00e547ed2485e60bebfdf7f0179cfc503f0c522d682483dea",
        source_paths=("main/phylonet/coalescent/CommandLine.java", "astral-tutorial.md"),
        package_constraints=("astral-tree==5.7.8",),
    ),
    "ebi_clustal_omega": PhylogenyEvidence(
        version="1.0.0",
        git_url="https://github.com/ebi-jdispatcher/webservice-clients.git",
        git_commit="38a8d24200474b65f28980775f683c3c2dd3d742",
        source_url="https://www.ebi.ac.uk/Tools/services/rest/clustalo",
        source_paths=("python/clustalo.py", "README.md"),
        contract_date="2026-07-19",
    ),
    "phylot": PhylogenyEvidence(
        version="1.0.0",
        source_url="https://phylot.biobyte.de/help.cgi",
        source_paths=("treeGenerator.cgi", "treeGeneratorGTD.cgi"),
        contract_date="2026-07-19",
        caveats=(
            "PhyloT is a mutable hosted service and its current help page describes token accounting; no live submission was made.",
        ),
    ),
    "phylogenetic_tree_builder": PhylogenyEvidence(
        version="1.0.0",
        git_url="https://github.com/biopython/biopython.git",
        git_commit="7a9c76cce8c6a58db791be2b12a135af210cedf2",
        source_url=(
            "https://github.com/biopython/biopython/tree/"
            "7a9c76cce8c6a58db791be2b12a135af210cedf2"
        ),
        source_paths=("Bio/Phylo/__init__.py", "Bio/Phylo/NewickIO.py"),
        package_constraints=("biopython==1.87",),
        caveats=(
            "This node selects identical canonical Newick strings by frequency; it does not compute a clade consensus tree.",
        ),
    ),
}


_NodeType = TypeVar("_NodeType", bound=type)


def source_pinned(node_id: str):
    """Attach the immutable evidence record to one focused owner class."""

    def decorate(node_class: _NodeType) -> _NodeType:
        evidence = NODE_EVIDENCE[node_id]
        node_class.GIT_URL = evidence.git_url
        node_class.GIT_COMMIT = evidence.git_commit
        node_class.SOURCE_URL = evidence.source_url
        node_class.SOURCE_PATHS = list(evidence.source_paths)
        node_class.SOURCE_SHA256 = evidence.source_sha256
        node_class.PACKAGE_CONSTRAINTS = evidence.package_constraints
        node_class.PACKAGE_CONSTRAINT = "; ".join(evidence.package_constraints)
        node_class.CONTRACT_ACCESSED_DATE = evidence.contract_date
        node_class.AUDIT_CAVEATS = list(evidence.caveats)
        node_class.AUDIT_STATUS = "contract-checked-no-external-execution"
        node_class.EXIT_SEMANTICS = (
            "Reject invalid inputs before dispatch; non-zero commands, failed remote jobs, "
            "and missing planned artifacts are fatal."
        )
        return node_class

    return decorate
