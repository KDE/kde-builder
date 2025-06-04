# SPDX-FileCopyrightText: 2019, 2021, 2022 Michael Pyne <mpyne@kde.org>
# SPDX-FileCopyrightText: 2023 - 2024 Andrew Shark <ashark@linuxcomp.ru>
#
# SPDX-License-Identifier: GPL-2.0-or-later

import os
import re

from kde_builder_lib.build_context import BuildContext
from kde_builder_lib.module.module import Module


def test_environment_prepend():
    """
    Test that empty install-dir and/or qt-install-dir do not cause empty /bin settings to be configured in environment.
    """
    ctx = BuildContext()

    def no_bare_bin(arg):
        elem = arg.split(":")
        return not any(x == "/bin" for x in elem)

    mod = Module(ctx, "test")
    mod.set_scm_type("git")
    new_path = os.environ.get("PATH")
    new_path = re.sub(r"^/bin:", "", new_path)  # Remove existing bare /bin entries if present
    new_path = re.sub(r":/bin$", "", new_path)
    new_path = re.sub(r":/bin:", "", new_path)
    os.environ["PATH"] = new_path

    ctx.set_option("install-dir", "")  # must be set but empty
    ctx.set_option("qt-install-dir", "/dev/null")

    mod.setup_environment()

    assert "PATH" in mod.env, "Entry created for PATH when setting up mod env"
    assert no_bare_bin(mod.env["PATH"]), "/bin wasn't prepended to PATH"

    # --

    mod.reset_environment()

    mod = Module(ctx, "test")
    mod.set_scm_type("git")
    new_path = os.environ.get("PATH")
    new_path = re.sub(r"^/bin:", "", new_path)  # Remove existing bare /bin entries if present
    new_path = re.sub(r":/bin$", "", new_path)
    new_path = re.sub(r":/bin:", "", new_path)
    os.environ["PATH"] = new_path

    ctx.set_option("qt-install-dir", "")  # must be set but empty
    ctx.set_option("install-dir", "/dev/null")

    mod.setup_environment()

    assert "PATH" in mod.env, "Entry created for PATH when setting up mod env"
    assert no_bare_bin(mod.env["PATH"]), "/bin wasn't prepended to PATH"

    # --

    mod.reset_environment()

    mod = Module(ctx, "test")
    mod.set_scm_type("git")
    new_path = os.environ.get("PATH")
    new_path = re.sub(r"^/bin:", "", new_path)  # Remove existing bare /bin entries if present
    new_path = re.sub(r":/bin$", "", new_path)
    new_path = re.sub(r":/bin:", "", new_path)
    os.environ["PATH"] = new_path

    ctx.set_option("qt-install-dir", "/dev/null")
    ctx.set_option("install-dir", "/dev/null")

    mod.setup_environment()

    assert "PATH" in mod.env, "Entry created for PATH when setting up mod env"
    assert no_bare_bin(mod.env["PATH"]), "/bin wasn't prepended to PATH"

    # --

    # Ensure binpath and libpath options work

    mod.reset_environment()

    mod = Module(ctx, "test")
    mod.set_scm_type("git")
    os.environ["PATH"] = "/bin:/usr/bin"

    ctx.set_option("binpath", "/tmp/fake/bin")
    ctx.set_option("libpath", "/tmp/fake/lib:/tmp/fake/lib64")

    mod.setup_environment()

    assert re.search("/tmp/fake/bin", mod.env["PATH"]), "Ensure `binpath` present in generated PATH"
    assert re.search("/tmp/fake/lib", mod.env["LD_LIBRARY_PATH"]), "Ensure `libpath` present in generated LD_LIBRARY_PATH"
