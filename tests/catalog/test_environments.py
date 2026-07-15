from __future__ import annotations

import re
from pathlib import Path

import pytest
from pydantic import TypeAdapter, ValidationError

import bionodulo.nodes.contract.environments as env


SHA_A = "sha256:" + "a" * 64
SHA_B = "sha256:" + "b" * 64


def test_package_requirement_accepts_only_small_explicit_constraint_language() -> None:
    exact = env.PackageRequirement(name="samtools", constraint="==1.20")
    bounded = env.PackageRequirement(name="numpy", constraint=">=1.26,<3")

    assert exact.as_string() == "samtools==1.20"
    assert bounded.as_string() == "numpy>=1.26,<3"
    assert hash(exact)


@pytest.mark.parametrize(
    "constraint",
    (
        "",
        "1.20",
        "*",
        "==*",
        ">=1.0",
        "<2",
        ">=1,<1",
        ">=1,<=1",
        "~=1.2",
        "==1.2;python_version>'3'",
        "==https://example.org/a.whl",
        "==git+https://example.org/repo",
        " ==1.2",
        "==1.2 ",
        "==1.2\n",
        "==1.2$(id)",
    ),
)
def test_package_requirement_rejects_unpinned_or_unsafe_constraints(constraint: str) -> None:
    with pytest.raises(ValidationError):
        env.PackageRequirement(name="samtools", constraint=constraint)


@pytest.mark.parametrize(
    "name",
    ("", "Samtools", "-samtools", "sam tools", "sam/tools", "samtools\n", "samtools;id"),
)
def test_package_requirement_names_are_canonical(name: str) -> None:
    with pytest.raises(ValidationError):
        env.PackageRequirement(name=name, constraint="==1.20")


def test_environment_platform_wire_values_are_unambiguous() -> None:
    assert tuple(platform.value for platform in env.ExecutionPlatform) == (
        "linux/amd64",
        "linux/arm64",
    )


@pytest.mark.parametrize(
    "image",
    (
        "example.org/tools/samtools:latest",
        "example.org/tools/samtools:1.20@" + SHA_A,
        "example.org/tools/samtools@sha256:" + "A" * 64,
        "example.org/tools/samtools@sha256:abc",
        "ubuntu@" + SHA_A,
        "library/ubuntu@" + SHA_A,
        "https://example.org/tools/samtools@" + SHA_A,
        "example.org/tools/../samtools@" + SHA_A,
        "example.org/tools/samtools@" + SHA_A + "?x=1",
    ),
)
def test_oci_references_reject_mutable_or_ambiguous_images(image: str) -> None:
    with pytest.raises(ValidationError):
        env.ContainerImageLock(
            platform=env.ExecutionPlatform.LINUX_AMD64,
            resolver_platform="linux-64",
            image=image,
        )


def test_oci_reference_accepts_registry_ports_and_lowercase_digest() -> None:
    lock = env.ContainerImageLock(
        platform=env.ExecutionPlatform.LINUX_AMD64,
        resolver_platform="linux-64",
        image="registry.example.org:5000/team/tool@" + SHA_A,
    )

    assert lock.image.endswith(SHA_A)
    assert re.fullmatch(r"sha256:[0-9a-f]{64}", lock.lock_digest())


def resolver() -> env.ResolverIdentity:
    return env.ResolverIdentity(
        name="pixi",
        version="0.24.2",
        config_digest=SHA_A,
    )


def artifact(
    name: str = "samtools",
    *,
    version: str = "1.20",
    build: str = "h50ea8bc_0",
    digest: str = SHA_B,
) -> env.LockedArtifact:
    return env.LockedArtifact(
        name=name,
        version=version,
        build=build,
        filename=f"{name}-{version}-{build}.conda",
        url=f"https://packages.example.org/linux-64/{name}-{version}-{build}.conda",
        sha256=digest,
        size_bytes=1234,
    )


def platform_lock(
    platform: env.ExecutionPlatform = env.ExecutionPlatform.LINUX_AMD64,
) -> env.PlatformLock:
    return env.PlatformLock(
        platform=platform,
        resolver_platform="linux-64" if platform is env.ExecutionPlatform.LINUX_AMD64 else "linux-aarch64",
        resolver=resolver(),
        artifacts=(artifact(),),
    )


