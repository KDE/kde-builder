# SPDX-FileCopyrightText: 2012, 2013, 2014, 2015, 2017, 2018, 2019, 2020, 2021, 2022 Michael Pyne <mpyne@kde.org>
# SPDX-FileCopyrightText: 2020 Johan Ouwerkerk <jm.ouwerkerk@gmail.com>
# SPDX-FileCopyrightText: 2023 - 2024 Andrew Shark <ashark@linuxcomp.ru>
#
# SPDX-License-Identifier: GPL-2.0-or-later

from __future__ import annotations

import inspect
import os.path
import re
import subprocess
import time
from typing import TYPE_CHECKING

from ..kb_exception import KBRuntimeError
from ..kb_exception import ConfigError
from ..kb_exception import ProgramError
from ..debug import Debug
from ..debug import KBLogger
from ..ipc.null import IPCNull
from ..util.logged_subprocess import UtilLoggedSubprocess
from ..util.util import Util
from ..util.textwrap_mod import textwrap

if TYPE_CHECKING:
    from typing import NoReturn
    from ..build_context import BuildContext
    from ..ipc.ipc import IPC
    from ..module.module import Module

logger_updater = KBLogger.getLogger("updater")


class Updater:
    """
    Responsible for updating git-based source code modules.

    Can have some features overridden by subclassing (see UpdaterKDEProject for an example).
    """

    DEFAULT_GIT_REMOTE = "origin"

    def __init__(self, module: Module):
        self.module = module
        self.ipc: IPC | None = None

    def update_internal(self, ipc=IPCNull()) -> int:
        """
        scm-specific update procedure.

        May change the current directory as necessary.

        Returns:
             Number of commits pulled.
        """
        self.ipc = ipc
        num_commits = self.update_checkout()
        self.ipc = None
        return num_commits

    @staticmethod
    # @override(check_signature=False)
    def name() -> str:
        return "git"

    def _resolve_branch_group(self, branch_group: str) -> NoReturn:
        raise KBRuntimeError("\t_resolve_branch_group is implemented in UpdaterKDEProject.")

    def current_revision_internal(self) -> str:
        return self.commit_id("HEAD")

    def commit_id(self, commit: str) -> str:
        """
        Return the current sha1 of the given git "commit-ish".
        """
        if commit is None:
            raise ProgramError("\tMust specify git-commit to retrieve id for")
        module = self.module

        gitdir = module.fullpath("source") + "/.git"

        # Note that the --git-dir must come before the git command itself.
        an_id = Util.filter_program_output(None, *["git", "--git-dir", gitdir, "rev-parse", commit])
        if an_id:
            an_id = an_id[0].removesuffix("\n")
        else:
            an_id = ""  # if it was empty list, make it str

        return an_id

    def _verify_ref_present(self, module: Module, repo: str) -> bool:
        ref, commit_type = self.determine_preferred_checkout_source(module)

        if Debug().pretending():
            return True

        if commit_type == "none":
            ref = "HEAD"

        process = subprocess.Popen(f"git ls-remote --exit-code {repo} {ref}".split(" "), stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        try:
            _, _ = process.communicate(timeout=10)
            result = process.returncode
        except subprocess.TimeoutExpired:
            process.kill()
            _, _ = process.communicate()
            result = -1

        if result == 2:  # Connection successful, but ref not found
            return False
        if result == 0:  # Ref is present
            return True

        raise KBRuntimeError(f"\tgit had error exit {result} when verifying {ref} present in repository at {repo}")

    def _clone(self, git_repo: str) -> int:
        """
        Perform a git clone to checkout the latest branch of a given git module.

        Args:
            git_repo: The repository (typically URL) to use.

        Returns:
            int: 1

        Raises:
             Exception: If an error occurs.
        """
        module = self.module
        srcdir = module.fullpath("source")
        args = ["--", git_repo, srcdir]

        if not self.ipc:
            raise ProgramError("\tMissing IPC object")
        ipc = self.ipc

        logger_updater.warning(f"\tCloning g[{module}]")

        Util.p_chdir(module.get_source_dir())

        commit_id, commit_type = self.determine_preferred_checkout_source(module)

        if commit_type != "none":
            commit_id = re.sub(r"^refs/tags/", "", commit_id)  # git-clone -b doesn't like refs/tags/
            args.insert(0, commit_id)  # Checkout branch right away
            args.insert(0, "-b")

        exitcode = Util.run_logged(module, "git-clone", module.get_source_dir(), ["git", "clone", "--recursive", *args])

        if not exitcode == 0:
            raise KBRuntimeError("\tFailed to make initial clone of project")

        ipc.notify_persistent_option_change(module.name, "git-cloned-repository", git_repo)

        Util.p_chdir(srcdir)

        # Setup user configuration
        if name := module.get_option("git-user"):
            username, email = None, None
            match = re.match(r"^([^<]+) +<([^>]+)>$", name)
            if match:
                username, email = match.groups()

            if not username or not email:
                raise KBRuntimeError(f"\tInvalid username or email for git-user option: {name}" +
                                     " (should be in format 'User Name <username@example.net>'")

            logger_updater.debug(f"\tAdding git identity {name} for project {module}")
            result = Util.safe_system(["git", "config", "--local", "user.name", username])
            result = Util.safe_system(["git", "config", "--local", "user.email", email]) or result
            if result:
                logger_updater.warning(f"\tUnable to set user.name and/or user.email git config for y[b[{module}]!")
        return 1  # success

    @staticmethod
    def _verify_safe_to_clone_into_source_dir(module: Module, srcdir: str) -> None:
        """
        Check that the required source dir is either not already present or is empty.

        Throws an exception if that's not true.
        """
        if os.path.exists(f"{srcdir}") and os.listdir(srcdir):
            logger_updater.error(textwrap.dedent(f"""\
            \tr[*] The desired source directory for b[{module}] is: y[b[{srcdir}]
            \tr[*] This directory already exists, but it is not empty, and it is not a git repository."""))
            raise KBRuntimeError("\tUnrecognised content in source-dir present")

    def update_checkout(self) -> int:
        """
        Either performs the initial checkout or updates the current git checkout as appropriate.

        Returns:
             Number of commits pulled.
             If not cloned yet, and in pretending mode, pretends that 1 commit was pulled.
             If already cloned, and in pretending mode, pretends that 0 commits were pulled.

        Raises:
             Exception: On an update error.
        """
        module = self.module
        srcdir = module.fullpath("source")

        git_repo: str = module.get_option("#resolved-repository")
        if not git_repo:
            msg = textwrap.dedent(f"""\
                \tThere was no y[b[repository] specified for the {module.name}.
                \tSee https://kde-builder.kde.org/en/getting-started/kde-projects-and-selection.html#groups\
                """)
            raise ConfigError(msg)

        # While .git is usually a directory, it can also be a file in case of a
        # worktree checkout (https://git-scm.com/docs/gitrepository-layout)
        if os.path.exists(f"{srcdir}/.git"):
            # Note that this function will throw an exception on failure.
            return self.update_existing_clone()
        else:
            self._verify_safe_to_clone_into_source_dir(module, srcdir)

            if not self._verify_ref_present(module, git_repo):
                raise KBRuntimeError(f"\t{module} build was requested, but it has no source code at the requested git branch")

            self._clone(git_repo)  # can handle pretending mode
            if Debug().pretending():
                return 1  # pretend like there was 1 commit pulled
            else:
                ret = int(subprocess.check_output(["git", "--git-dir", f"{srcdir}/.git", "rev-list", "HEAD", "--count"]).decode().strip())
                return ret

    @staticmethod
    def is_push_url_managed() -> bool:
        """
        Determine whether _setup_remote should manage the configuration of the git push URL for the repo.

        Returns:
             Boolean indicating whether _setup_remote should assume control over the push URL.
        """
        return False

    def _setup_remote(self, remote: str) -> int:
        """
        Ensure the given remote is pre-configured for the module's git repository.

        The remote is either set up from scratch or its URLs are updated.

        Args:
            remote: name (alias) of the remote to configure

        Returns 1 or raises exception on an error.
        """
        module = self.module
        repo = module.get_option("#resolved-repository")
        has_old_remote = self.has_remote(remote)

        if has_old_remote:
            logger_updater.debug(f"\tUpdating the URL for git remote {remote} of {module} ({repo})")
            exitcode = Util.run_logged(module, "git-fix-remote", None, ["git", "remote", "set-url", remote, repo])
            if not exitcode == 0:
                raise KBRuntimeError(f"\tUnable to update the URL for git remote {remote} of {module} ({repo})")
        else:
            logger_updater.debug(f"\tAdding new git remote {remote} of {module} ({repo})")
            exitcode = Util.run_logged(module, "git-add-remote", None, ["git", "remote", "add", remote, repo])
            if not exitcode == 0:
                raise KBRuntimeError(f"\tUnable to add new git remote {remote} of {module} ({repo})")

        # If we make it here, no exceptions were thrown
        if not self.is_push_url_managed():
            return 1

        # pushInsteadOf does not work nicely with git remote set-url --push
        # The result would be that the pushInsteadOf kde: prefix gets ignored.
        #
        # The next best thing is to remove any preconfigured pushurl and
        # restore the kde: prefix mapping that way.  This is effectively the
        # same as updating the push URL directly because of the remote set-url
        # executed previously by this function for the fetch URL.

        existing_push_url = subprocess.run(f"git config --get remote.{remote}.pushurl", shell=True, capture_output=True, text=True).stdout.strip()

        if not existing_push_url:
            return 1

        logger_updater.info(f"\tRemoving preconfigured push URL for git remote {remote} of {module}: {existing_push_url}")

        exitcode = Util.run_logged(module, "git-fix-remote", None, ["git", "config", "--unset", f"remote.{remote}.pushurl"])
        if not exitcode == 0:
            raise KBRuntimeError(f"\tUnable to remove preconfigured push URL for {module}!")
        return 1  # overall success

    def _setup_best_remote(self) -> str:
        """
        Select a git remote for the user's selected repository (preferring a defined remote if available, using "origin" otherwise).

        Assumes the current directory is already set to the source directory.

        Returns the name of the remote (which will be setup by kde-builder) to use for updates, or raises exception on an error.

        See also the "repository" module option.
        """
        module = self.module
        cur_repo = module.get_option("#resolved-repository")
        if not self.ipc:
            raise ProgramError("\tMissing IPC object")
        ipc = self.ipc

        # Search for an existing remote name first. If none, add our alias.
        remote_names = self.best_remote_name()
        chosen_remote = remote_names[0] if remote_names else Updater.DEFAULT_GIT_REMOTE

        self._setup_remote(chosen_remote)

        # Make a notice if the repository we're using has moved.
        old_repo = module.get_persistent_option("git-cloned-repository")
        if old_repo and (cur_repo != old_repo):
            logger_updater.warning(f"\ty[b[*]\ty[{module}]'s selected repository has changed")
            logger_updater.warning(f"\ty[b[*]\tfrom y[{old_repo}]")
            logger_updater.warning(f"\ty[b[*]\tto   b[{cur_repo}]")
            logger_updater.warning("\ty[b[*]\tThe git remote named b[" + Updater.DEFAULT_GIT_REMOTE + "] has been updated")

            # Update what we think is the current repository on-disk.
            ipc.notify_persistent_option_change(module.name, "git-cloned-repository", cur_repo)
        return chosen_remote

    def _warn_if_stashed_from_wrong_branch(self, remote_name: str, branch: str, branch_name: str) -> bool:
        """
        Return true if there is a git stash active from the wrong branch, so we don't mistakenly try to apply the stash after we switch branch.
        """
        module = self.module

        # Check if this branch_name we want was already the branch we were on. If
        # not, and if we stashed local changes, then we might dump a bunch of
        # conflicts in the repo if we un-stash those changes after a branch switch.
        # See issue #67.
        existing_branch = next(iter(Util.filter_program_output(None, "git", "branch", "--show-current")), None)
        if existing_branch is not None:
            existing_branch = existing_branch.removesuffix("\n")

        # The result is empty if in "detached HEAD" state where we should also
        # clearly not switch branches if there are local changes.
        if module.get_option("#git-was-stashed") and (not existing_branch or (existing_branch != branch_name)):

            # Make error message make more sense
            if not existing_branch:
                existing_branch = "Detached HEAD"
            if not branch_name:
                branch_name = f"New branch to point to {remote_name}/{branch}"

            logger_updater.info(textwrap.dedent(f"""\
                \ty[b[*] The project y[b[{module}] had local changes from a different branch than expected:
                \ty[b[*]   Expected branch: b[{branch_name}]
                \ty[b[*]   Actual branch:   b[{existing_branch}]
                \ty[b[*]
                \ty[b[*] To avoid conflict with your local changes, b[{module}] will not be updated, and the
                \ty[b[*] branch will remain unchanged, so it may be out of date from upstream.
                """))

            self._notify_post_build_message(f" y[b[*] b[{module}] was not updated as it had local changes against an unexpected branch.")
            return True
        return False

    def _update_to_remote_head(self, remote_name: str, branch: str) -> int:
        """
        Completes the steps needed to update a git checkout to be checked-out to a given remote-tracking branch.

        Any existing local branch with the given
        branch set as upstream will be used if one exists, otherwise one will be
        created. The given branch will be rebased into the local branch.

        No checkout is done, this should be performed first.
        Assumes we're already in the needed source dir.
        Assumes we're in a clean working directory (use git-stash to achieve if necessary).

        Args:
            remote_name: The remote to use.
            branch: The branch to update to.

        Returns:
             boolean success flag.
        Exception may be thrown if unable to create a local branch.
        """
        module = self.module

        # "branch" option requests a given remote head in the user's selected
        # repository. The local branch with "branch" as upstream might have a
        # different name. If there's no local branch this method creates one.
        branch_name = self.get_remote_branch_name(remote_name, branch)

        if self._warn_if_stashed_from_wrong_branch(remote_name, branch, branch_name):
            return 0

        croak_reason = None
        result = None
        cmd = UtilLoggedSubprocess().module(module).chdir_to(module.fullpath("source"))

        if not branch_name:
            new_name = self.make_branchname(remote_name, branch)

            def announcer_sub(_):
                # pl2py: despite in perl this sub had no arguments, it is called with one argument, so we add unused argument here
                logger_updater.debug(f"\tUpdating g[{module}] with new remote-tracking branch y[{new_name}]")

            cmd.log_to("git-checkout-branch") \
                .set_command(["git", "checkout", "-b", new_name, f"{remote_name}/{branch}"]) \
                .announcer(announcer_sub)

            croak_reason = f"\tUnable to perform a git checkout of {remote_name}/{branch} to a local branch of {new_name}"
            result = cmd.start()
        else:
            def announcer_sub(_):
                # pl2py: despite in perl this sub had no arguments, it is called with one argument, so we add unused argument here
                logger_updater.debug(f"\tUpdating g[{module}] using existing branch g[{branch_name}]")

            cmd.log_to("git-checkout-update") \
                .set_command(["git", "checkout", branch_name]) \
                .announcer(announcer_sub)

            croak_reason = f"\tUnable to perform a git checkout to existing branch {branch_name}"

            result = cmd.start()

            if not result == 0:
                pass
            else:
                croak_reason = f"\t{module}: Unable to reset to remote development branch {branch}"

                # Given that we're starting with a "clean" checkout, it's now simply a fast-forward
                # to the remote HEAD (previously we pulled, incurring additional network I/O).
                result = Util.run_logged(module, "git-rebase", None, ["git", "reset", "--hard", f"{remote_name}/{branch}"])

        if not result == 0:
            raise KBRuntimeError(croak_reason)
        return 1  # success

    def _update_to_detached_head(self, commit: str) -> int:
        """
        Completes the steps needed to update a git checkout to be checked-out to a given commit.

        The local checkout is left in a detached HEAD state,
        even if there is a local branch which happens to be pointed to the
        desired commit. Based the given commit is used directly, no rebase/merge
        is performed.

        No checkout is done, this should be performed first.
        Assumes we're already in the needed source dir.
        Assumes we're in a clean working directory (use git-stash to achieve if necessary).

        Args:
            commit: The commit to update to. This can be in pretty
                much any format that git itself will respect (e.g. tag, sha1, etc.).
                It is recommended to use refs/foo/bar syntax for specificity.

        Returns:
             boolean success flag.
        """
        module = self.module
        srcdir = module.fullpath("source")

        logger_updater.info(f"\tDetaching head to b[{commit}]")

        result = Util.run_logged(module, "git-checkout-commit", srcdir, ["git", "checkout", commit])
        result = result == 0  # need to adapt to boolean success flag
        return result

    def update_existing_clone(self) -> int:
        """
        Update an already existing git checkout by running git pull.

        Returns:
             Number of pulled commits.

        Raises:
            Exception: On an error.
        """
        module = self.module
        cur_repo = module.get_option("#resolved-repository")

        Util.p_chdir((module.fullpath("source")))

        if module.get_option("hold-work-branches"):
            current_branch = subprocess.run(f"git branch --show-current", shell=True, capture_output=True, text=True).stdout.strip()
            if current_branch.startswith("work/") or current_branch.startswith("mr/"):
                logger_updater.warning(f"\tHolding g[{module}] at branch b[{current_branch}]")
                return 0

        # Try to save the user if they are doing a merge or rebase
        if os.path.exists(".git/MERGE_HEAD") or os.path.exists(".git/rebase-merge") or os.path.exists(".git/rebase-apply"):
            raise KBRuntimeError(f"\tAborting git update for {module}, you appear to have a rebase or merge in progress!")

        remote_name = self._setup_best_remote()
        logger_updater.info(f"\tFetching remote changes to g[{module}]")
        exitcode = Util.run_logged(module, "git-fetch", None, ["git", "fetch", "-f", "--tags", remote_name])

        # Download updated objects. This also updates remote heads so do this
        # before we start comparing branches and such.

        if not exitcode == 0:
            raise KBRuntimeError(f"\tUnable to perform git fetch for {remote_name} ({cur_repo})")

        # Now we need to figure out if we should update a branch, or simply
        # checkout a specific tag/SHA1/etc.
        commit_id, commit_type = self.determine_preferred_checkout_source(module)
        if commit_type == "none":
            commit_type = "branch"
            commit_id = self._detect_default_remote_head(remote_name)

        logger_updater.warning(f"\tMerging g[{module}] changes from {commit_type} b[{commit_id}]")
        start_commit = self.commit_id("HEAD")

        self.stash_and_update(commit_type, remote_name, commit_id)
        ret = int(subprocess.check_output(["git", "rev-list", f"{start_commit}..HEAD", "--count"]).decode().strip())
        return ret

    @staticmethod
    def _detect_default_remote_head(remote_name: str) -> str:
        """
        Try to determine the best remote branch name to use as a default if the user hasn't selected one.

        Determination is done by resolving the remote symbolic ref "HEAD" from
        its entry in the .git dir. This can also be found by introspecting the
        output of "git remote show $REMOTE_NAME" or "git branch -r" but these are
        incredibly slow.
        """
        if not os.path.isdir(".git"):
            caller_name = inspect.currentframe().f_back.f_code.co_name
            raise ProgramError("\tRun " + caller_name + " from git repo!")

        with open(f".git/refs/remotes/{remote_name}/HEAD", "r") as file:
            data = file.read()

        if not data:
            data = ""

        match = re.search(r"^ref: *refs/remotes/[^/]+/([^/]+)$", data)
        head = match.group(1) if match else None
        if not head:
            raise KBRuntimeError(f"\tCan't find HEAD for remote {remote_name}")

        head = head.removesuffix("\n")
        return head

    def determine_preferred_checkout_source(self, module: Module | None = None) -> tuple:
        """
        Goes through all the various combination of git checkout selection options in various orders of priority.

        Returns a *list* containing: (the resultant symbolic ref/or SHA1,"branch" or
        "tag" (to determine if something like git-pull would be suitable or whether
        you have a detached HEAD)). Since the sym-ref is returned first that should
        be what you get in a scalar context, if that's all you want.
        """
        if not module:
            module = self.module

        priority_ordered_sources = [
            #   option-name    type   get_option-inheritance-flag
            ["commit", "tag", "module"],
            ["revision", "tag", "module"],
            ["tag", "tag", "module"],
            ["branch", "branch", "module"],
            ["branch-group", "branch", "module"],
            # commit/rev/tag don't make sense for git as globals
            ["branch", "branch", "allow-inherit"],
            ["branch-group", "branch", "allow-inherit"],
        ]

        # For modules that are not actually a "proj" module we skip branch-group
        # entirely to allow for global/module branch selection
        # options to be selected... kind of complicated, but more DWIMy
        from .kde_project import UpdaterKDEProject
        if not isinstance(module.scm(), UpdaterKDEProject):
            priority_ordered_sources = [priorityOrderedSource for priorityOrderedSource in priority_ordered_sources if priorityOrderedSource[0] != "branch-group"]

        checkout_source = None
        # easiest way to be clear that bool context is intended

        source_type = next((x for x in priority_ordered_sources if (checkout_source := module.get_option(x[0], x[2]))), None)  # Note that we check for truth of get_option, not if it is None, because we want to treat empty string also as false

        # The user has no clear desire here (either set for the module or globally.
        # Note that the default config doesn't generate a global "branch" setting).
        # In this case it's unclear which convention source modules will use between
        # "master", "main", or something entirely different.  So just don't guess...
        if not source_type:
            logger_updater.debug(f"\tNo branch specified for {module}, will use whatever git gives us")
            return "none", "none"

        # Likewise branch-group requires special handling. checkout_source is
        # currently the branch-group to be resolved.
        if source_type[0] == "branch-group":
            # noinspection PyUnreachableCode
            checkout_source = self._resolve_branch_group(checkout_source)

            if not checkout_source:
                branch_group = module.get_option("branch-group")
                logger_updater.debug(f"\tNo specific branch set for {module} and {branch_group}, using master!")
                checkout_source = "master"

        if source_type[0] == "tag" and not checkout_source.startswith("^refs/tags/"):
            checkout_source = f"refs/tags/{checkout_source}"

        return checkout_source, source_type[1]

    @staticmethod
    def _has_submodules() -> bool:
        """
        Try to check whether the git module is using submodules or not.

        Currently, we just check the .git/config file (using git-config) to determine whether
        there are any "active" submodules.

        MUST BE RUN FROM THE SOURCE DIR
        """
        # The git-config line shows all option names of the form submodule.foo.active,
        # filtering down to options for which the option is set to "true"
        config_lines = Util.filter_program_output(None, "git", "config", "--local", "--get-regexp", r"^submodule\..*\.active", "true")
        return len(config_lines) > 0

    @staticmethod
    def _split_uri(uri) -> tuple[str, str, str, str, str]:
        match = re.match(r"(?:([^:/?#]+):)?(?://([^/?#]*))?([^?#]*)(?:\?([^#]*))?(?:#(.*))?", uri)
        scheme, authority, path, query, fragment = match.groups()
        return scheme, authority, path, query, fragment

    def count_stash(self, description=None) -> int:
        module = self.module

        if os.path.exists(".git/refs/stash"):
            p = subprocess.run("git rev-list --walk-reflogs --count refs/stash", shell=True, text=True, capture_output=True)
            print(p.stderr, end="")  # pl2py: in case git warns about something, for example about deprecated grafts. Unfortunately, subprocess washes the colors, but not a big deal.
            count = p.stdout
            if count:
                count = count.removesuffix("\n")
            logger_updater.debug(f"\tNumber of stashes found for b[{module}] is: b[{count}]")
            return int(count)
        else:
            logger_updater.debug(f"\tIt appears there is no stash for b[{module}]")
            return 0

    def _notify_post_build_message(self, mesg: str) -> None:
        """
        Send a post-build (warning) message via the IPC object.

        This just takes care of the boilerplate to forward its arguments as message.
        """
        module = self.module
        self.ipc.notify_new_post_build_message(module.name, mesg)

    def stash_and_update(self, commit_type: str, remote_name: str, commit_id: str) -> int:
        """
        Stashes existing changes if necessary, and then runs appropriate update function.

        Update function (_update_to_remote_head or _update_to_detached_head) is run in order to advance the given module to the desired head.
        Finally, if changes were stashed, they are applied and the stash stack is popped.

        It is assumed that the required remote has been set up already, that we
        are on the right branch, and that we are already in the correct
        directory.

        Returns:
             1 or raises exception on error.
        """
        module = self.module
        date = time.strftime("%F-%R", time.gmtime())  # ISO Date, hh:mm time
        stash_name = f"kde-builder auto-stash at {date}"

        # first, log the git status prior to kde-builder taking over the reins in the repo
        result = Util.run_logged(module, "git-status-before-update", None, ["git", "status"])

        old_stash_count = self.count_stash()

        # always stash:
        # - also stash untracked files because what if upstream started to track them
        # - we do not stash .gitignore'd files because they may be needed for builds?
        #   on the other hand that leaves a slight risk if upstream altered those
        #   (i.e. no longer truly .gitignore'd)
        logger_updater.debug("\tStashing local changes if any...")

        if Debug().pretending():  # probably best not to do anything if pretending
            result = 0
        else:
            result = Util.run_logged(module, "git-stash-push", None, ["git", "stash", "push", "-u", "--quiet", "--message", stash_name])

        if result == 0:
            pass
        else:
            # Might happen if the repo is already in merge conflict state.
            # We could mark everything as resolved using git add . before stashing,
            # but that might not always be appreciated by people having to figure
            # out what the original merge conflicts were afterwards.
            self._notify_post_build_message(f"\tb[{module}] may have local changes that we couldn't handle, so the project was left alone.")

            result = Util.run_logged(module, "git-status-after-error", None, ["git", "status"])
            raise KBRuntimeError(f"\tUnable to stash local changes (if any) for {module}, aborting update.")

        # next: check if the stash was truly necessary.
        # compare counts (not just testing if there is *any* stash) because there
        # might have been a genuine user's stash already prior to kde-builder
        # taking over the reins in the repo.
        new_stash_count = self.count_stash()

        # mark that we applied a stash so that $updateSub (_update_to_remote_head or
        # _update_to_detached_head) can know not to do dumb things
        if new_stash_count != old_stash_count:
            module.set_option("#git-was-stashed", True)

        # finally, update to remote head
        if commit_type == "branch":
            result = self._update_to_remote_head(remote_name, commit_id)
        else:
            result = self._update_to_detached_head(commit_id)

        if result:
            result = 1
        else:
            result = Util.run_logged(module, "git-status-after-error", None, ["git", "status"])
            raise KBRuntimeError(f"\tUnable to update source code for {module}")

        # we ignore git-status exit code deliberately, it's a debugging aid

        if new_stash_count == old_stash_count:
            result = 1  # success
        else:
            # If the stash had been needed then try to re-apply it before we build, so
            # that KDE developers working on changes do not have to manually re-apply.
            exitcode = Util.run_logged(module, "git-stash-pop", None, ["git", "stash", "pop"])
            if exitcode != 0:
                message = f"\tr[b[*] Unable to restore local changes for b[{module}]! " + \
                          f"You should manually inspect the new stash: b[{stash_name}]"
                logger_updater.warning(f"\t{message}")
                self._notify_post_build_message(message)
            else:
                logger_updater.info(f"\tb[*] You had local changes to b[{module}], which have been re-applied.")

            result = 1  # success

        return result

    def get_remote_branch_name(self, remote_name: str, branch_name: str) -> str:
        """
        Find an existing remote-tracking branch name for the given repository's named remote.

        For instance if the user was using the
        local remote-tracking branch called "qt-stable" to track kde-qt's master
        branch, this function would return the branchname "qt-stable" when
        passed kde-qt and "master".

        The current directory must be the source directory of the git module.

        Args:
            remote_name: The git remote to use (normally origin).
            branch_name: The remote head name to find a local branch for.

        Returns:
            Empty string if no match is found, or the name of the local
            remote-tracking branch if one exists.
        """
        # We'll parse git config output to search for branches that have a
        # remote of $remote_name and a "merge" of refs/heads/$branch_name.

        # TODO: Replace with git for-each-ref refs/heads and the %(upstream)
        # format.
        branches = self.slurp_git_config_output(["git", "config", "--null", "--get-regexp", r"branch\..*\.remote", remote_name])

        for git_branch in branches:
            # The key/value is \n separated, we just want the key.
            key_name = git_branch.split("\n")[0]
            this_branch = re.match(r"^branch\.(.*)\.remote$", key_name).group(1)

            # We have the local branch name, see if it points to the remote
            # branch we want.
            config_output = self.slurp_git_config_output(["git", "config", "--null", f"branch.{this_branch}.merge"])

            if config_output and config_output[0] == f"refs/heads/{branch_name}":
                # We have a winner
                return this_branch
        return ""

    def _is_plausible_existing_remote(self, name: str, url: str, configured_url: str) -> bool:
        """
        Filter for best_remote_name to determine if a given remote name and url looks like a plausible prior existing remote for a given configured repository URL.

        Note that the actual repository fetch URL is not necessarily the same as the
        configured (expected) fetch URL: an upstream might have moved, or kde-builder
        configuration might have been updated to the same effect.

        Args:
            name: name of the remote found
            url: the configured (fetch) URL
            configured_url: the configured URL for the module (the expected fetch URL).

        Returns:
             Whether the remote will be considered for best_remote_name
        """
        # name - not used, subclasses might want to filter on remote name
        return url == configured_url

    def best_remote_name(self) -> list[str]:
        """
        Return a list of all remote aliased matching the supplied repository (besides the internal alias that is).

        99% of the time the "origin" remote will be what we want anyway, and
        0.5% of the rest the user will have manually added a remote, which we
        should try to utilize when doing checkouts for instance. To aid in this, this function is run.

        Assumes that we are already in the proper source directory.

        Returns:
             A list of matching remote names (list in case the user hates us
            and has aliased more than one remote to the same repo). Obviously the list
            will be empty if no remote names were found.
        """
        module = self.module
        configured_url = module.get_option("#resolved-repository")
        outputs = []

        # The Repo URL isn't much good, let's find a remote name to use it with.
        # We'd have to escape the repo URL to pass it to Git, which I don't trust,
        # so we just look for all remotes and make sure the URL matches afterwards.
        try:
            outputs = self.slurp_git_config_output(r"git config --null --get-regexp remote\..*\.url .".split(" "))
        except Exception as e:
            print(e)
            logger_updater.error("\tUnable to run git config, is there a setup error?")
            return []

        results = []
        for output in outputs:
            # git config output between key/val is divided by newline.
            remote_name, url = output.split("\n")

            remote_name = re.sub(r"^remote\.", "", remote_name)
            remote_name = re.sub(r"\.url$", "", remote_name)  # remove the cruft

            # Skip other remotes
            if not self._is_plausible_existing_remote(remote_name, url, configured_url):
                continue

            # Try to avoid "weird" remote names.
            if not re.match(r"^[\w-]*$", remote_name):
                continue

            # A winner is this one.
            results.append(remote_name)
        return results

    def make_branchname(self, remote_name: str, branch: str) -> str:
        """
        Generate a potential new branch name for the case where we have to set up a new remote-tracking branch for a repository/branch.

        There are several criteria that go into this:
        - The local branch name will be equal to the remote branch name to match usual
          Git convention.
        - The name chosen must not already exist. This method tests for that.
        - The repo name chosen should be (ideally) a remote name that the user has
          added. If not, we'll try to autogenerate a repo name (but not add a
          remote!) based on the repository.git part of the URI.

        As with nearly all git support functions, we should be running in the
        source directory of the git module. Don't call this function unless
        you've already checked that a suitable remote-tracking branch doesn't
        exist.

        Args:
            remote_name: The name of a git remote to use.
            branch: The name of the remote head we need to make a branch name of.

        Returns:
             A useful branch name that doesn't already exist, or "" if no
            name can be generated.
        """
        if not remote_name:
            remote_name = "origin"
        module = self.module

        # Use "branch" directly if not already used, otherwise try to prefix with the remote name.
        for possible_branch in [branch, f"{remote_name}-{branch}", f"ksdc-{remote_name}-{branch}"]:
            result = subprocess.call(["git", "show-ref", "--quiet", "--verify", "--", f"refs/heads/{possible_branch}"])

            if result == 1:
                return possible_branch

        raise KBRuntimeError(f"\tUnable to find good branch name for {module} branch name {branch}")

    @staticmethod
    def slurp_git_config_output(args: list[str]) -> list[str]:
        """
        Split the output of "git config --null" correctly.

        All parameters are then passed to filter_program_output (so look there for help on usage).
        """
        # Don't call with $self->, all args are passed to filter_program_output

        # This gets rid of the trailing nulls for single-line output. (chomp uses
        # $/ instead of hardcoding newline
        output = Util.filter_program_output(None, *args)  # No filter
        output = [o.removesuffix("\0") for o in output]
        return output

    @staticmethod
    def has_remote(remote: str) -> bool:
        """
        Return true if the git module in the current directory has a remote of the name given by the first parameter.
        """
        has_remote = False

        try:
            def filter_fn(x):
                nonlocal has_remote
                if not has_remote:
                    has_remote = x and x.startswith(remote)

            Util.filter_program_output(filter_fn, "git", "remote")
        except Exception:
            pass
        return has_remote

    @staticmethod
    def verify_git_config(context_options: BuildContext) -> bool:
        """
        Add the "kde:" alias to the user's git config if it's not already set.

        Call this as a static class function, not as an object method
        (i.e. Updater_Git.verify_git_config, not foo.verify_git_config)

        Returns:
             False on failure of any sort, True otherwise.
        """
        protocol = context_options.get_option("git-push-protocol") or "git"

        push_url_prefix = ""
        other_push_url_prefix = ""

        if protocol == "git" or protocol == "https":
            push_url_prefix = "ssh://git@invent.kde.org/" if protocol == "git" else "https://invent.kde.org/"
            other_push_url_prefix = "https://invent.kde.org/" if protocol == "git" else "ssh://git@invent.kde.org/"
        else:
            logger_updater.error(f"\tb[y[*] Invalid b[git-push-protocol] {protocol}")
            logger_updater.error("\tb[y[*] Try setting this option to \"git\" if you're not using a proxy")
            raise KBRuntimeError(f"\tInvalid git-push-protocol: {protocol}")

        p = subprocess.run("git config --global --includes --get url.https://invent.kde.org/.insteadOf kde:", shell=True, capture_output=True, text=True)
        config_output = p.stdout.removesuffix("\n")
        err_num = p.returncode

        # 0 means no error, 1 means no such section exists -- which is OK
        if err_num >= 2:
            error = f"Code {err_num}"
            errors = {
                1: "Invalid section or key",
                2: "No section was provided to git-config",
                3: "Invalid config file (~/.gitconfig)",
                4: "Could not write to ~/.gitconfig",
                5: "Tried to set option that had no (or multiple) values",
                6: "Invalid regexp with git-config",
                128: "HOME environment variable is not set (?)",
            }

            if err_num in errors:
                error = errors[err_num]
            logger_updater.error(f"\tr[*] Unable to run b[git] command:\n\t{error}")
            return False

        # If we make it here, I'm just going to assume git works from here on out
        # on this simple task.
        if not re.search(r"^kde:\s*$", config_output):
            logger_updater.debug("\tAdding git download kde: alias (fetch: https://invent.kde.org/)")
            result = Util.safe_system("git config --global --add url.https://invent.kde.org/.insteadOf kde:".split(" "))
            if result != 0:
                return False

        config_output = subprocess.run(f"git config --global --includes --get url.{push_url_prefix}.pushInsteadOf kde:", shell=True, capture_output=True, text=True).stdout.removesuffix("\n")
        if not re.search(r"^kde:\s*$", config_output):
            logger_updater.debug(f"\tAdding git upload kde: alias (push: {push_url_prefix})")
            result = Util.safe_system(["git", "config", "--global", "--add", f"url.{push_url_prefix}.pushInsteadOf", "kde:"])
            if result != 0:
                return False

        # Remove old kde-builder installed aliases (kde: -> git://anongit.kde.org/)
        config_output = subprocess.run("git config --global --get url.git://anongit.kde.org/.insteadOf kde:", shell=True, capture_output=True, text=True).stdout.removesuffix("\n")
        if re.search(r"^kde:\s*$", config_output):
            logger_updater.debug("\tRemoving outdated kde: alias (fetch: git://anongit.kde.org/)")
            result = Util.safe_system("git config --global --unset-all url.git://anongit.kde.org/.insteadOf kde:".split(" "))
            if result != 0:
                return False

        config_output = subprocess.run("git config --global --get url.https://anongit.kde.org/.insteadOf kde:", shell=True, capture_output=True, text=True).stdout.removesuffix("\n")
        if re.search(r"^kde:\s*$", config_output):
            logger_updater.debug("\tRemoving outdated kde: alias (fetch: https://anongit.kde.org/)")
            result = Util.safe_system("git config --global --unset-all url.https://anongit.kde.org/.insteadOf kde:".split(" "))
            if result != 0:
                return False

        config_output = subprocess.run("git config --global --get url.git@git.kde.org:.pushInsteadOf kde:", shell=True, capture_output=True, text=True).stdout.removesuffix("\n")
        if re.search(r"^kde:\s*$", config_output):
            logger_updater.debug("\tRemoving outdated kde: alias (push: git@git.kde.org)")
            result = Util.safe_system("git config --global --unset-all url.git@git.kde.org:.pushInsteadOf kde:".split(" "))
            if result != 0:
                return False

        # remove outdated alias if git-push-protocol gets flipped
        config_output = subprocess.run(f"git config --global --get url.{other_push_url_prefix}.pushInsteadOf kde:", shell=True, capture_output=True, text=True).stdout.removesuffix("\n")
        if re.search(r"^kde:\s*$", config_output):
            logger_updater.debug(f"\tRemoving outdated kde: alias (push: {other_push_url_prefix})")
            result = Util.safe_system(["git", "config", "--global", "--unset-all", f"url.{other_push_url_prefix}.pushInsteadOf", "kde:"])
            if result != 0:
                return False
        return True
