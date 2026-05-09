# SPDX-FileCopyrightText: 2026 Andrew Shark <ashark@linuxcomp.ru>
#
# SPDX-License-Identifier: GPL-2.0-or-later

from kde_builder_lib.application import Application

def test_install_login_session(monkeypatch):
    """
    Test use of --install-login-session-only.
    """
    app = Application("--pretend --rc-file tests/integration/fixtures/sample-rc/kde-builder.yaml --install-login-session-only".split(" "))
    assert app.run_mode == "install-login-session-only"
    app.generate_module_list()
    module_list = app.modules
    assert len(module_list) == 0, "Right number of projects"

    install_login_session_called = False

    def mock_install_login_session(self):
        nonlocal install_login_session_called
        install_login_session_called = True
        return 0

    monkeypatch.setattr(Application, "install_login_session", mock_install_login_session)

    app.run_all_module_phases()
    assert install_login_session_called, "install_login_session method was called"
