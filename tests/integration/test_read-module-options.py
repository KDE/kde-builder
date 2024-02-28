import os
from ksblib.Util.Util import Util  # load early so we can override
from promise import Promise

# Now we can load ksb::Application, which will load a bunch more modules all
# using log_command and run_logged_p from ksb::Util
from ksblib.Application import Application
from ksblib.Updater.Git import Updater_Git
from ksblib.Debug import Debug


def test_option_reading():
    """
    Test basic option reading from rc-files
    """
    # Override ksb::Util::log_command for final test to see if it is called with 'cmake'
    
    CMD = []
    
    def mock_run_logged_p(module, filename, directory, argRef):
        nonlocal CMD
        if not argRef:
            raise "No arg to module"
        command = argRef
        if "cmake" in command:
            CMD = command
        
        return Promise.resolve(0)
    
    Util.run_logged_p = mock_run_logged_p
    app = Application("--pretend --rc-file tests/integration/fixtures/sample-rc/kdesrc-buildrc".split(" "))
    moduleList = app.modules
    
    assert len(moduleList) == 4, "Right number of modules"
    
    # module2 is last in rc-file so should sort last
    assert moduleList[3].name == "module2", "Right module name"
    
    scm = moduleList[3].scm()
    assert isinstance(scm, Updater_Git)
    
    branch, sourcetype = scm._determinePreferredCheckoutSource()
    
    assert branch == "refs/tags/fake-tag5", "Right tag name"
    assert sourcetype == "tag", "Result came back as a tag"
    
    # setmod2 is second module in set of 3 at start, should be second overall
    assert moduleList[1].name == "setmod2", "Right module name from module-set"
    branch, sourcetype = moduleList[1].scm()._determinePreferredCheckoutSource()
    
    assert branch == "refs/tags/tag-setmod2", "Right tag name (options block)"
    assert sourcetype == "tag", "options block came back as tag"
    
    # Test some of the option parsing indirectly by seeing how the value is input
    # into build system.
    
    # Override auto-detection since no source is downloaded
    moduleList[1].setOption({"override-build-system": "kde"})
    
    # Should do nothing in --pretend
    assert moduleList[1].setupBuildSystem(), 'setup fake build system'
    
    assert CMD, "run_logged_p cmake was called"
    assert len(CMD) == 12
    
    assert CMD[0] == "cmake", "CMake command should start with cmake"
    assert CMD[1] == "-B",    "Passed build dir to cmake"
    assert CMD[2] == ".",     "Passed cur dir as build dir to cmake"
    assert CMD[3] == "-S",    "Pass source dir to cmake"
    assert CMD[4] == "/tmp/setmod2", "CMake command should specify source directory after -S"
    assert CMD[5] == "-G", "CMake generator should be specified explicitly"
    assert CMD[6] == "Unix Makefiles", "Expect the default CMake generator to be used"
    assert CMD[7] == "-DCMAKE_EXPORT_COMPILE_COMMANDS:BOOL=ON", "Per default we generate compile_commands.json"
    assert CMD[8] == "-DCMAKE_BUILD_TYPE=a b", "CMake options can be quoted"
    assert CMD[9] == "bar=c", "CMake option quoting does not eat all options"
    assert CMD[10] == "baz", "Plain CMake options are preserved correctly"
    assert CMD[11] == f"""-DCMAKE_INSTALL_PREFIX={os.environ.get("HOME")}/kde/usr""", "Prefix is passed to cmake"
    
    # See https://phabricator.kde.org/D18165
    assert moduleList[0].getOption("cxxflags") == "", "empty cxxflags renders with no whitespace in module"
    Debug().setPretending(False)  # disable pretending, to not influence on other tests, because Debug is singleton
