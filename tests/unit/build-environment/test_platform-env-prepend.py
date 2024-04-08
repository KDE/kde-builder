import os
import re
from ksblib.BuildContext import BuildContext
from ksblib.Module.Module import Module


def test_environment_prepend():
    """
    Test that empty install-dir and/or qt-install-dir do not cause empty /bin settings to be configured in environment.
    """
    ctx = BuildContext()

    def no_bare_bin(arg):
        elem = arg.split(":")
        return not any(x == "/bin" for x in elem)

    mod = Module(ctx, "test")
    newPath = os.environ.get("PATH")
    newPath = re.sub(r"^/bin:", "", newPath)  # Remove existing bare /bin entries if present
    newPath = re.sub(r":/bin$", "", newPath)
    newPath = re.sub(r":/bin:", "", newPath)
    os.environ["PATH"] = newPath

    ctx.setOption({"install-dir": ""})  # must be set but empty
    ctx.setOption({"qt-install-dir": "/dev/null"})

    mod.setupEnvironment()

    assert "PATH" in ctx.env, "Entry created for PATH when setting up mod env"
    assert no_bare_bin(ctx.env["PATH"]), "/bin wasn't prepended to PATH"

    # --

    ctx.resetEnvironment()

    mod = Module(ctx, "test")
    newPath = os.environ.get("PATH")
    newPath = re.sub(r"^/bin:", "", newPath)  # Remove existing bare /bin entries if present
    newPath = re.sub(r":/bin$", "", newPath)
    newPath = re.sub(r":/bin:", "", newPath)
    os.environ["PATH"] = newPath

    ctx.setOption({"qt-install-dir": ""})  # must be set but empty
    ctx.setOption({"install-dir": "/dev/null"})

    mod.setupEnvironment()

    assert "PATH" in ctx.env, "Entry created for PATH when setting up mod env"
    assert no_bare_bin(ctx.env["PATH"]), "/bin wasn't prepended to PATH"

    # --

    ctx.resetEnvironment()

    mod = Module(ctx, "test")
    newPath = os.environ.get("PATH")
    newPath = re.sub(r"^/bin:", "", newPath)  # Remove existing bare /bin entries if present
    newPath = re.sub(r":/bin$", "", newPath)
    newPath = re.sub(r":/bin:", "", newPath)
    os.environ["PATH"] = newPath

    ctx.setOption({"qt-install-dir": "/dev/null"})
    ctx.setOption({"install-dir": "/dev/null"})

    mod.setupEnvironment()

    assert "PATH" in ctx.env, "Entry created for PATH when setting up mod env"
    assert no_bare_bin(ctx.env["PATH"]), "/bin wasn't prepended to PATH"

    # --

    # Ensure binpath and libpath options work

    ctx.resetEnvironment()

    mod = Module(ctx, "test")
    os.environ["PATH"] = "/bin:/usr/bin"

    ctx.setOption({"binpath": "/tmp/fake/bin"})
    ctx.setOption({"libpath": "/tmp/fake/lib:/tmp/fake/lib64"})

    mod.setupEnvironment()

    assert re.search("/tmp/fake/bin", ctx.env["PATH"]), "Ensure `binpath` present in generated PATH"
    assert re.search("/tmp/fake/lib", ctx.env["LD_LIBRARY_PATH"]), "Ensure `libpath` present in generated LD_LIBRARY_PATH"
