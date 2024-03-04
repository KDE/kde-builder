from ksblib.Application import Application
from ksblib.Debug import Debug


def test_kde_projects():
    """
    Verify that test kde-project data still results in workable build.
    """
    
    # The file has a module-set that only refers to juk but should expand to
    # kcalc juk in that order
    args = "--pretend --rc-file tests/integration/fixtures/kde-projects/kdesrc-buildrc-with-deps".split(" ")
    app = Application(args)
    moduleList = app.modules
    
    assert len(moduleList) == 3, "Right number of modules (include-dependencies)"
    assert moduleList[0].name == "kcalc", "Right order: kcalc before juk (test dep data)"
    assert moduleList[1].name == "juk", "Right order: juk after kcalc (test dep data)"
    assert moduleList[2].name == "kde-builder", "Right order: dolphin after juk (implicit order)"
    assert moduleList[0].getOption("tag") == "tag-setmod2", "options block works for indirect reference to kde-projects module"
    assert moduleList[0].getOption("cmake-generator") == "Ninja", "Global opts seen even with other options"
    assert moduleList[1].getOption("cmake-generator") == "Make", "options block works for kde-projects module-set"
    assert moduleList[1].getOption("cmake-options") == "-DSET_FOO:BOOL=ON", "module options block can override set options block"
    assert moduleList[2].getOption("cmake-generator") == 'Make', "options block works for kde-projects module-set after options"
    assert moduleList[2].getOption("cmake-options") == "-DSET_FOO:BOOL=ON", "module-set after options can override options block"
    Debug().setPretending(False)  # disable pretending, to not influence on other tests, because Debug is singleton
