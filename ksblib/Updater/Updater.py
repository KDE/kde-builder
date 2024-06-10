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
import textwrap
import time
from typing import Callable
from typing import TYPE_CHECKING

from ..BuildException import BuildException
from ..Debug import Debug
from ..Debug import kbLogger
from ..IPC.Null import IPC_Null
from ..Util.LoggedSubprocess import Util_LoggedSubprocess
from ..Util.Util import Util

if TYPE_CHECKING:
    from ..BuildContext import BuildContext
    from ..Module.Module import Module

logger_updater = kbLogger.getLogger("updater")


class Updater:
    """
    Class that is responsible for updating git-based source code modules. Can
    have some features overridden by subclassing (see Updater_KDEProject
    for an example).
    """

    DEFAULT_GIT_REMOTE = "origin"

    def __init__(self, module):
        self.module = module
        self.ipc = None

    def updateInternal(self, ipc=IPC_Null()) -> int:
        """
        scm-specific update procedure.
        May change the current directory as necessary.
        """
        self.ipc = ipc
        err = None
        numCommits = None

        try:
            numCommits = self.updateCheckout()
        except Exception as _err:
            err = _err

        self.ipc = None

        if err:
            raise err
        return numCommits

    @staticmethod
    # @override(check_signature=False)
    def name() -> str:
        return "git"

    def currentRevisionInternal(self) -> str:
        Util.assert_isa(self, Updater)
        return self.commit_id("HEAD")

    def commit_id(self, commit: str) -> str:
        """
        Returns the current sha1 of the given git "commit-ish".
        """
        Util.assert_isa(self, Updater)
        if commit is None:
            BuildException.croak_internal("Must specify git-commit to retrieve id for")
        module = self.module

        gitdir = module.fullpath("source") + "/.git"

        # Note that the --git-dir must come before the git command itself.
        an_id = Util.filter_program_output(None, *["git", "--git-dir", gitdir, "rev-parse", commit])
        if an_id:
            an_id = an_id[0].removesuffix("\n")
        else:
            an_id = ""  # if it was empty list, make it str

        return an_id

    def _verifyRefPresent(self, module: Module, repo: str) -> bool:
        ref, commitType = self._determinePreferredCheckoutSource(module)

        if Debug().pretending():
            return True

        if commitType == "none":
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

        BuildException.croak_runtime(f"git had error exit {result} when verifying {ref} present in repository at {repo}")

    def _clone(self, git_repo: str) -> int:
        """
        Perform a git clone to checkout the latest branch of a given git module

        First parameter is the repository (typically URL) to use.

        Returns:
             1, or raises exception if an error occurs.
        """
        Util.assert_isa(self, Updater)
        module = self.module
        srcdir = module.fullpath("source")
        args = ["--", git_repo, srcdir]

        ipc = self.ipc or BuildException.croak_internal("Missing IPC object")

        logger_updater.warning(f"Cloning g[{module}]")

        Util.p_chdir(module.getSourceDir())

        commitId, commitType = self._determinePreferredCheckoutSource(module)

        if commitType != "none":
            commitId = re.sub(r"^refs/tags/", "", commitId)  # git-clone -b doesn't like refs/tags/
            args.insert(0, commitId)  # Checkout branch right away
            args.insert(0, "-b")

        exitcode = Util.run_logged(module, "git-clone", module.getSourceDir(), ["git", "clone", "--recursive", *args])

        if not exitcode == 0:
            BuildException.croak_runtime("Failed to make initial clone of $module")

        ipc.notifyPersistentOptionChange(module.name, "git-cloned-repository", git_repo)

        Util.p_chdir(srcdir)

        # Setup user configuration
        if name := module.getOption("git-user"):
            username, email = re.match(r"^([^<]+) +<([^>]+)>$", name)
            if not username or not email:
                BuildException.croak_runtime(f"Invalid username or email for git-user option: {name}" +
                                             " (should be in format 'User Name <username@example.net>'")

            logger_updater.debug(f"\tAdding git identity {name} for new git module {module}")
            result = Util.safe_system(["git", "config", "--local", "user.name", username]) == 0

            result = Util.safe_system(["git", "config", "--local", "user.email", email]) == 0 or result

            if not result:
                logger_updater.warning(f"Unable to set user.name and user.email git config for y[b[{module}]!")
        return 1  # success

    def _verifySafeToCloneIntoSourceDir(self, module: Module, srcdir: str) -> None:
        """
        Checks that the required source dir is either not already present or is empty.
        Throws an exception if that's not true.
        """
        if os.path.exists(f"{srcdir}") and not os.listdir(srcdir):
            if module.getOption("#delete-my-patches"):
                logger_updater.warning("\tRemoving conflicting source directory " + "as allowed by --delete-my-patches")
                logger_updater.warning(f"\tRemoving b[{srcdir}]")
                Util.safe_rmtree(srcdir) or BuildException.croak_internal(f"Unable to delete {srcdir}!")
            else:
                logger_updater.error(textwrap.dedent("""\
                The source directory for b[$module] does not exist. kde-builder would download
                it, except there is already a file or directory present in the desired source
                directory:
                \ty[b[$srcdir]

                Please either remove the source directory yourself and re-run this script, or
                pass the b[--delete-my-patches] option to kde-builder and kde-builder will
                try to do so for you.

                DO NOT FORGET TO VERIFY THERE ARE NO UNCOMMITTED CHANGES OR OTHER VALUABLE
                FILES IN THE DIRECTORY.

                """))

                if os.path.exists(f"{srcdir}/.git"):
                    logger_updater.error(f"git status of {srcdir}:")
                    print(subprocess.check_output(["git", "status", srcdir]))
                BuildException.croak_runtime("Conflicting source-dir present")

    def updateCheckout(self) -> int:
        """
        Either performs the initial checkout or updates the current git checkout
        for git-using modules, as appropriate.

        Returns the number of *commits* affected, or
        throws exception on an update error.
        """
        Util.assert_isa(self, Updater)
        module = self.module
        srcdir = module.fullpath("source")

        # While .git is usually a directory, it can also be a file in case of a
        # worktree checkout (https://git-scm.com/docs/gitrepository-layout)
        if os.path.exists(f"{srcdir}/.git"):
            # Note that this function will throw an exception on failure.
            return self.updateExistingClone()
        else:
            self._verifySafeToCloneIntoSourceDir(module, srcdir)

            git_repo = module.getOption("repository")
            if not git_repo:
                BuildException.croak_internal(f"Unable to checkout {module}, you must specify a repository to use.")

            if not self._verifyRefPresent(module, git_repo):
                if self._moduleIsNeeded():
                    BuildException.croak_runtime(f"{module} build was requested, but it has no source code at the requested git branch")
                else:
                    BuildException.croak_runtime("The required git branch does not exist at the source repository")

            self._clone(git_repo)
            if Debug().pretending():
                return 1
            else:
                return Updater.count_command_output("git", "--git-dir", f"{srcdir}/.git", "ls-files")

    @staticmethod
    def _moduleIsNeeded() -> bool:
        """
        Intended to be reimplemented
        """
        return True

    @staticmethod
    def isPushUrlManaged() -> bool:
        """
        Determine whether _setupRemote should manage the configuration of the git push URL for the repo.

        Returns:
             Boolean indicating whether _setupRemote should assume control over the push URL.
        """
        return False

    def _setupRemote(self, remote: str) -> int:
        """
        Ensures the given remote is pre-configured for the module's git repository.
        The remote is either set up from scratch or its URLs are updated.

        Parameters:
            remote: name (alias) of the remote to configure

        Returns 1 or raises exception on an error.
        """
        module = self.module
        repo = module.getOption("repository")
        hasOldRemote = self.hasRemote(remote)

        if hasOldRemote:
            logger_updater.debug(f"\tUpdating the URL for git remote {remote} of {module} ({repo})")
            exitcode = Util.run_logged(module, "git-fix-remote", None, ["git", "remote", "set-url", remote, repo])
            if not exitcode == 0:
                BuildException.croak_runtime(f"Unable to update the URL for git remote {remote} of {module} ({repo})")
        else:
            logger_updater.debug(f"\tAdding new git remote {remote} of {module} ({repo})")
            exitcode = Util.run_logged(module, "git-add-remote", None, ["git", "remote", "add", remote, repo])
            if not exitcode == 0:
                BuildException.croak_runtime(f"Unable to add new git remote {remote} of {module} ({repo})")

        # If we make it here, no exceptions were thrown
        if not self.isPushUrlManaged():
            return 1

        # pushInsteadOf does not work nicely with git remote set-url --push
        # The result would be that the pushInsteadOf kde: prefix gets ignored.
        #
        # The next best thing is to remove any preconfigured pushurl and
        # restore the kde: prefix mapping that way.  This is effectively the
        # same as updating the push URL directly because of the remote set-url
        # executed previously by this function for the fetch URL.

        existingPushUrl = subprocess.run(f"git config --get remote.{remote}.pushurl", shell=True, capture_output=True, text=True).stdout.strip()

        if not existingPushUrl:
            return 1

        logger_updater.info(f"\tRemoving preconfigured push URL for git remote {remote} of {module}: {existingPushUrl}")

        exitcode = Util.run_logged(module, "git-fix-remote", None, ["git", "config", "--unset", f"remote.{remote}.pushurl"])
        if not exitcode == 0:
            BuildException.croak_runtime(f"Unable to remove preconfigured push URL for {module}!")
        return 1  # overall success

    def _setupBestRemote(self) -> str:
        """
        Selects a git remote for the user's selected repository (preferring a
        defined remote if available, using "origin" otherwise).

        Assumes the current directory is already set to the source directory.

        Returns the name of the remote (which will be setup by kde-builder) to use for updates, or raises exception on an error.

        See also the "repository" module option.
        """
        Util.assert_isa(self, Updater)
        module = self.module
        cur_repo = module.getOption("repository")
        ipc = self.ipc or BuildException.croak_internal("Missing IPC object")

        # Search for an existing remote name first. If none, add our alias.
        remoteNames = self.bestRemoteName()
        chosenRemote = remoteNames[0] if remoteNames else Updater.DEFAULT_GIT_REMOTE

        self._setupRemote(chosenRemote)

        # Make a notice if the repository we're using has moved.
        old_repo = module.getPersistentOption("git-cloned-repository")
        if old_repo and (cur_repo != old_repo):
            logger_updater.warning(f" y[b[*]\ty[{module}]'s selected repository has changed")
            logger_updater.warning(f" y[b[*]\tfrom y[{old_repo}]")
            logger_updater.warning(f" y[b[*]\tto   b[{cur_repo}]")
            logger_updater.warning(" y[b[*]\tThe git remote named b[" + Updater.DEFAULT_GIT_REMOTE + "] has been updated")

            # Update what we think is the current repository on-disk.
            ipc.notifyPersistentOptionChange(module.name, "git-cloned-repository", cur_repo)
        return chosenRemote

    def _warnIfStashedFromWrongBranch(self, remoteName: str, branch: str, branchName: str) -> bool:
        """
        Returns true if there is a git stash active from the wrong branch, so we
        don't mistakenly try to apply the stash after we switch branch.
        """
        module = self.module

        # Check if this branchName we want was already the branch we were on. If
        # not, and if we stashed local changes, then we might dump a bunch of
        # conflicts in the repo if we un-stash those changes after a branch switch.
        # See issue #67.
        existingBranch = next(iter(Util.filter_program_output(None, "git", "branch", "--show-current")), None)
        if existingBranch is not None:
            existingBranch = existingBranch.removesuffix("\n")

        # The result is empty if in 'detached HEAD' state where we should also
        # clearly not switch branches if there are local changes.
        if module.getOption("#git-was-stashed") and (not existingBranch or (existingBranch != branchName)):

            # Make error message make more sense
            if not existingBranch:
                existingBranch = "Detached HEAD"
            if not branchName:
                branchName = f"New branch to point to {remoteName}/{branch}"

            logger_updater.info(textwrap.dedent(f"""\
                y[b[*] The module y[b[{module}] had local changes from a different branch than expected:
                y[b[*]   Expected branch: b[{branchName}]
                y[b[*]   Actual branch:   b[{existingBranch}]
                y[b[*]
                y[b[*] To avoid conflict with your local changes, b[{module}] will not be updated, and the
                y[b[*] branch will remain unchanged, so it may be out of date from upstream.
                """))

            self._notifyPostBuildMessage(f" y[b[*] b[{module}] was not updated as it had local changes against an unexpected branch.")
            return True
        return False

    def _updateToRemoteHead(self, remoteName: str, branch: str) -> int:
        """
        Completes the steps needed to update a git checkout to be checked-out to
        a given remote-tracking branch. Any existing local branch with the given
        branch set as upstream will be used if one exists, otherwise one will be
        created. The given branch will be rebased into the local branch.

        No checkout is done, this should be performed first.
        Assumes we're already in the needed source dir.
        Assumes we're in a clean working directory (use git-stash to achieve if necessary).

        Parameters:
            remoteName: The remote to use.
            branch: The branch to update to.

        Returns:
             boolean success flag.
        Exception may be thrown if unable to create a local branch.
        """
        module = self.module

        # "branch" option requests a given remote head in the user's selected
        # repository. The local branch with "branch" as upstream might have a
        # different name. If there's no local branch this method creates one.
        branchName = self.getRemoteBranchName(remoteName, branch)

        if self._warnIfStashedFromWrongBranch(remoteName, branch, branchName):
            return 0

        croak_reason = None
        result = None
        cmd = Util_LoggedSubprocess().module(module).chdir_to(module.fullpath("source"))

        if not branchName:
            newName = self.makeBranchname(remoteName, branch)

            def announcer_sub(_):
                # pl2py: despite in perl this sub had no arguments, it is called with one argument, so we add unused argument here
                logger_updater.debug(f"\tUpdating g[{module}] with new remote-tracking branch y[{newName}]")

            cmd.log_to("git-checkout-branch") \
                .set_command(["git", "checkout", "-b", newName, f"{remoteName}/{branch}"]) \
                .announcer(announcer_sub)

            croak_reason = f"Unable to perform a git checkout of {remoteName}/{branch} to a local branch of {newName}"
            result = cmd.start()
        else:
            def announcer_sub(_):
                # pl2py: despite in perl this sub had no arguments, it is called with one argument, so we add unused argument here
                logger_updater.debug(f"\tUpdating g[{module}] using existing branch g[{branchName}]")

            cmd.log_to("git-checkout-update") \
                .set_command(["git", "checkout", branchName]) \
                .announcer(announcer_sub)

            croak_reason = f"Unable to perform a git checkout to existing branch {branchName}"

            result = cmd.start()

            if not result == 0:
                pass
            else:
                croak_reason = f"{module}: Unable to reset to remote development branch {branch}"

                # Given that we're starting with a "clean" checkout, it's now simply a fast-forward
                # to the remote HEAD (previously we pulled, incurring additional network I/O).
                result = Util.run_logged(module, "git-rebase", None, ["git", "reset", "--hard", f"{remoteName}/{branch}"])

        if not result == 0:
            BuildException.croak_runtime(croak_reason)
        return 1  # success

    def _updateToDetachedHead(self, commit: str) -> int:
        """
        Completes the steps needed to update a git checkout to be checked-out to
        a given commit. The local checkout is left in a detached HEAD state,
        even if there is a local branch which happens to be pointed to the
        desired commit. Based the given commit is used directly, no rebase/merge
        is performed.

        No checkout is done, this should be performed first.
        Assumes we're already in the needed source dir.
        Assumes we're in a clean working directory (use git-stash to achieve if necessary).

        Parameters:
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

    def updateExistingClone(self) -> int:
        """
        Updates an already existing git checkout by running git pull.
        Throws an exception on error.
        Returns the number of affected *commits*.
        """
        Util.assert_isa(self, Updater)
        module = self.module
        cur_repo = module.getOption("repository")
        result = None

        Util.p_chdir((module.fullpath("source")))

        # Try to save the user if they are doing a merge or rebase
        if os.path.exists(".git/MERGE_HEAD") or os.path.exists(".git/rebase-merge") or os.path.exists(".git/rebase-apply"):
            BuildException.croak_runtime(f"Aborting git update for {module}, you appear to have a rebase or merge in progress!")

        remoteName = self._setupBestRemote()
        logger_updater.info(f"Fetching remote changes to g[{module}]")
        exitcode = Util.run_logged(module, "git-fetch", None, ["git", "fetch", "--tags", remoteName])

        # Download updated objects. This also updates remote heads so do this
        # before we start comparing branches and such.

        if not exitcode == 0:
            BuildException.croak_runtime(f"Unable to perform git fetch for {remoteName} ({cur_repo})")

        # Now we need to figure out if we should update a branch, or simply
        # checkout a specific tag/SHA1/etc.
        commitId, commitType = self._determinePreferredCheckoutSource(module)
        if commitType == "none":
            commitType = "branch"
            commitId = self._detectDefaultRemoteHead(remoteName)

        logger_updater.warning(f"Merging g[{module}] changes from {commitType} b[{commitId}]")
        start_commit = self.commit_id("HEAD")

        self.stash_and_update(commitType, remoteName, commitId)
        ret = Updater.count_command_output("git", "rev-list", f"{start_commit}..HEAD")
        return ret

    @staticmethod
    def _detectDefaultRemoteHead(remoteName: str) -> str:
        """
        Tries to determine the best remote branch name to use as a default if the
        user hasn't selected one, by resolving the remote symbolic ref "HEAD" from
        its entry in the .git dir. This can also be found by introspecting the
        output of "git remote show $REMOTE_NAME" or "git branch -r" but these are
        incredibly slow.
        """
        if not os.path.isdir(".git"):
            caller_name = inspect.currentframe().f_back.f_code.co_name
            BuildException.croak_internal("Run " + caller_name + " from git repo!")

        with open(f".git/refs/remotes/{remoteName}/HEAD", "r") as file:
            data = file.read()

        if not data:
            data = ""

        match = re.search(r"^ref: *refs/remotes/[^/]+/([^/]+)$", data)
        head = match.group(1) if match else None
        if not head:
            BuildException.croak_runtime(f"Can't find HEAD for remote {remoteName}")

        head = head.removesuffix("\n")
        return head

    def _determinePreferredCheckoutSource(self, module: Module | None = None) -> tuple:
        """
        Goes through all the various combination of git checkout selection options in
        various orders of priority.

        Returns a *list* containing: (the resultant symbolic ref/or SHA1,"branch" or
        'tag' (to determine if something like git-pull would be suitable or whether
        you have a detached HEAD)). Since the sym-ref is returned first that should
        be what you get in a scalar context, if that's all you want.
        """

        if not module:
            module = self.module

        priorityOrderedSources = [
            #   option-name    type   getOption-inheritance-flag
            ["commit", "tag", "module"],
            ["revision", "tag", "module"],
            ["tag", "tag", "module"],
            ["branch", "branch", "module"],
            ["branch-group", "branch", "module"],
            # commit/rev/tag don't make sense for git as globals
            ["branch", "branch", "allow-inherit"],
            ["branch-group", "branch", "allow-inherit"],
        ]

        # For modules that are not actually a 'proj' module we skip branch-group
        # entirely to allow for global/module branch selection
        # options to be selected... kind of complicated, but more DWIMy
        from .KDEProject import Updater_KDEProject
        if not isinstance(module.scm(), Updater_KDEProject):
            priorityOrderedSources = [priorityOrderedSource for priorityOrderedSource in priorityOrderedSources if priorityOrderedSource[0] != "branch-group"]

        checkoutSource = None
        # easiest way to be clear that bool context is intended

        sourceTypeRef = next((x for x in priorityOrderedSources if (checkoutSource := module.getOption(x[0], x[2]))), None)  # Note that we check for truth of getOption, not if it is None, because we want to treat empty string also as false

        # The user has no clear desire here (either set for the module or globally.
        # Note that the default config doesn't generate a global 'branch' setting).
        # In this case it's unclear which convention source modules will use between
        # 'master', 'main', or something entirely different.  So just don't guess...
        if not sourceTypeRef:
            logger_updater.debug(f"No branch specified for {module}, will use whatever git gives us")
            return "none", "none"

        # Likewise branch-group requires special handling. checkoutSource is
        # currently the branch-group to be resolved.
        if sourceTypeRef[0] == "branch-group":
            Util.assert_isa(self, Updater_KDEProject)
            checkoutSource = self._resolveBranchGroup(checkoutSource)

            if not checkoutSource:
                branchGroup = module.getOption("branch-group")
                logger_updater.debug(f"No specific branch set for {module} and {branchGroup}, using master!")
                checkoutSource = "master"

        if sourceTypeRef[0] == "tag" and not checkoutSource.startswith("^refs/tags/"):
            checkoutSource = f"refs/tags/{checkoutSource}"

        return checkoutSource, sourceTypeRef[1]

    @staticmethod
    def _hasSubmodules() -> bool:
        """
        Tries to check whether the git module is using submodules or not. Currently,
        we just check the .git/config file (using git-config) to determine whether
        there are any 'active' submodules.

        MUST BE RUN FROM THE SOURCE DIR
        """
        # The git-config line shows all option names of the form submodule.foo.active,
        # filtering down to options for which the option is set to 'true'
        configLines = Util.filter_program_output(None, "git", "config", "--local", "--get-regexp", r"^submodule\..*\.active", "true")
        return len(configLines) > 0

    @staticmethod
    def _splitUri(uri) -> tuple:
        match = re.match(r"(?:([^:/?#]+):)?(?://([^/?#]*))?([^?#]*)(?:\?([^#]*))?(?:#(.*))?", uri)
        scheme, authority, path, query, fragment = match.groups()
        return scheme, authority, path, query, fragment

    def countStash(self, description=None) -> int:
        Util.assert_isa(self, Updater)
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

    def _notifyPostBuildMessage(self, *args: str) -> None:
        """
        Wrapper to send a post-build (warning) message via the IPC object.
        This just takes care of the boilerplate to forward its arguments as message.
        """
        Util.assert_isa(self, Updater)
        module = self.module
        self.ipc.notifyNewPostBuildMessage(module.name, *args)

    def stash_and_update(self, commit_type: str, remote_name: str, commit_id: str) -> int:
        """
        Stashes existing changes if necessary, and then runs appropriate update function
        (_updateToRemoteHead or _updateToDetachedHead) in order to advance the given module to the desired head.
        Finally, if changes were stashed, they are applied and the stash stack is
        popped.

        It is assumed that the required remote has been set up already, that we
        are on the right branch, and that we are already in the correct
        directory.

        Returns:
             1 or raises exception on error.
        """
        module = self.module
        date = time.strftime("%F-%R", time.gmtime())  # ISO Date, hh:mm time
        stashName = f"kde-builder auto-stash at {date}"

        # first, log the git status prior to kde-builder taking over the reins in the repo
        result = Util.run_logged(module, "git-status-before-update", None, ["git", "status"])

        oldStashCount = self.countStash()

        # always stash:
        # - also stash untracked files because what if upstream started to track them
        # - we do not stash .gitignore'd files because they may be needed for builds?
        #   on the other hand that leaves a slight risk if upstream altered those
        #   (i.e. no longer truly .gitignore'd)
        logger_updater.debug("\tStashing local changes if any...")

        if Debug().pretending():  # probably best not to do anything if pretending
            result = 0
        else:
            result = Util.run_logged(module, "git-stash-push", None, ["git", "stash", "push", "-u", "--quiet", "--message", stashName])

        if result == 0:
            pass
        else:
            # Might happen if the repo is already in merge conflict state.
            # We could mark everything as resolved using git add . before stashing,
            # but that might not always be appreciated by people having to figure
            # out what the original merge conflicts were afterwards.
            self._notifyPostBuildMessage(f"b[{module}] may have local changes that we couldn't handle, so the module was left alone.")

            result = Util.run_logged(module, "git-status-after-error", None, ["git", "status"])
            BuildException.croak_runtime(f"Unable to stash local changes (if any) for {module}, aborting update.")

        # next: check if the stash was truly necessary.
        # compare counts (not just testing if there is *any* stash) because there
        # might have been a genuine user's stash already prior to kde-builder
        # taking over the reins in the repo.
        newStashCount = self.countStash()

        # mark that we applied a stash so that $updateSub (_updateToRemoteHead or
        # _updateToDetachedHead) can know not to do dumb things
        if newStashCount != oldStashCount:
            module.setOption({"#git-was-stashed": True})

        # finally, update to remote head
        if commit_type == "branch":
            result = self._updateToRemoteHead(remote_name, commit_id)
        else:
            result = self._updateToDetachedHead(commit_id)

        if result:
            result = 1
        else:
            result = Util.run_logged(module, "git-status-after-error", None, ["git", "status"])
            BuildException.croak_runtime(f"Unable to update source code for {module}")

        # we ignore git-status exit code deliberately, it's a debugging aid

        if newStashCount == oldStashCount:
            result = 1  # success
        else:
            # If the stash had been needed then try to re-apply it before we build, so
            # that KDE developers working on changes do not have to manually re-apply.
            exitcode = Util.run_logged(module, "git-stash-pop", None, ["git", "stash", "pop"])
            if exitcode != 0:
                message = f"r[b[*] Unable to restore local changes for b[{module}]! " + \
                          f"You should manually inspect the new stash: b[{stashName}]"
                logger_updater.warning(f"\t{message}")
                self._notifyPostBuildMessage(message)
            else:
                logger_updater.info(f"\tb[*] You had local changes to b[{module}], which have been re-applied.")

            result = 1  # success

        return result

    def getRemoteBranchName(self, remoteName: str, branchName: str) -> str:
        """
        This function finds an existing remote-tracking branch name for the
        given repository's named remote. For instance if the user was using the
        local remote-tracking branch called "qt-stable" to track kde-qt's master
        branch, this function would return the branchname "qt-stable" when
        passed kde-qt and "master".

        The current directory must be the source directory of the git module.

        Parameters:
            remoteName: The git remote to use (normally origin).
            branchName: The remote head name to find a local branch for.

        Returns:
            Empty string if no match is found, or the name of the local
            remote-tracking branch if one exists.
        """
        Util.assert_isa(self, Updater)

        # We'll parse git config output to search for branches that have a
        # remote of $remoteName and a 'merge' of refs/heads/$branchName.

        # TODO: Replace with git for-each-ref refs/heads and the %(upstream)
        # format.
        branches = self.slurp_git_config_output(["git", "config", "--null", "--get-regexp", r"branch\..*\.remote", remoteName])

        for gitBranch in branches:
            # The key/value is \n separated, we just want the key.
            keyName = gitBranch.split("\n")[0]
            thisBranch = re.match(r"^branch\.(.*)\.remote$", keyName).group(1)

            # We have the local branch name, see if it points to the remote
            # branch we want.
            configOutput = self.slurp_git_config_output(["git", "config", "--null", f"branch.{thisBranch}.merge"])

            if configOutput and configOutput[0] == f"refs/heads/{branchName}":
                # We have a winner
                return thisBranch
        return ""

    def _isPlausibleExistingRemote(self, name: str, url: str, configuredUrl: str) -> bool:
        """
        Filter for bestRemoteName to determine if a given remote name and url looks
        like a plausible prior existing remote for a given configured repository URL.

        Note that the actual repository fetch URL is not necessarily the same as the
        configured (expected) fetch URL: an upstream might have moved, or kde-builder
        configuration might have been updated to the same effect.

        Parameters:
            name: name of the remote found
            url: the configured (fetch) URL
            configuredUrl: the configured URL for the module (the expected fetch URL).

        Returns:
             Whether the remote will be considered for bestRemoteName
        """
        Util.assert_isa(self, Updater)
        # name - not used, subclasses might want to filter on remote name
        return url == configuredUrl

    def bestRemoteName(self) -> list:
        """
        99% of the time the "origin" remote will be what we want anyway, and
        0.5% of the rest the user will have manually added a remote, which we
        should try to utilize when doing checkouts for instance. To aid in this,
        this function returns a list of all remote aliased matching the
        supplied repository (besides the internal alias that is).

        Assumes that we are already in the proper source directory.

        Returns:
             A list of matching remote names (list in case the user hates us
            and has aliased more than one remote to the same repo). Obviously the list
            will be empty if no remote names were found.
        """
        Util.assert_isa(self, Updater)
        module = self.module
        configuredUrl = module.getOption("repository")
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
            remoteName, url = output.split("\n")

            remoteName = re.sub(r"^remote\.", "", remoteName)
            remoteName = re.sub(r"\.url$", "", remoteName)  # remove the cruft

            # Skip other remotes
            if not self._isPlausibleExistingRemote(remoteName, url, configuredUrl):
                continue

            # Try to avoid "weird" remote names.
            if not re.match(r"^[\w-]*$", remoteName):
                continue

            # A winner is this one.
            results.append(remoteName)
        return results

    def makeBranchname(self, remoteName: str, branch: str) -> str:
        """
        Generates a potential new branch name for the case where we have to set up
        a new remote-tracking branch for a repository/branch. There are several
        criteria that go into this:
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

        Parameters:
            remoteName: The name of a git remote to use.
            branch: The name of the remote head we need to make a branch name of.
        Returns:
             A useful branch name that doesn't already exist, or "" if no
            name can be generated.
        """
        Util.assert_isa(self, Updater)
        if not remoteName:
            remoteName = "origin"
        module = self.module
        chosenName = None

        # Use "$branch" directly if not already used, otherwise try to prefix
        # with the remote name.
        for possibleBranch in [branch, f"{remoteName}-{branch}", f"ksdc-{remoteName}-{branch}"]:
            result = subprocess.call(["git", "show-ref", "--quiet", "--verify", "--", f"refs/heads/{possibleBranch}"])

            if result == 1:
                return possibleBranch

        BuildException.croak_runtime(f"Unable to find good branch name for {module} branch name {branch}")

    @staticmethod
    def count_command_output(*args: str) -> int:
        """
        Returns the number of lines in the output of the given command. The command
        and all required arguments should be passed as a normal list, and the current
        directory should already be set as appropriate.

        Return value is the number of lines of output.
        Exceptions are raised if the command could not be run.
        """
        # Don't call with $self->, all args are passed to filter_program_output

        count = 0

        def func(x):
            nonlocal count
            if x:
                count += 1

        Util.filter_program_output(func, *args)
        return count

    @staticmethod
    def slurp_git_config_output(args: list) -> list:
        """
        A simple wrapper that is used to split the output of "git config --null"
        correctly. All parameters are then passed to filter_program_output (so look
        there for help on usage).
        """
        # Don't call with $self->, all args are passed to filter_program_output

        # This gets rid of the trailing nulls for single-line output. (chomp uses
        # $/ instead of hardcoding newline
        output = Util.filter_program_output(None, *args)  # No filter
        output = [o.removesuffix("\0") for o in output]
        return output

    @staticmethod
    def hasRemote(remote: str) -> bool:
        """
        Returns true if the git module in the current directory has a remote of the
        name given by the first parameter.
        """
        hasRemote = False

        try:
            def filter_fn(x):
                nonlocal hasRemote
                if not hasRemote:
                    hasRemote = x and x.startswith(remote)

            Util.filter_program_output(filter_fn, "git", "remote")
        except Exception:
            pass
        return hasRemote

    @staticmethod
    def verifyGitConfig(contextOptions: BuildContext) -> bool:
        """
        Function to add the "kde:" alias to the user's git config if it's not
        already set.

        Call this as a static class function, not as an object method
        (i.e. Updater_Git.verifyGitConfig, not foo.verifyGitConfig)

        Returns:
             False on failure of any sort, True otherwise.
        """
        protocol = contextOptions.getOption("git-push-protocol") or "git"

        pushUrlPrefix = ""
        otherPushUrlPrefix = ""

        if protocol == "git" or protocol == "https":
            pushUrlPrefix = "ssh://git@invent.kde.org/" if protocol == "git" else "https://invent.kde.org/"
            otherPushUrlPrefix = "https://invent.kde.org/" if protocol == "git" else "ssh://git@invent.kde.org/"
        else:
            logger_updater.error(f" b[y[*] Invalid b[git-push-protocol] {protocol}")
            logger_updater.error(" b[y[*] Try setting this option to 'git' if you're not using a proxy")
            BuildException.croak_runtime(f"Invalid git-push-protocol: {protocol}")

        p = subprocess.run("git config --global --includes --get url.https://invent.kde.org/.insteadOf kde:", shell=True, capture_output=True, text=True)
        configOutput = p.stdout.removesuffix("\n")
        errNum = p.returncode

        # 0 means no error, 1 means no such section exists -- which is OK
        if errNum >= 2:
            error = f"Code {errNum}"
            errors = {
                1: "Invalid section or key",
                2: "No section was provided to git-config",
                3: "Invalid config file (~/.gitconfig)",
                4: "Could not write to ~/.gitconfig",
                5: "Tried to set option that had no (or multiple) values",
                6: "Invalid regexp with git-config",
                128: "HOME environment variable is not set (?)",
            }

            if errNum in errors:
                error = errors[errNum]
            logger_updater.error(f" r[*] Unable to run b[git] command:\n\t{error}")
            return False

        # If we make it here, I'm just going to assume git works from here on out
        # on this simple task.
        if not re.search(r"^kde:\s*$", configOutput):
            logger_updater.debug("\tAdding git download kde: alias (fetch: https://invent.kde.org/)")
            result = Util.safe_system("git config --global --add url.https://invent.kde.org/.insteadOf kde:".split(" "))
            if result != 0:
                return False

        configOutput = subprocess.run(f"git config --global --includes --get url.{pushUrlPrefix}.pushInsteadOf kde:", shell=True, capture_output=True, text=True).stdout.removesuffix("\n")
        if not re.search(r"^kde:\s*$", configOutput):
            logger_updater.debug(f"\tAdding git upload kde: alias (push: {pushUrlPrefix})")
            result = Util.safe_system(["git", "config", "--global", "--add", f"url.{pushUrlPrefix}.pushInsteadOf", "kde:"])
            if result != 0:
                return False

        # Remove old kde-builder installed aliases (kde: -> git://anongit.kde.org/)
        configOutput = subprocess.run("git config --global --get url.git://anongit.kde.org/.insteadOf kde:", shell=True, capture_output=True, text=True).stdout.removesuffix("\n")
        if re.search(r"^kde:\s*$", configOutput):
            logger_updater.debug("\tRemoving outdated kde: alias (fetch: git://anongit.kde.org/)")
            result = Util.safe_system("git config --global --unset-all url.git://anongit.kde.org/.insteadOf kde:".split(" "))
            if result != 0:
                return False

        configOutput = subprocess.run("git config --global --get url.https://anongit.kde.org/.insteadOf kde:", shell=True, capture_output=True, text=True).stdout.removesuffix("\n")
        if re.search(r"^kde:\s*$", configOutput):
            logger_updater.debug("\tRemoving outdated kde: alias (fetch: https://anongit.kde.org/)")
            result = Util.safe_system("git config --global --unset-all url.https://anongit.kde.org/.insteadOf kde:".split(" "))
            if result != 0:
                return False

        configOutput = subprocess.run("git config --global --get url.git@git.kde.org:.pushInsteadOf kde:", shell=True, capture_output=True, text=True).stdout.removesuffix("\n")
        if re.search(r"^kde:\s*$", configOutput):
            logger_updater.debug("\tRemoving outdated kde: alias (push: git@git.kde.org)")
            result = Util.safe_system("git config --global --unset-all url.git@git.kde.org:.pushInsteadOf kde:".split(" "))
            if result != 0:
                return False

        # remove outdated alias if git-push-protocol gets flipped
        configOutput = subprocess.run(f"git config --global --get url.{otherPushUrlPrefix}.pushInsteadOf kde:", shell=True, capture_output=True, text=True).stdout.removesuffix("\n")
        if re.search(r"^kde:\s*$", configOutput):
            logger_updater.debug(f"\tRemoving outdated kde: alias (push: {otherPushUrlPrefix})")
            result = Util.safe_system(["git", "config", "--global", "--unset-all", f"url.{otherPushUrlPrefix}.pushInsteadOf", "kde:"])
            if result != 0:
                return False
        return True
