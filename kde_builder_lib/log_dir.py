# SPDX-FileCopyrightText: 2025 Andrew Shark <ashark@linuxcomp.ru>
#
# SPDX-License-Identifier: GPL-2.0-or-later

import os
import re

from .build_context import BuildContext
from .debug import Debug
from .debug import KBLogger
from .kb_exception import KBRuntimeError
from .util.util import Util

logger_app = KBLogger.getLogger("application")


class LogDir:
    """
    Responsible for created log directories.
    """

    @staticmethod
    def delete_unreferenced_log_directories(ctx: BuildContext) -> None:
        """
        Remove log directories from previous kde-builder runs.

        All log directories that are not referenced by log_dir/latest somehow are made to go away.
        """
        Util.assert_isa(ctx, BuildContext)
        logdir = ctx.get_absolute_path("log-dir")

        if not os.path.exists(f"{logdir}/latest"):  # Could happen for error on first run...
            return

        found_dirs = [f for f in os.listdir(logdir) if re.search(r"(\d{4}-\d{2}-\d{2}[-_]\d+)", f)]

        keep_dirs = []
        for tracked_log_dir in [f"{logdir}/latest", f"{logdir}/latest-by-phase"]:
            if not os.path.isdir(tracked_log_dir):
                continue
            keep_dirs = LogDir._symlinked_log_dirs(tracked_log_dir)

        length = len(found_dirs) - len(keep_dirs)
        logger_app.debug(f"Removing g[b[{length}] out of g[b[{len(found_dirs) - 1}] old log directories...")

        for dir_id in found_dirs:
            if dir_id not in keep_dirs:
                Util.safe_rmtree(logdir + "/" + dir_id)

    @staticmethod
    def cleanup_latest_log_dir(ctx) -> None:
        """
        Delete all symlinks to specific (YYYY-MM-DD_XX) log directories in latest log directory.

        You may be interested why we do not just make the "latest" as a symlink to YYYY-MM-DD_XX dir
        or why we just do not remove the "latest" dir entirely to clean it up.
        One reason is because user may override `log-dir` for individual project (so there would be several log dirs
        locations, but we must present all logs in that single "latest" dir).
        Another reason is because we want to support a situation when user has an "IDE project" in this "latest" dir.
        For example when they want to conveniently filter for specific errors in all log files from last run.
        In other words, we allow user to store directories like ".idea" or ".vscode" in "latest", and
        such files/folders will not be removed.
        """
        if Debug().pretending():
            return

        Util.assert_isa(ctx, BuildContext)
        logdir = ctx.get_absolute_path("log-dir")
        logdir_latest = f"{logdir}/latest"

        if not os.path.exists(logdir_latest):
            return

        dir_els = os.listdir(logdir_latest)
        for el in dir_els:
            if os.path.islink(logdir_latest + "/" + el):
                readlink = os.readlink(logdir_latest + "/" + el)
                # check if it is a symlink to some actual YYYY-MM-DD_XX log dir, not a random one user's symlink
                if re.search(logdir + "/" + r"(\d{4}-\d{2}-\d{2}[-_]\d+)" + "/" + el, readlink):
                    os.unlink(logdir_latest + "/" + el)

        if os.path.islink(logdir_latest + "/" + "status-list.log"):
            os.unlink(logdir_latest + "/" + "status-list.log")

        if os.path.islink(logdir_latest + "/" + "screen.log"):
            os.unlink(logdir_latest + "/" + "screen.log")

    @staticmethod
    def _symlinked_log_dirs(logdir: str) -> list[str]:
        """
        Return a list of module directories IDs that are still referenced by symlinks.

        Can be used to get the list of directories that must be kept when removing old log directories.
        References are checked from the "<log-dir>/latest/<module_name>" symlink and from the "<log-dir>/latest-by-phase/<module_name>/*.log" symlinks.
        The directories IDs are based on YYYY-MM-DD_XX format.

        This function may call itself recursively if needed.

        Args:
            logdir: The log directory under which to search for symlinks, including the "/latest" or "/latest-by-phase" part of the path.
        """
        links = []

        try:
            with os.scandir(logdir) as entries:
                for entry in entries:
                    if entry.is_symlink():  # symlinks to files/folders
                        link = os.readlink(entry.path)
                        links.append(link)
                    elif entry.name != "." and entry.name != ".." and not entry.is_file():  # regular (not symlinks) files/folders
                        # Skip regular files (note that it is not a symlink to file, because of previous is_symlink check), because there may be files in logdir, for example ".directory" file.
                        links.extend(LogDir._symlinked_log_dirs(os.path.join(logdir, entry.name)))  # for regular directories, get links from it
        except OSError as e:
            raise KBRuntimeError(f"Can't opendir {logdir}: {e}")

        # Extract numeric directories IDs from directories/files paths in links list.
        dirs = [re.search(r"(\d{4}-\d\d-\d\d[-_]\d+)", d).group(1) for d in links if re.search(r"(\d{4}-\d\d-\d\d[-_]\d+)", d)]  # if we use pretending, then symlink will point to /dev/null, so check if found matching group first
        uniq_dirs = list(set(dirs))
        return uniq_dirs