def executable_probe(probe_id: str = "samtools") -> env.ExecutableProbe:
    return env.ExecutableProbe(
        probe_id=probe_id,
        locator="bin/samtools",
        version_arguments=("--version",),
        expected_version_pattern=r"^samtools 1\.20(?:\n|$)",
    )


def test_platform_lock_contains_exact_resolver_and_artifact_identity() -> None:
    lock = platform_lock()
    rebuilt = env.PlatformLock.model_validate_json(lock.model_dump_json())

    assert rebuilt == lock
    assert hash(rebuilt) == hash(lock)
    assert lock.artifacts[0].sha256 == SHA_B
    assert re.fullmatch(r"sha256:[0-9a-f]{64}", lock.lock_digest())
    assert lock.lock_digest() == rebuilt.lock_digest()


@pytest.mark.parametrize(
    "url",
    (
        "http://packages.example.org/linux-64/samtools-1.20-h0.conda",
        "https://user:secret@packages.example.org/linux-64/samtools-1.20-h0.conda",
        "https://packages.example.org/linux-64/samtools-1.20-h0.conda?token=secret",
        "https://packages.example.org/linux-64/samtools-1.20-h0.conda#fragment",
        "https://PACKAGES.example.org/linux-64/samtools-1.20-h0.conda",
        "https://packages.example.org:443/linux-64/samtools-1.20-h0.conda",
        "https://packages.example.org/linux-64/%73amtools-1.20-h0.conda",
        "https://packages.example.org/linux-64/latest.conda",
        "https://packages.example.org/linux-64/../samtools-1.20-h0.conda",
    ),
)
def test_locked_artifact_rejects_nonimmutable_or_credential_bearing_urls(url: str) -> None:
    with pytest.raises(ValidationError):
        env.LockedArtifact(
            name="samtools",
            version="1.20",
            build="h0",
            filename="samtools-1.20-h0.conda",
            url=url,
            sha256=SHA_A,
            size_bytes=1,
        )


@pytest.mark.parametrize(
    ("field", "value"),
    (
        ("version", "latest"),
        ("version", ">=1.20"),
        ("build", ""),
        ("build", "*"),
        ("sha256", "a" * 64),
        ("sha256", "sha256:" + "A" * 64),
        ("size_bytes", True),
        ("size_bytes", 0),
    ),
)
def test_locked_artifact_fields_are_exact_and_strict(field: str, value: object) -> None:
    values = artifact().model_dump(mode="python")
    values[field] = value

    with pytest.raises(ValidationError):
        env.LockedArtifact.model_validate(values)


def test_locked_artifact_url_basename_must_equal_explicit_filename() -> None:
    locked = artifact()

    with pytest.raises(ValidationError, match="filename"):
        locked.model_copy(update={"filename": "different-1.20-h0.conda"})


def test_platform_lock_rejects_duplicate_or_noncanonical_artifacts() -> None:
    alpha = artifact("alpha", version="1.0", build="h0")
    zeta = artifact("zeta", version="2.0", build="h1")

    with pytest.raises(ValidationError, match="canonically ordered"):
        env.PlatformLock(
            platform=env.ExecutionPlatform.LINUX_AMD64,
            resolver_platform="linux-64",
            resolver=resolver(),
            artifacts=(zeta, alpha),
        )
    with pytest.raises(ValidationError, match="unique"):
        env.PlatformLock(
            platform=env.ExecutionPlatform.LINUX_AMD64,
            resolver_platform="linux-64",
            resolver=resolver(),
            artifacts=(alpha, alpha),
        )


@pytest.mark.parametrize(
    "case",
    (
        "empty_artifacts",
        "list_artifacts",
        "bad_platform",
        "bad_resolver",
    ),
)
def test_platform_lock_copy_revalidates_nested_content(case: str) -> None:
    updates: dict[str, object]
    if case == "empty_artifacts":
        updates = {"artifacts": ()}
    elif case == "list_artifacts":
        updates = {"artifacts": [artifact()]}
    elif case == "bad_platform":
        updates = {"resolver_platform": " linux-64"}
    else:
        updates = {"resolver": {"name": "pixi", "version": "latest", "config_digest": SHA_A}}

    with pytest.raises(ValidationError):
        platform_lock().model_copy(update=updates)


def test_executable_probe_binds_a_locator_not_a_path_lookup_name() -> None:
    probe = executable_probe()

    assert probe.locator == "bin/samtools"
    assert probe.version_arguments == ("--version",)
    assert hash(probe)


