"""Pinned official source authorities for the focused epigenomics wave."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class EpigenomicsEvidence:
    version: str
    git_url: str
    git_commit: str
    source_ref: str
    source_paths: tuple[str, ...]
    documentation_url: str
    package_constraints: tuple[str, ...]

    @property
    def source_urls(self) -> tuple[str, ...]:
        if "github.com" not in self.git_url:
            return (self.git_url,)
        repo = self.git_url.removesuffix(".git")
        return tuple(f"{repo}/blob/{self.git_commit}/{path}" for path in self.source_paths)


NODE_EVIDENCE = {
    "methyldackel": EpigenomicsEvidence(
        version="0.6.1",
        git_url="https://github.com/dpryan79/MethylDackel.git",
        git_commit="b6db120e96ec8cf9ab44e1b1074d2aa7af876932",
        source_ref="tag 0.6.1",
        source_paths=("README.md", "MBias.c", "extract.c", "svg.c"),
        documentation_url=(
            "https://github.com/dpryan79/MethylDackel/blob/"
            "b6db120e96ec8cf9ab44e1b1074d2aa7af876932/README.md"
        ),
        package_constraints=("methyldackel==0.6.1",),
    ),
    "dss_dmr": EpigenomicsEvidence(
        version="2.58.0",
        git_url="https://git.bioconductor.org/packages/DSS",
        git_commit="11b2949991730570a19a41f6aa38eab44d4b6d01",
        source_ref="Bioconductor RELEASE_3_22",
        source_paths=("DESCRIPTION", "R/BSseq_util.R", "R/DML.R", "R/DMR.R", "vignettes/DSS.Rmd"),
        documentation_url="https://bioconductor.org/packages/3.22/bioc/html/DSS.html",
        package_constraints=(
            "r-base==4.5.3",
            "bioconductor-dss==2.58.0",
            "r-readr==2.2.0",
        ),
    ),
    "modkit_dmr": EpigenomicsEvidence(
        version="0.4.3",
        git_url="https://github.com/nanoporetech/modkit.git",
        git_commit="d13b97db2d221afc4a1db3616a7eccdc6858a313",
        source_ref="tag v0.4.3",
        source_paths=("book/src/intro_dmr.md", "book/src/advanced_usage.md", "src/dmr/subcommands.rs"),
        documentation_url=(
            "https://github.com/nanoporetech/modkit/blob/"
            "d13b97db2d221afc4a1db3616a7eccdc6858a313/book/src/intro_dmr.md"
        ),
        package_constraints=("ont-modkit==0.4.3",),
    ),
    "hic_pro": EpigenomicsEvidence(
        version="3.1.0",
        git_url="https://github.com/nservant/HiC-Pro.git",
        git_commit="de77ff9cc9dd927989e661f74454aeac24a61791",
        source_ref="tag v3.1.0",
        source_paths=("bin/HiC-Pro", "config-hicpro.txt", "README.md"),
        documentation_url=(
            "https://github.com/nservant/HiC-Pro/blob/"
            "de77ff9cc9dd927989e661f74454aeac24a61791/README.md"
        ),
        package_constraints=(),
    ),
    "juicer": EpigenomicsEvidence(
        version="2.0",
        git_url="https://github.com/aidenlab/juicer.git",
        git_commit="177eb610397e4207fc56db1df169b2d08d06d43a",
        source_ref="main at pinned commit; CPU/juicer.sh declares Juicer 2.0 (no 2.0 tag)",
        source_paths=("CPU/juicer.sh", "README.md"),
        documentation_url=(
            "https://github.com/aidenlab/juicer/blob/"
            "177eb610397e4207fc56db1df169b2d08d06d43a/CPU/juicer.sh"
        ),
        package_constraints=("bwa==0.7.19", "samtools==1.23.1", "openjdk>=17"),
    ),
    "cooler": EpigenomicsEvidence(
        version="0.10.2",
        git_url="https://github.com/open2c/cooler.git",
        git_commit="7076bffdc61166a08808f16792256df3a958b475",
        source_ref="tag v0.10.2",
        source_paths=(
            "src/cooler/cli/cload.py",
            "src/cooler/cli/csort.py",
            "src/cooler/cli/zoomify.py",
            "src/cooler/cli/balance.py",
        ),
        documentation_url="https://cooler.readthedocs.io/en/latest/cli.html",
        package_constraints=("cooler==0.10.2",),
    ),
    "cooltools_compartments": EpigenomicsEvidence(
        version="0.7.0",
        git_url="https://github.com/open2c/cooltools.git",
        git_commit="976513740f1b45fe68ffff1b8c2256d73925224e",
        source_ref="tag v0.7.0 eigs-cis",
        source_paths=("cooltools/cli/eigs_cis.py",),
        documentation_url="https://cooltools.readthedocs.io/en/latest/cli.html#eigs-cis",
        package_constraints=("cooltools==0.7.0",),
    ),
    "cooltools_insulation": EpigenomicsEvidence(
        version="0.7.0",
        git_url="https://github.com/open2c/cooltools.git",
        git_commit="976513740f1b45fe68ffff1b8c2256d73925224e",
        source_ref="tag v0.7.0 insulation",
        source_paths=("cooltools/cli/insulation.py",),
        documentation_url="https://cooltools.readthedocs.io/en/latest/cli.html#insulation",
        package_constraints=("cooltools==0.7.0",),
    ),
}
