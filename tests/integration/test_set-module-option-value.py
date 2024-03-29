from ksblib.Application import Application
from ksblib.Debug import Debug


def test_set_module_option():
    """
    Test use of --set-module-option-value
    """
    app = Application("--pretend --rc-file tests/integration/fixtures/sample-rc/kdesrc-buildrc --set-module-option-value module2,tag,fake-tag10 --set-module-option-value setmod2,tag,tag-setmod10".split(" "))
    moduleList = app.modules
    assert len(moduleList) == 4, "Right number of modules"
    
    module = [m for m in moduleList if f"{m}" == "module2"][0]
    scm = module.scm()
    branch, sourcetype = scm._determinePreferredCheckoutSource()
    
    assert branch == "refs/tags/fake-tag10", "Right tag name"
    assert sourcetype == "tag", "Result came back as a tag"
    
    module = [m for m in moduleList if f"{m}" == "setmod2"][0]
    branch, sourcetype = module.scm()._determinePreferredCheckoutSource()
    
    assert branch == "refs/tags/tag-setmod10", "Right tag name (options block from cmdline)"
    assert sourcetype == "tag", "cmdline options block came back as tag"
    
    assert not module.isKDEProject(), "setmod2 is *not* a \"KDE\" project"
    assert module.fullProjectPath() == "setmod2", "fullProjectPath on non-KDE modules returns name"
    Debug().setPretending(False)  # disable pretending, to not influence on other tests, because Debug is singleton
