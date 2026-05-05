from __future__ import annotations

import argparse
from dataclasses import dataclass
from pathlib import Path
import os
import re
import subprocess
import tempfile
from typing import Any

import yaml

from .application import Application
from .build_context import BuildContext
from .debug import Debug
from .debug import KBLogger
from .dependency_resolver import DependencyResolver
from .kb_exception import KBRuntimeError
from .kb_exception import NoKDEProjectsFound
from .module.module import Module
from .module_resolver import ModuleResolver
from .updater.updater import Updater
from .util.util import Util

logger_bst = KBLogger.getLogger("application")

BST_SORT_PRIORITY = [
    "kind",
    "build-depends",
    "depends",
    "runtime-depends",
    "variables",
]


@dataclass
class BstGenerateOptions:
    projects: list[str]
    branch_group: str
    output_root: str
    stack_id: str
    sdk_element: str
    policy_file: str


@dataclass
class GenerationPolicy:
    third_party_map: dict[str, str]

    @classmethod
    def from_path(cls, policy_file: str) -> GenerationPolicy:
        try:
            with open(policy_file, "r") as fh:
                policy = yaml.safe_load(fh) or {}
        except FileNotFoundError as exc:
            raise KBRuntimeError(f"Unable to read policy file {policy_file}") from exc

        unknown_keys = sorted(set(policy.keys()) - {"third_party_map"})
        if unknown_keys:
            raise KBRuntimeError(
                f"Unsupported policy keys in {policy_file}: {', '.join(unknown_keys)}"
            )

        return cls(
            third_party_map=dict(policy.get("third_party_map", {})),
        )


def parse_bst_generate_args(argv: list[str]) -> BstGenerateOptions:
    parser = argparse.ArgumentParser(prog="kde-builder bst-generate", allow_abbrev=False)
    parser.add_argument("projects", nargs="+")
    parser.add_argument("--branch-group", default="latest-kf6")
    parser.add_argument("--output-root", required=True)
    parser.add_argument("--stack-id", default="org.kde.Sdk")
    parser.add_argument("--sdk-element", required=True)
    parser.add_argument("--policy-file", required=True)
    args = parser.parse_args(argv)
    return BstGenerateOptions(
        projects=args.projects,
        branch_group=args.branch_group,
        output_root=args.output_root,
        stack_id=args.stack_id,
        sdk_element=args.sdk_element,
        policy_file=args.policy_file,
    )


