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
        self.current_project_cur_progress = -1
        self.current_project_full_progress = -1
        """
        The total amount of progress deemed possible.
        """
        self.status = ""
        """
        The "base" message to show as part of the update. E.g. "Compiling...".
        """

        # Records number of modules built stats
        self.mod_total = -1
        """
        Number of modules to be built.
        """
        self.mod_failed = 0
        """
        Number of modules not built successfully.
        """
        self.mod_success = 0
        """
        Number of modules built successfully.
        """

    def set_progress(self, new_progress) -> None:
        """
        Set the amount of progress made vs. the total progress possible.
        """
        old_progress = self.current_project_cur_progress
        self.current_project_cur_progress = new_progress

        if old_progress != new_progress:
            self.update()

    def update(self) -> None:
        """
        Send out the I/O needed to ensure the latest status is displayed.

        E.g. for TTY it clears the line and redisplays the current stats.
        """
        current_project_full_progress = self.current_project_full_progress

        mod_total, mod_success, mod_failed = self.mod_total, self.mod_success, self.mod_failed

        status_line = self.status

        if mod_total > 1:
            # Build up message in reverse order
            tail_msg = f"{mod_total} projects"
            if mod_failed:
                tail_msg = Debug().colorize(f"r[b[{mod_failed}] failed, ") + tail_msg
            if mod_success:
                tail_msg = Debug().colorize(f"g[b[{mod_success}] built, ") + tail_msg

            status_line = status_line + f" ({tail_msg})"

        if current_project_full_progress > 0:
            msg = f"{self.current_project_cur_progress * 100 / current_project_full_progress:.1f}%{status_line}"

        elif self.current_project_cur_progress < 0:
            msg = status_line
        else:
            spinner = "-\\|/"
            msg = spinner[self.current_project_cur_progress % len(spinner)] + status_line

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