@pytest.mark.parametrize(
    ("field", "value"),
    (
        ("locator", "samtools"),
        ("locator", "../bin/samtools"),
        ("locator", "bin\\samtools"),
        ("locator", "bin//samtools"),
        ("locator", "bin/samtools\x00"),
        ("version_arguments", ()),
        ("version_arguments", ["--version"]),
        ("version_arguments", ("--version\x00",)),
        ("expected_version_pattern", ""),
        ("expected_version_pattern", "["),
    ),
)
def test_executable_probe_rejects_path_fallback_and_unbounded_probe_data(
    field: str,
    value: object,
) -> None:
    values = executable_probe().model_dump(mode="python")
    values[field] = value

    with pytest.raises(ValidationError):
        env.ExecutableProbe.model_validate(values)


def test_import_and_r_package_probes_are_typed_and_versioned() -> None:
    python_probe = env.ImportProbe(
        probe_id="numpy",
        module="numpy.linalg",
        expected_version="1.26.4",
    )
    r_probe = env.RPackageProbe(
        probe_id="deseq2",
        package="DESeq2",
        expected_version="1.42.0",
    )

    assert python_probe.module == "numpy.linalg"
    assert r_probe.package == "DESeq2"


@pytest.mark.parametrize("module", ("", ".numpy", "numpy..linalg", "../numpy", "numpy module", "numpy\n"))
def test_import_probe_rejects_traversal_or_control_characters(module: str) -> None:
    with pytest.raises(ValidationError):
        env.ImportProbe(
            probe_id="numpy",
            module=module,
            expected_version="1.26.4",
        )


def pixi_environment(**updates: object) -> env.PixiEnvironment:
    values: dict[str, object] = {
        "environment_id": "alignment-tools",
        "packages": ("samtools==1.20",),
        "channels": ("https://conda.anaconda.org/bioconda",),
        "platforms": (
            env.ExecutionPlatform.LINUX_AMD64,
            env.ExecutionPlatform.LINUX_ARM64,
        ),
        "locks": (platform_lock(),),
        "executable_probes": (executable_probe(),),
        "import_probes": (),
    }
    values.update(updates)
    return env.PixiEnvironment(**values)


def python_environment(**updates: object) -> env.PythonEnvironment:
    values: dict[str, object] = {
        "environment_id": "python-analysis",
        "python_version": ">=3.11,<3.13",
        "packages": ("numpy==1.26.4",),
        "indexes": ("https://pypi.org/simple",),
        "platforms": (env.ExecutionPlatform.LINUX_AMD64,),
        "locks": (),
        "executable_probes": (executable_probe("python"),),
        "import_probes": (
            env.ImportProbe(
                probe_id="numpy",
                module="numpy",
                expected_version="1.26.4",
            ),
        ),
    }
    values.update(updates)
    return env.PythonEnvironment(**values)


def r_environment(**updates: object) -> env.REnvironment:
    values: dict[str, object] = {
        "environment_id": "r-analysis",
        "r_version": "==4.3.3",
        "packages": ("deseq2==1.42.0",),
        "repositories": ("https://cran.r-project.org/src/contrib",),
        "platforms": (env.ExecutionPlatform.LINUX_AMD64,),
        "locks": (),
        "executable_probes": (executable_probe("rscript"),),
        "package_probes": (
            env.RPackageProbe(
                probe_id="deseq2",
                package="DESeq2",
                expected_version="1.42.0",
            ),
        ),
    }
    values.update(updates)
    return env.REnvironment(**values)


def container_environment(**updates: object) -> env.ContainerEnvironment:
    values: dict[str, object] = {
        "environment_id": "container-tools",
        "image": "registry.example.org/tools/samtools@" + SHA_A,
        "platforms": (env.ExecutionPlatform.LINUX_AMD64,),
        "image_locks": (
            env.ContainerImageLock(
                platform=env.ExecutionPlatform.LINUX_AMD64,
                resolver_platform="linux-64",
                image="registry.example.org/tools/samtools@" + SHA_B,
            ),
        ),
        "executable_probes": (executable_probe(),),
    }
    values.update(updates)
    return env.ContainerEnvironment(**values)


