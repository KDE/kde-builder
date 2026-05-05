import unittest  # noqa: F401

from pathlib import Path
import yaml

from kde_builder_lib.bst_generator import BuildStreamGenerator
from kde_builder_lib.bst_generator import BstGenerateOptions


def make_options(tmp_path, projects):
    return BstGenerateOptions(
        projects=projects,
        branch_group="latest-kf6",
        output_root=str(tmp_path),
        stack_id="org.kde.Sdk",
        sdk_element="sdk/base.bst",
        policy_file="tests/fixtures/bst-generate/policy.yaml",
    )


def test_generate_kde_builder_closure_contains_expected_transitive_deps(tmp_path, monkeypatch):
    generator = BuildStreamGenerator(make_options(tmp_path, ["kde-builder"]))
    refs = {
        ("kde:test/kcalc.git", "master"): "1111111111111111111111111111111111111111",
        ("kde:test/juk.git", "master"): "2222222222222222222222222222222222222222",
        ("kde:test/kde-builder.git", "master"): "3333333333333333333333333333333333333333",
    }
    monkeypatch.setattr(generator, "resolve_git_ref", lambda repo, branch: refs[(repo, branch)])
    monkeypatch.setattr(generator, "resolve_branch", lambda identifier, repopath: "master")

    assert generator.run() == 0

    fixture_root = Path("tests/fixtures/bst-generate")
    stack = yaml.safe_load((tmp_path / "org.kde.Sdk.bst").read_text())
    kde_builder = yaml.safe_load((tmp_path / "org.kde.Sdk" / "kde-builder.bst").read_text())

    assert stack == yaml.safe_load((fixture_root / "expected-kde-builder-stack.bst").read_text())
    assert stack["depends"] == ["org.kde.Sdk/kcalc.bst", "org.kde.Sdk/juk.bst", "org.kde.Sdk/kde-builder.bst"]
    assert kde_builder["build-depends"] == [
        "sdk/base.bst",
        "org.kde.Sdk/juk.bst",
        "sdk/taglib.bst",
    ]
    assert kde_builder["sources"][0]["track"] == "master"
    assert kde_builder["sources"][0]["ref"] == "3333333333333333333333333333333333333333"


def test_generate_multiple_projects_combines_closures(tmp_path, monkeypatch):
    generator = BuildStreamGenerator(make_options(tmp_path, ["juk", "kde-builder"]))
    refs = {
        ("kde:test/kcalc.git", "master"): "1111111111111111111111111111111111111111",
        ("kde:test/juk.git", "master"): "2222222222222222222222222222222222222222",
        ("kde:test/kde-builder.git", "master"): "3333333333333333333333333333333333333333",
    }
    monkeypatch.setattr(generator, "resolve_git_ref", lambda repo, branch: refs[(repo, branch)])
    monkeypatch.setattr(generator, "resolve_branch", lambda identifier, repopath: "master")

    assert generator.run() == 0

    stack = yaml.safe_load((tmp_path / "org.kde.Sdk.bst").read_text())
    assert stack["description"] == "Generated stack for juk, kde-builder (latest-kf6)"
    assert stack["depends"] == [
        "org.kde.Sdk/kcalc.bst",
        "org.kde.Sdk/juk.bst",
        "org.kde.Sdk/kde-builder.bst",
    ]
