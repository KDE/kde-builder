from ksblib.Util import Util
from ksblib.Application import Application
from ksblib.BuildSystem.KDECMake import BuildSystem_KDECMake
from promise import Promise
from ksblib.Debug import Debug


def test_cmake_prefix(monkeypatch):
    """
    Verify that a user-set CMAKE_PREFIX_PATH is not removed, even if we supply
    "magic" of our own
    See bug 395627 -- https://bugs.kde.org/show_bug.cgi?id=395627
    """
    
    savedCommand = []
    log_called = 0
    
    # Redefine log_command to capture whether it was properly called.
    def mock_run_logged_p(module, filename, directory, argRef):
        nonlocal log_called
        nonlocal savedCommand
        log_called = 1
        savedCommand = argRef
        return Promise.resolve(0)  # success
    
    monkeypatch.setattr(Util.Util, "run_logged_p", mock_run_logged_p)
    
    args = "--pretend --rc-file tests/integration/fixtures/bug-395627/kdesrc-buildrc".split(" ")
    app = Application(args)
    moduleList = app.modules
    
    assert len(moduleList) == 6, "Right number of modules"
    assert isinstance(moduleList[0].buildSystem(), BuildSystem_KDECMake)
    
    # This requires log_command to be overridden above
    result = moduleList[0].setupBuildSystem()
    assert log_called == 1, "Overridden log_command was called"
    assert result, "Setup build system for auto-set prefix path"
    
    # We should expect an auto-set -DCMAKE_PREFIX_PATH passed to cmake somewhere
    prefix = next((x for x in savedCommand if "-DCMAKE_PREFIX_PATH" in x), None)
    assert prefix == "-DCMAKE_PREFIX_PATH=/tmp/qt5", "Prefix path set to custom Qt prefix"
    
    result = moduleList[2].setupBuildSystem()
    assert result, "Setup build system for manual-set prefix path"
    
    prefixes = [el for el in savedCommand if "-DCMAKE_PREFIX_PATH" in el]
    assert len(prefixes) == 1, "Only one set prefix path in manual mode"
    if prefixes:
        assert prefixes[0] == "-DCMAKE_PREFIX_PATH=FOO", "Manual-set prefix path is as set by user"
    
    result = moduleList[4].setupBuildSystem()
    assert result, "Setup build system for manual-set prefix path"
    
    prefixes = [el for el in savedCommand if "-DCMAKE_PREFIX_PATH" in el]
    assert len(prefixes) == 1, "Only one set prefix path in manual mode"
    if prefixes:
        assert prefixes[0] == "-DCMAKE_PREFIX_PATH:PATH=BAR", "Manual-set prefix path is as set by user"
    Debug().setPretending(False)  # disable pretending, to not influence on other tests, because Debug is singleton