@pytest.mark.parametrize(
    "factory",
    (pixi_environment, python_environment, r_environment, container_environment),
)
def test_every_environment_variant_is_frozen_hashable_and_json_roundtrippable(
    factory: object,
) -> None:
    environment = factory()
    rebuilt = TypeAdapter(env.EnvironmentSpec).validate_json(environment.model_dump_json())

    assert rebuilt == environment
    assert hash(rebuilt) == hash(environment)
    assert rebuilt.environment_digest() == environment.environment_digest()
    assert re.fullmatch(r"sha256:[0-9a-f]{64}", environment.environment_digest())
    with pytest.raises(ValidationError, match="frozen_instance"):
        environment.environment_id = "changed"


def test_environment_union_discriminator_selects_all_four_variants() -> None:
    adapter = TypeAdapter(env.EnvironmentSpec)
    variants = (
        pixi_environment(),
        python_environment(),
        r_environment(),
        container_environment(),
    )

    rebuilt = tuple(adapter.validate_json(item.model_dump_json()) for item in variants)

    assert tuple(type(item) for item in rebuilt) == tuple(type(item) for item in variants)
    schema = adapter.json_schema()
    assert schema["discriminator"]["propertyName"] == "kind"


def test_pixi_parses_pinned_strings_but_rejects_bare_packages() -> None:
    environment = pixi_environment(
        packages=("bcftools>=1.19,<2", "samtools==1.20"),
        locks=(),
    )

    assert tuple(package.as_string() for package in environment.packages) == (
        "bcftools>=1.19,<2",
        "samtools==1.20",
    )
    with pytest.raises(ValidationError):
        pixi_environment(packages=("samtools",))


@pytest.mark.parametrize(
    ("factory", "field", "value"),
    (
        (pixi_environment, "platforms", ()),
        (
            pixi_environment,
            "platforms",
            (env.ExecutionPlatform.LINUX_ARM64, env.ExecutionPlatform.LINUX_AMD64),
        ),
        (
            pixi_environment,
            "platforms",
            (env.ExecutionPlatform.LINUX_AMD64, env.ExecutionPlatform.LINUX_AMD64),
        ),
        (pixi_environment, "packages", ("samtools==1.20", "samtools==1.21")),
        (
            pixi_environment,
            "channels",
            ("https://conda.anaconda.org/bioconda", "https://conda.anaconda.org/bioconda"),
        ),
        (python_environment, "python_version", ">=3.11"),
        (r_environment, "r_version", "latest"),
        (container_environment, "image", "registry.example.org/tools/samtools:latest"),
    ),
)
def test_environment_variants_reject_ambiguous_or_duplicate_declarations(
    factory: object,
    field: str,
    value: object,
) -> None:
    with pytest.raises(ValidationError):
        factory(**{field: value})


@pytest.mark.parametrize(
    "url",
    (
        "http://pypi.org/simple",
        "https://user:secret@pypi.org/simple",
        "https://pypi.org/simple?token=secret",
        "https://pypi.org/simple#fragment",
        "https://PYPI.org/simple",
        "https://pypi.org:443/simple",
        "https://pypi.org/%73imple",
        "https://pypi.org/simple path",
    ),
)
def test_package_repository_urls_are_https_and_credential_free(url: str) -> None:
    with pytest.raises(ValidationError):
        python_environment(indexes=(url,))


def test_locks_may_be_absent_or_partial_without_claiming_full_resolution() -> None:
    unlocked = pixi_environment(locks=())
    partial = pixi_environment(locks=(platform_lock(),))
    arm_lock = platform_lock(env.ExecutionPlatform.LINUX_ARM64)
    fully_locked = pixi_environment(locks=(platform_lock(), arm_lock))

    assert unlocked.is_fully_locked is False
    assert partial.is_fully_locked is False
    assert fully_locked.is_fully_locked is True


@pytest.mark.parametrize(
    ("name", "version", "build"),
    (
        ("unrelated", "1.0", "h0"),
        ("samtools", "1.19", "h0"),
    ),
)
def test_lock_inventory_must_resolve_every_direct_package_request(
    name: str,
    version: str,
    build: str,
) -> None:
    locked_artifact = artifact(name, version=version, build=build)
    incomplete = env.PlatformLock(
        platform=env.ExecutionPlatform.LINUX_AMD64,
        resolver_platform="linux-64",
        resolver=resolver(),
        artifacts=(locked_artifact,),
    )

    with pytest.raises(ValidationError, match="package request"):
        pixi_environment(locks=(incomplete,))


