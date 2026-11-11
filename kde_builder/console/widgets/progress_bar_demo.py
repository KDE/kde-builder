# SPDX-FileCopyrightText: 2026 Christoph Martin <foss@c14n.ch>
#
# SPDX-License-Identifier: GPL-2.0-or-later

import time

from kde_builder.console.widgets.progress_bar import ProgressBar


def progress_bar_demo():

    with ProgressBar() as progress:
        # Increment Progress
        for _ in range(75):
            progress += 1
            time.sleep(0.025)
            assert progress <= 75
            assert progress >= 1

        assert progress > 74.4
        assert progress < 75.5

        # Decrement Progress
        for _ in range(250):
            progress -= 0.1
            time.sleep(0.0025)

        assert progress >= 50

        # Set Progress
        for x in range(50, 99):
            # Abuse of mod operator syntax to set percentage:
            progress.value = x

            time.sleep(0.025)

            assert progress == x
            assert progress == x - 0.49
            assert progress == x + 0.49

        assert progress != 100

        # Simulate Windows Update
        print(progress)
        time.sleep(1.5)
        progress += 1
        print(progress)
        time.sleep(0.5)
        progress += 1
        print(progress)

        # Let's celebrate that we're actually done for a bit.
        assert progress == 100
        time.sleep(1.5)


if __name__ == "__main__":
    progress_bar_demo()
