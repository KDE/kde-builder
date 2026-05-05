import unittest  # noqa: F401

import pytest

from kde_builder_lib.bst_generator import BuildStreamGenerator
from kde_builder_lib.bst_generator import BstGenerateOptions
from kde_builder_lib.bst_generator import GenerationPolicy
from kde_builder_lib.dependency_resolver import DependencyResolver
from kde_builder_lib.kb_exception import KBRuntimeError


def make_options(tmp_path, projects=None, policy_file="tests/fixtures/bst-generate/policy.yaml", branch_group="latest-kf6"):
    if projects is None:
        projects = ["konsole"]
    return BstGenerateOptions(
        projects=projects,
        branch_group=branch_group,
        output_root=str(tmp_path),
        stack_id="org.kde.Sdk",
        sdk_element="sdk/base.bst",
        policy_file=policy_file,
    )


def test_third_party_mapping_lookup_and_failure(tmp_path):
    generator = BuildStreamGenerator(make_options(tmp_path))
    graph = {
        "konsole": {
            "deps": {
                "taglib": {"path": "third-party/taglib"},
            },
        },
        "taglib": {
            "path": "third-party/taglib",
            "module": None,
        },
    }

    assert generator._build_depends_for_module(graph, "konsole") == [
        "sdk/base.bst",
        "sdk/taglib.bst",
    ]

    generator.policy = GenerationPolicy(
        third_party_map={},
    )
    with pytest.raises(KBRuntimeError, match="Missing third-party mapping"):
        generator._build_depends_for_module(graph, "konsole")


def test_topological_order_and_closure_expansion(tmp_path):
    generator = BuildStreamGenerator(make_options(tmp_path, projects=["kde-builder"]))
    root_module = generator.module_resolver.resolve_module_if_present("kde-builder")
    graph = generator._resolve_dependency_graph([root_module])
    ordered = DependencyResolver.sort_modules_into_build_order(graph)

    assert [module.name for module in ordered] == ["kcalc", "juk", "kde-builder"]


def test_yaml_emission_stability(tmp_path, monkeypatch):
    generator = BuildStreamGenerator(make_options(tmp_path, projects=["kde-builder"]))
    refs = {
        ("kde:test/kcalc.git", "master"): "1111111111111111111111111111111111111111",
        ("kde:test/juk.git", "master"): "2222222222222222222222222222222222222222",
        ("kde:test/kde-builder.git", "master"): "3333333333333333333333333333333333333333",
    }
    monkeypatch.setattr(generator, "resolve_git_ref", lambda repo, branch: refs[(repo, branch)])
    monkeypatch.setattr(generator, "resolve_branch", lambda identifier, repopath: "master")

    assert generator.run() == 0
    first = (tmp_path / "org.kde.Sdk" / "kde-builder.bst").read_text()

    assert generator.run() == 0
    second = (tmp_path / "org.kde.Sdk" / "kde-builder.bst").read_text()

    assert first == second


def test_missing_policy_file_fails(tmp_path):
    with pytest.raises(KBRuntimeError, match="Unable to read policy file"):
        BuildStreamGenerator(make_options(tmp_path, policy_file="tests/fixtures/bst-generate/missing.yaml"))


def test_multiple_projects_are_deduplicated(tmp_path, monkeypatch):
    generator = BuildStreamGenerator(make_options(tmp_path, projects=["juk", "juk", "kde-builder"]))
    refs = {
        ("kde:test/kcalc.git", "master"): "1111111111111111111111111111111111111111",
        ("kde:test/juk.git", "master"): "2222222222222222222222222222222222222222",
        ("kde:test/kde-builder.git", "master"): "3333333333333333333333333333333333333333",
    }
    monkeypatch.setattr(generator, "resolve_git_ref", lambda repo, branch: refs[(repo, branch)])
    monkeypatch.setattr(generator, "resolve_branch", lambda identifier, repopath: "master")

    assert generator.run() == 0

    stack = (tmp_path / "org.kde.Sdk.bst").read_text()
    assert "Generated stack for juk, kde-builder (latest-kf6)" in stack
    assert stack.count("org.kde.Sdk/juk.bst") == 1
