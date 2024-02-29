# SPDX-FileCopyrightText: 2003 - 2023 Michael Pyne <mpyne@kde.org>
# SPDX-FileCopyrightText: 2004 - 2024 KDE Contributors (see git history) <community@kde.org>
# SPDX-FileCopyrightText: 2023 - 2024 Andrew Shark <ashark@linuxcomp.ru>
#
# SPDX-License-Identifier: GPL-2.0-only OR GPL-3.0-only OR LicenseRef-KDE-Accepted-GPL

# Helper used to handle a generic 'progress update' status for the module
# build, update, install, etc. processes.
#
# Currently, supports TTY output only, but it's not impossible to visualize
# extending this to a GUI or even web server as options.
from __future__ import annotations

import sys
from .Debug import Debug


class StatusView:
    def __init__(self):
        # defaultOpts

        self.cur_progress = -1
        self.progress_total = -1
        self.status = ""

        # Records number of modules built stats
        self.mod_total = -1
        self.mod_failed = 0
        self.mod_success = 0

    def setStatus(self, newStatus) -> None:
        """
        Sets the 'base' message to show as part of the update. E.g. "Compiling..."
        """
        self.status = Debug().colorize(newStatus)

    def setProgress(self, newProgress) -> None:
        """
        Sets the amount of progress made vs. the total progress possible.
        """
        oldProgress = self.cur_progress
        self.cur_progress = newProgress

        if oldProgress != newProgress:
            self.update()

    def setProgressTotal(self, newProgressTotal) -> None:
        """
        Sets the total amount of progress deemed possible.
        """
        self.progress_total = newProgressTotal

    def numberModulesTotal(self, newTotal: int = None) -> int:
        """
        Gets (or sets, if arg provided) number of modules to be built.
        """
        if newTotal:
            self.mod_total = newTotal
        return self.mod_total

    def numberModulesSucceeded(self, newTotal: int | None = None) -> int:
        """
        Gets (or sets, if arg provided) number of modules built successfully.
        """
        if newTotal:
            self.mod_success = newTotal
        return self.mod_success

    def numberModulesFailed(self, newTotal: int | None = None) -> int:
        """
        Gets (or sets, if arg provided) number of modules not built successfully.
        """
        if newTotal:
            self.mod_failed = newTotal
        return self.mod_failed

    def update(self) -> None:
        """
        Sends out the I/O needed to ensure the latest status is displayed.
        E.g. for TTY it clears the line and redisplays the current stats.
        """
        progress_total = self.progress_total
        msg = None

        mod_total, mod_success, mod_failed = self.mod_total, self.mod_success, self.mod_failed

        if mod_total >= 100:
            fmt_spec = "%03d"
        else:
            fmt_spec = "%02d"

        status_line = self.status

        if mod_total > 1:
            # Build up message in reverse order
            msg = f"{mod_total} modules"
            if mod_failed:
                msg = Debug().colorize(f"r[b[{mod_failed}] failed, ") + msg
            if mod_success:
                msg = Debug().colorize(f"g[b[{mod_success}] built, ") + msg

            status_line = self.status + f" ({msg})"

        if progress_total > 0:
            msg = "{:.1f}%{}".format(self.cur_progress * 100 / progress_total, status_line)

        elif self.cur_progress < 0:
            msg = status_line
        else:
            spinner = "-\\|/"
            msg = spinner[self.cur_progress % len(spinner)] + status_line

        StatusView._clearLineAndUpdate(msg)

    @staticmethod
    def releaseTTY(msg: str = "") -> None:
        """
        For TTY outputs, this clears the line (if we actually had dirtied it) so
        the rest of the program can resume output from where it'd been left off.
        """
        StatusView._clearLineAndUpdate(Debug().colorize(msg))

    @staticmethod
    def _clearLineAndUpdate(msg: str) -> None:
        """
        Give escape sequence to return to column 1 and clear the entire line
        Then print message and return to column 1 again in case somewhere else
        uses the tty.
        """
        print(f"\033[1G\033[K{msg}\033[1G", end="")
        sys.stdout.flush()