class BuildStreamGenerator:
    def __init__(self, options: BstGenerateOptions):
        self.options = options
        self.context = self._load_context()
        self.policy = GenerationPolicy.from_path(options.policy_file)
        self.module_resolver = self._load_module_resolver()

    def run(self) -> int:
        root_identifiers = self._resolve_requested_projects(self.options.projects)
        root_modules: list[Module] = []
        for root_identifier in root_identifiers:
            root_module = self.module_resolver.resolve_module_if_present(root_identifier)
            if root_module is None:
                raise KBRuntimeError(f"Unable to load KDE project {root_identifier}")
            root_modules.append(root_module)

        graph = self._resolve_dependency_graph(root_modules)
        ordered_modules = DependencyResolver.sort_modules_into_build_order(graph)
        generated_modules = [module for module in ordered_modules if module.is_kde_project()]
        output_root = Path(self.options.output_root)

        for module in generated_modules:
            self._write_module_element(output_root, graph, module)

        self._write_root_stack(output_root, generated_modules, root_identifiers)
        return 0

    def _load_context(self) -> BuildContext:
        ctx = BuildContext()
        ctx.set_option("branch-group", self.options.branch_group)
        ctx.set_metadata_module()
        self._configure_generator_paths(ctx)
        self._download_metadata_if_needed(ctx)
        ctx.set_metadata()
        return ctx

    def _load_module_resolver(self) -> ModuleResolver:
        ctx = self.context
        build_config = self._branch_group_build_config_path()
        if Debug().is_testing() and not os.path.exists(build_config):
            return ModuleResolver(ctx)

        ctx.rc_file = self._write_generator_rc_file()
        modules_and_sets, overrides = Application._process_configs_content(ctx, ctx.rc_file, {})
        module_resolver = ModuleResolver(ctx)
        module_resolver.cmdline_per_project_options = {}
        module_resolver.set_deferred_options(overrides)
        module_resolver.set_initial_projects_and_groups(modules_and_sets)
        module_resolver.handle_initial_projects()
        module_resolver.ignored_selectors = set()
        module_resolver.expand_all_groups()
        return module_resolver

    def _write_generator_rc_file(self) -> str:
        state_root = os.path.join(self.options.output_root, ".kde-builder")
        os.makedirs(state_root, exist_ok=True)

        build_config = self._branch_group_build_config_path()
        config_text = (
            "config-version: 2\n"
            "global:\n"
            f"  persistent-data-file: {state_root}/persistent.json\n"
            f"include {build_config}: \"\"\n"
        )

        with tempfile.NamedTemporaryFile(
            mode="w",
            delete=False,
            dir=state_root,
            prefix="bst-generate-",
            suffix=".yaml",
        ) as temp_file:
            temp_file.write(config_text)
            return temp_file.name

    def _branch_group_build_config_path(self) -> str:
        repo_metadata_path = self._repo_metadata_path()
        if "kf6" in self.options.branch_group:
            config_name = "kde6.yaml"
        elif "kf5" in self.options.branch_group:
            config_name = "kde5.yaml"
        else:
            raise KBRuntimeError(f"Unsupported branch group for build-config selection: {self.options.branch_group}")
        return os.path.join(repo_metadata_path, "build-configs", config_name)

    def _repo_metadata_path(self) -> str:
        if Debug().is_testing():
            return os.path.normpath(os.path.dirname(os.path.realpath(__file__)) + "/../tests/fixtures/repo-metadata")
        return self.context.metadata_module.fullpath("source")

    def _configure_generator_paths(self, ctx: BuildContext) -> None:
        state_root = os.path.join(self.options.output_root, ".kde-builder")
        metadata_module = ctx.metadata_module
        if metadata_module is None:
            raise KBRuntimeError("Metadata module was not initialized")

        ctx.set_option("log-dir", os.path.join(state_root, "log"))
        metadata_module.set_option("log-dir", os.path.join(state_root, "log"))

        existing_checkout = metadata_module.fullpath("source")
        if os.path.exists(existing_checkout):
            ctx.set_option("no-metadata", True)
            return

        metadata_module.set_option("source-dir", state_root)

    def _download_metadata_if_needed(self, ctx: BuildContext) -> None:
        if Debug().is_testing():
            return

        metadata_module = ctx.metadata_module
        if metadata_module is None:
            raise KBRuntimeError("Metadata module was not initialized")

        source_dir = metadata_module.get_source_dir()
        if not Util.super_mkdir(source_dir):
            raise KBRuntimeError(f"Could not create {source_dir} directory")

        module_source = metadata_module.fullpath("source")
        update_desired = not ctx.get_option("no-metadata")
        update_needed = (not os.path.exists(module_source)) or (not os.listdir(module_source))

        if not update_desired and not update_needed:
            return

        Updater.verify_git_config(ctx)
        original_dir = os.getcwd()
        try:
            metadata_module.current_phase = "update"
            metadata_module.scm.update_internal()
        finally:
            metadata_module.current_phase = None
            Util.p_chdir(original_dir)

        if update_needed and ((not os.path.exists(module_source)) or (not os.listdir(module_source))):
            raise KBRuntimeError("Metadata download did not produce a usable checkout")

    def _resolve_requested_project(self, requested_project: str) -> str:
        repositories = self.context.projects_db.repositories
        if requested_project in repositories:
            identifier = requested_project
        else:
            try:
                matches = self.context.projects_db.get_identifiers_for_selector(requested_project, [])
            except NoKDEProjectsFound as exc:
                raise KBRuntimeError(f"Project {requested_project} is not defined in repo-metadata") from exc
            if len(matches) != 1:
                raise KBRuntimeError(f"Project selector {requested_project} is ambiguous")
            identifier = matches[0]

        project = repositories.get(identifier)
        if project is None:
            raise KBRuntimeError(f"Project {requested_project} is not defined in repo-metadata")
        if not project.get("active"):
            raise KBRuntimeError(f"Project {identifier} is inactive in repo-metadata")

        repopath = str(project["invent_name"])
        if self._is_ignored_repopath(repopath, self.context.metadata.ignored_projects):
            raise KBRuntimeError(f"Project {identifier} is ignored by repo-metadata policy")

        branch = self.resolve_branch(identifier, repopath)
        if not branch:
            raise KBRuntimeError(f"Project {identifier} does not resolve to a branch for {self.options.branch_group}")

        return identifier

    def _resolve_requested_projects(self, requested_projects: list[str]) -> list[str]:
        resolved_projects: list[str] = []
        seen = set()
        for requested_project in requested_projects:
            identifier = self._resolve_requested_project(requested_project)
            if identifier in seen:
                continue
            seen.add(identifier)
            resolved_projects.append(identifier)
        return resolved_projects

    @staticmethod
    def _is_ignored_repopath(repopath: str, ignored_projects: list[str]) -> bool:
        return any(re.search(rf"(^|/){re.escape(item)}($|/)", repopath) for item in ignored_projects)

    def _resolve_dependency_graph(self, modules: list[Module]) -> dict:
        dependency_resolver = DependencyResolver(self.module_resolver)
        repo_metadata_path = self._repo_metadata_path()
        if Debug().is_testing():
            dependency_file = f"{repo_metadata_path}/kde-dependencies/kde-dependencies"
        else:
            dependency_file = f"{repo_metadata_path}/kde-dependencies/kde-dependencies-{self.options.branch_group}"

        with open(dependency_file, "r") as dependencies:
            dependency_resolver.read_dependency_data(dependencies)

        result = dependency_resolver.resolve_to_module_graph(modules)
        graph = result.get("graph")
        if not graph:
            raise KBRuntimeError("Unable to resolve dependency graph for bst-generate")
        return graph

    def resolve_branch(self, identifier: str, repopath: str) -> str:
        branch = self.context.branch_group_resolver.resolve_branch_group(repopath, self.options.branch_group)
        if not branch:
            raise KBRuntimeError(f"Project {identifier} does not resolve to a branch for {self.options.branch_group}")
        return branch

    def resolve_git_ref(self, repo_url: str, branch: str) -> str:
        result = subprocess.run(
            ["git", "ls-remote", repo_url, branch],
            capture_output=True,
            text=True,
            check=False,
        )
        if result.returncode != 0:
            stderr = result.stderr.strip()
            raise KBRuntimeError(f"git ls-remote failed for {repo_url} {branch}: {stderr or result.returncode}")

        for line in result.stdout.splitlines():
            if not line.strip():
                continue
            sha, _sep, _ref = line.partition("\t")
            if sha:
                return sha

        raise KBRuntimeError(f"git ls-remote did not return a ref for {repo_url} {branch}")

    def _write_module_element(self, output_root: Path, graph: dict, module: Module) -> None:
        identifier = module.name
        repopath = module.get_repopath()
        if repopath is None:
            raise KBRuntimeError(f"Generated module {identifier} is missing a KDE repopath")

        branch = self.resolve_branch(identifier, repopath)
        repo_url = f"kde:{repopath}.git"
        git_ref = self.resolve_git_ref(repo_url, branch)

        build_depends = self._build_depends_for_module(graph, identifier)

        element: dict[str, Any] = {
            "kind": "cmake",
            "description": f"Generated from kde-builder metadata for {identifier}",
            "sources": [
                {
                    "kind": "git",
                    "url": repo_url,
                    "track": branch,
                    "ref": git_ref,
                    "ref-format": "sha1",
                }
            ],
            "build-depends": build_depends,
        }

        cmake_options = module.get_option("cmake-options")
        if isinstance(cmake_options, str) and cmake_options:
            element["variables"] = {
                "cmake-local": cmake_options,
            }

        output_path = output_root / self.options.stack_id / f"{identifier}.bst"
        self._write_yaml(output_path, element)

    def _build_depends_for_module(self, graph: dict, identifier: str) -> list[str]:
        deps = [
            self.options.sdk_element,
        ]

        for dep_item in sorted(graph[identifier]["deps"].keys()):
            dep_info = graph[identifier]["deps"][dep_item]
            dep_graph = graph.get(dep_item)
            if dep_graph is None:
                raise KBRuntimeError(f"Dependency graph entry missing for {dep_item}")

            dep_path = dep_graph["path"] or dep_info["path"]
            mapped_dep = (
                self.policy.third_party_map.get(dep_path)
                or self.policy.third_party_map.get(f"third-party/{dep_item}")
                or self.policy.third_party_map.get(dep_item)
            )
            if dep_path.startswith("third-party/") or dep_graph["module"] is None:
                if mapped_dep is None:
                    raise KBRuntimeError(
                        f"Missing third-party mapping for dependency {dep_path} of {identifier}. "
                        f"Add a third_party_map entry for one of: {dep_path}, third-party/{dep_item}, or {dep_item}"
                    )
                deps.append(mapped_dep)
                continue

            deps.append(self.module_element_name(dep_item))

        return self._stable_unique(deps)

    def _write_root_stack(self, output_root: Path, ordered_modules: list[Module], root_identifiers: list[str]) -> None:
        if len(root_identifiers) == 1:
            description = f"Generated stack for {root_identifiers[0]} ({self.options.branch_group})"
        else:
            description = f"Generated stack for {', '.join(root_identifiers)} ({self.options.branch_group})"
        stack = {
            "kind": "stack",
            "description": description,
            "depends": [self.module_element_name(module.name) for module in ordered_modules],
        }
        self._write_yaml(output_root / f"{self.options.stack_id}.bst", stack)

    def module_element_name(self, identifier: str) -> str:
        return f"{self.options.stack_id}/{identifier}.bst"

    @staticmethod
    def _stable_unique(items: list[str]) -> list[str]:
        seen = set()
        result = []
        for item in items:
            if item in seen:
                continue
            seen.add(item)
            result.append(item)
        return result

    @staticmethod
    def _bst_sort(data: dict[str, Any]) -> dict[str, Any]:
        def sort_key(key: str) -> tuple[int, str]:
            if key in BST_SORT_PRIORITY:
                return (BST_SORT_PRIORITY.index(key), key)
            return (len(BST_SORT_PRIORITY), key)

        return dict(sorted(data.items(), key=lambda item: sort_key(item[0])))

    @staticmethod
    def _write_yaml(path: Path, data: dict[str, Any]) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "w", encoding="utf-8") as fh:
            fh.write("# File generated by kde-builder\n\n")
            yaml.dump(
                BuildStreamGenerator._bst_sort(data),
                fh,
                default_flow_style=False,
                sort_keys=False,
                allow_unicode=True,
            )


def run_bst_generate_cli(argv: list[str]) -> int:
    options = parse_bst_generate_args(argv)
    generator = BuildStreamGenerator(options)
    return generator.run()
