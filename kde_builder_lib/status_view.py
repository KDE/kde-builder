# SPDX-FileCopyrightText: 2015 Michael Pyne <mpyne@kde.org>
# SPDX-FileCopyrightText: 2023 - 2024 Andrew Shark <ashark@linuxcomp.ru>
#
# SPDX-License-Identifier: GPL-2.0-or-later

from __future__ import annotations

import sys

from .debug import Debug


class StatusView:
    """
    Helper used to handle a generic "progress update" status for the module build, update, install, etc. processes.

    Currently, supports TTY output only, but it's not impossible to visualize
    extending this to a GUI or even web server as options.
    """

    def __init__(self):
        # defaultOpts

        self.cur_progress = -1
        self.progress_total = -1
        self.status = ""

        # Records number of modules built stats
        self.mod_total = -1
        self.mod_failed = 0
        self.mod_success = 0

    def set_status(self, new_status) -> None:
        """
        Set the "base" message to show as part of the update. E.g. "Compiling...".
        """
        self.status = Debug().colorize(new_status)

    def set_progress(self, new_progress) -> None:
        """
        Set the amount of progress made vs. the total progress possible.
        """
        old_progress = self.cur_progress
        self.cur_progress = new_progress

        if old_progress != new_progress:
            self.update()

    def set_progress_total(self, new_progress_total) -> None:
        """
        Set the total amount of progress deemed possible.
        """
        self.progress_total = new_progress_total

    def number_modules_total(self, new_total: int = None) -> int:
        """
        Get (or set, if arg provided) number of modules to be built.
        """
        if new_total:
            self.mod_total = new_total
        return self.mod_total

    def number_modules_succeeded(self, new_total: int | None = None) -> int:
        """
        Get (or set, if arg provided) number of modules built successfully.
        """
        if new_total:
            self.mod_success = new_total
        return self.mod_success

    def number_modules_failed(self, new_total: int | None = None) -> int:
        """
        Get (or set, if arg provided) number of modules not built successfully.
        """
        if new_total:
            self.mod_failed = new_total
        return self.mod_failed

    def update(self) -> None:
        """
        Send out the I/O needed to ensure the latest status is displayed.

        E.g. for TTY it clears the line and redisplays the current stats.
        """
        progress_total = self.progress_total
        msg = None

        mod_total, mod_success, mod_failed = self.mod_total, self.mod_success, self.mod_failed

        status_line = self.status

        if mod_total > 1:
            # Build up message in reverse order
            msg = f"{mod_total} projects"
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

        StatusView._clear_line_and_update(msg)

    @staticmethod
    def release_tty(msg: str = "") -> None:
        """
        For TTY outputs, this clears the line (if we actually had dirtied it) so the rest of the program can resume output from where it'd been left off.
        """
        StatusView._clear_line_and_update(Debug().colorize(msg))

    @staticmethod
    def _clear_line_and_update(msg: str) -> None:
        """
        Give escape sequence to return to column 1 and clear the entire line.

        Then print message and return to column 1 again in case somewhere else uses the tty.
        """
        print(f"\033[1G\033[K{msg}\033[1G", end="")
        sys.stdout.flush()