def test_locks_are_unique_sorted_and_cover_only_declared_platforms() -> None:
    amd = platform_lock()
    arm = platform_lock(env.ExecutionPlatform.LINUX_ARM64)

    with pytest.raises(ValidationError, match="canonically ordered"):
        pixi_environment(locks=(arm, amd))
    with pytest.raises(ValidationError, match="unique"):
        pixi_environment(locks=(amd, amd))
    with pytest.raises(ValidationError, match="declared"):
        python_environment(locks=(arm,))


def test_container_platform_image_locks_have_the_same_full_lock_semantics() -> None:
    unlocked = container_environment(image_locks=())
    full = container_environment()

    assert unlocked.is_fully_locked is False
    assert full.is_fully_locked is True
    with pytest.raises(ValidationError, match="unique"):
        container_environment(image_locks=(full.image_locks[0], full.image_locks[0]))


def test_container_image_locks_must_use_the_declared_image_repository() -> None:
    unrelated = env.ContainerImageLock(
        platform=env.ExecutionPlatform.LINUX_AMD64,
        resolver_platform="linux-64",
        image="registry.example.org/other/tool@" + SHA_B,
    )

    with pytest.raises(ValidationError, match="repository"):
        container_environment(image_locks=(unrelated,))


def test_probe_ids_share_one_namespace_within_an_environment() -> None:
    duplicate = env.ImportProbe(
        probe_id="samtools",
        module="samtools",
        expected_version="1.20",
    )

    with pytest.raises(ValidationError, match="probe IDs must be unique"):
        pixi_environment(import_probes=(duplicate,))


@pytest.mark.parametrize(
    "model_name",
    (
        "PackageRequirement",
        "ResolverIdentity",
        "LockedArtifact",
        "PlatformLock",
        "ContainerImageLock",
        "ExecutableProbe",
        "ImportProbe",
        "RPackageProbe",
        "VersionRequest",
        "PixiEnvironment",
        "PythonEnvironment",
        "REnvironment",
        "ContainerEnvironment",
    ),
)
def test_all_environment_models_use_the_strict_frozen_contract(model_name: str) -> None:
    model = getattr(env, model_name)

    assert model.model_config["strict"] is True
    assert model.model_config["frozen"] is True
    assert model.model_config["extra"] == "forbid"
    assert model.model_config["revalidate_instances"] == "always"


def test_environment_extras_and_python_collection_coercions_are_rejected() -> None:
    with pytest.raises(ValidationError):
        pixi_environment(shell=True)
    with pytest.raises(ValidationError):
        pixi_environment(platforms=[env.ExecutionPlatform.LINUX_AMD64])
    with pytest.raises(ValidationError):
        pixi_environment(packages=["samtools==1.20"])
    with pytest.raises(ValidationError):
        executable_probe().model_copy(update={"version_arguments": "--version"})


def test_environment_copy_and_construct_revalidate_nested_instances() -> None:
    invalid_probe = env.ExecutableProbe.model_construct(
        probe_id="samtools",
        locator="samtools",
        version_arguments=("--version",),
        expected_version_pattern="^1.20$",
        fingerprint=None,
    )
    valid = pixi_environment()
    forged = env.PixiEnvironment.model_construct(
        **{
            **valid.model_dump(mode="python"),
            "executable_probes": (invalid_probe,),
        }
    )

    with pytest.raises(ValidationError):
        env.PixiEnvironment.model_validate(forged)
    with pytest.raises(ValidationError):
        forged.model_copy()
    with pytest.raises(ValidationError):
        valid.model_copy(update={"platforms": ()})


def test_environment_digest_is_canonical_and_semantically_sensitive() -> None:
    original = pixi_environment()
    reconstructed = env.PixiEnvironment.model_validate_json(original.model_dump_json())
    unlocked_original = pixi_environment(locks=())
    changed_package = pixi_environment(packages=("samtools==1.21",), locks=())
    changed_probe = pixi_environment(
        executable_probes=(executable_probe().model_copy(update={"version_arguments": ("version",)}),)
    )

    assert reconstructed.environment_digest() == original.environment_digest()
    assert changed_package.environment_digest() != unlocked_original.environment_digest()
    assert changed_probe.environment_digest() != original.environment_digest()


def test_environment_module_is_declarative_and_isolated_from_execution_code() -> None:
    source = Path(env.__file__).read_text(encoding="utf-8")

    for forbidden in (
        "_shell_join",
        "subprocess",
        "os.system",
        "shlex.join",
        "legacy.executor",
    ):
        assert forbidden not in source
